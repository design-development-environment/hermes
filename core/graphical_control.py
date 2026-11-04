#!/usr/bin/env python3
"""Cinnamon/X11 appliance integration for Hermes Alpha.

All actions run as the logged-in desktop user through the authenticated Action
Bridge.  The module deliberately avoids privileged package, driver, network,
power-off, and account-management operations.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from platform_support import graphical_environment, platform_status, require_x11_automation


router = APIRouter(prefix="/graphical", tags=["Cinnamon desktop integration"])
MAX_OUTPUT = 40_000
MAX_CLIPBOARD = 1_000_000


def _which(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise HTTPException(404, f"Required desktop utility is not installed: {name}")
    return executable


def _run(command: list[str], *, desktop: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=graphical_environment() if desktop else os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(502, f"Desktop command failed: {type(exc).__name__}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "Desktop command failed").strip()[-2000:]
        raise HTTPException(502, detail)
    return result


def _x11() -> dict[str, str]:
    try:
        return require_x11_automation()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


class ClipboardReadRequest(BaseModel):
    confirmed: bool = False


class ClipboardWriteRequest(BaseModel):
    text: str = Field(max_length=MAX_CLIPBOARD)


class VolumeRequest(BaseModel):
    percent: int = Field(ge=0, le=150)


class MuteRequest(BaseModel):
    muted: bool


class MediaRequest(BaseModel):
    action: str = Field(pattern=r"^(play|pause|play-pause|next|previous|stop)$")
    player: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_.:-]*$")


class WorkspaceRequest(BaseModel):
    workspace: int = Field(ge=0, le=63)


class WindowWorkspaceRequest(WorkspaceRequest):
    window_id: str = Field(pattern=r"^0x[0-9a-fA-F]+$")
    follow: bool = False


class SettingsPanelRequest(BaseModel):
    panel: str = Field(pattern=r"^(display|sound|keyboard|mouse|power|network|themes|backgrounds|fonts|windows|workspaces|apps|info)$")


class ConfirmedRequest(BaseModel):
    confirmed: bool = False


@router.get("/readiness", operation_id="get_graphical_appliance_readiness")
def graphical_readiness():
    """Inspect target hardware, Cinnamon/X11, drivers, and graphical utilities without changing anything."""
    status = platform_status()
    try:
        cpu_name = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines()
            if line.lower().startswith("model name")
        )
    except (OSError, StopIteration, IndexError):
        cpu_name = "unknown"
    utilities = {
        name: bool(shutil.which(name))
        for name in (
            "wmctrl", "xdotool", "xclip", "pactl", "playerctl", "xrandr",
            "cinnamon-settings", "cinnamon-screensaver-command", "vainfo", "inxi",
            "notify-send", "gio", "bwrap", "node", "npm", "git", "rg",
            "nmcli", "gsettings",
        )
    }
    desktop_name = status.get("desktop", "").casefold()
    cinnamon_settings = bool(shutil.which("cinnamon-settings"))
    xfce_settings = bool(shutil.which("xfce4-settings-manager"))
    supported_desktop = "cinnamon" in desktop_name or "xfce" in desktop_name
    target = {
        "architecture": "amd64",
        "desktop": "Linux Mint Cinnamon or XFCE",
        "session": "X11 preferred; Wayland has documented limitations",
        "local_ai": False,
        "drivers": "preinstalled by the owner; Hermes does not install GPU drivers",
    }
    checks = {
        "amd64": status["architecture"] == "amd64",
        "debian_family": status["distribution"]["debian_family"],
        "linux_mint": status["distribution"]["id"] == "linuxmint",
        "supported_desktop": supported_desktop,
        "x11_or_wayland": status["session"] in {"x11", "wayland"},
        "gpu_driver_present": any(Path(f"/sys/module/{module}").exists() for module in ("i915", "amdgpu", "nvidia")) or Path("/dev/dri").exists(),
    }
    utilities["cinnamon-settings"] = cinnamon_settings
    utilities["xfce4-settings-manager"] = xfce_settings
    required = ("wmctrl", "xdotool", "xclip", "pactl", "playerctl", "xrandr", "notify-send", "gio", "bwrap", "git", "rg", "nmcli", "gsettings")
    missing = [name for name in required if not utilities[name]]
    if not (cinnamon_settings or xfce_settings):
        missing.append("cinnamon-settings|xfce4-settings-manager")
    return {
        "ready": all(checks[key] for key in ("amd64", "debian_family", "linux_mint", "supported_desktop", "x11_or_wayland")) and not missing,
        "target_profile": target,
        "detected": {"cpu": cpu_name, "gpu_driver": next((module for module in ("i915", "amdgpu", "nvidia") if Path(f"/sys/module/{module}").exists()), "unknown"), **status},
        "checks": checks,
        "utilities": utilities,
        "missing_required_utilities": missing,
        "driver_note": "GPU drivers are owner-installed and hardware-specific; Hermes only verifies that Linux exposes a graphics device.",
    }


@router.get("/network", operation_id="get_desktop_network_status")
def network_status():
    """Return NetworkManager state and device connections without exposing credentials."""
    nmcli = _which("nmcli")
    general = _run([nmcli, "--terse", "--fields", "STATE,CONNECTIVITY", "general", "status"], desktop=False).stdout.strip()
    devices = _run([nmcli, "--terse", "--fields", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"], desktop=False).stdout.splitlines()
    return {"success": True, "general": general, "devices": devices}


@router.get("/power-policy", operation_id="get_appliance_power_policy")
def get_power_policy():
    """Read Cinnamon's AC inactivity policy for this always-on appliance."""
    gsettings = _which("gsettings")
    schema = "org.cinnamon.settings-daemon.plugins.power"
    timeout = _run([gsettings, "get", schema, "sleep-inactive-ac-timeout"]).stdout.strip()
    action = _run([gsettings, "get", schema, "sleep-inactive-ac-type"]).stdout.strip().strip("'")
    return {"success": True, "ac_timeout_seconds": int(timeout), "ac_action": action, "keep_awake": int(timeout) == 0 or action == "nothing"}


@router.post("/power-policy/keep-awake", operation_id="enable_appliance_keep_awake")
def enable_keep_awake(request: ConfirmedRequest):
    """Disable automatic AC suspend after explicit confirmation; manual lock remains available."""
    if not request.confirmed:
        raise HTTPException(403, "Changing the desktop power policy requires explicit confirmation")
    gsettings = _which("gsettings")
    schema = "org.cinnamon.settings-daemon.plugins.power"
    before = get_power_policy()
    _run([gsettings, "set", schema, "sleep-inactive-ac-timeout", "0"])
    _run([gsettings, "set", schema, "sleep-inactive-ac-type", "nothing"])
    after = get_power_policy()
    return {"success": True, "before": before, "after": after, "note": "Manual lock and explicit shutdown remain available"}


@router.get("/monitors", operation_id="get_desktop_monitor_layout")
def monitor_layout():
    """Return connected displays, modes, positions, and the current desktop size."""
    environment = _x11()
    result = subprocess.run([_which("xrandr"), "--query"], capture_output=True, text=True, timeout=10, check=False, env=environment)
    if result.returncode:
        raise HTTPException(502, (result.stderr or "xrandr failed").strip())
    displays = []
    pattern = re.compile(r"^(\S+) connected(?: primary)?(?: (\d+)x(\d+)\+(\d+)\+(\d+))?")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            name, width, height, x, y = match.groups()
            displays.append({
                "name": name,
                "active": width is not None,
                "width": int(width) if width else None,
                "height": int(height) if height else None,
                "x": int(x) if x else None,
                "y": int(y) if y else None,
                "primary": " connected primary " in f" {line} ",
            })
    return {"success": True, "displays": displays, "raw": result.stdout[-MAX_OUTPUT:]}


@router.post("/clipboard/read", operation_id="read_desktop_clipboard")
def read_clipboard(request: ClipboardReadRequest):
    """Read text from the desktop clipboard only after explicit confirmation because it may contain secrets."""
    if not request.confirmed:
        raise HTTPException(403, "Reading the clipboard may expose sensitive text and requires explicit confirmation")
    _x11()
    result = _run([_which("xclip"), "-selection", "clipboard", "-o"])
    text = result.stdout
    return {"success": True, "text": text[:MAX_CLIPBOARD], "characters": len(text), "truncated": len(text) > MAX_CLIPBOARD}


@router.post("/clipboard/write", operation_id="write_desktop_clipboard")
def write_clipboard(request: ClipboardWriteRequest):
    """Replace the desktop clipboard with supplied text."""
    _x11()
    _run([_which("xclip"), "-selection", "clipboard", "-in"], input_text=request.text)
    return {"success": True, "characters": len(request.text)}


@router.get("/audio", operation_id="get_desktop_audio_status")
def audio_status():
    """Return default speaker volume, mute state, and default audio devices."""
    pactl = _which("pactl")
    volume = _run([pactl, "get-sink-volume", "@DEFAULT_SINK@"]).stdout.strip()
    muted = _run([pactl, "get-sink-mute", "@DEFAULT_SINK@"]).stdout.strip()
    info = _run([pactl, "info"]).stdout
    defaults = {}
    for line in info.splitlines():
        if line.startswith(("Default Sink:", "Default Source:", "Server Name:")):
            key, value = line.split(":", 1)
            defaults[key.strip().lower().replace(" ", "_")] = value.strip()
    return {"success": True, "volume": volume, "mute": muted, **defaults}


@router.post("/audio/volume", operation_id="set_desktop_audio_volume")
def set_audio_volume(request: VolumeRequest):
    """Set default speaker volume from 0 to 150 percent."""
    _run([_which("pactl"), "set-sink-volume", "@DEFAULT_SINK@", f"{request.percent}%"])
    return {"success": True, "percent": request.percent}


@router.post("/audio/mute", operation_id="set_desktop_audio_mute")
def set_audio_mute(request: MuteRequest):
    """Mute or unmute the default speakers."""
    _run([_which("pactl"), "set-sink-mute", "@DEFAULT_SINK@", "1" if request.muted else "0"])
    return {"success": True, "muted": request.muted}


@router.get("/media", operation_id="list_desktop_media_players")
def media_players():
    """List media players that expose MPRIS controls."""
    result = subprocess.run(
        [_which("playerctl"), "--list-all"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=graphical_environment(),
    )
    if result.returncode not in {0, 1}:
        raise HTTPException(502, (result.stderr or "playerctl failed").strip())
    return {"success": True, "players": [line for line in result.stdout.splitlines() if line]}


@router.post("/media", operation_id="control_desktop_media")
def control_media(request: MediaRequest):
    """Control play, pause, track navigation, or stop through MPRIS."""
    command = [_which("playerctl")]
    if request.player:
        command.extend(["--player", request.player])
    command.append(request.action)
    _run(command)
    return {"success": True, "action": request.action, "player": request.player or "default"}


@router.get("/workspaces", operation_id="list_desktop_workspaces")
def list_workspaces():
    """List Cinnamon/X11 workspaces and identify the active workspace."""
    environment = _x11()
    result = subprocess.run([_which("wmctrl"), "-d"], capture_output=True, text=True, timeout=10, check=False, env=environment)
    if result.returncode:
        raise HTTPException(502, (result.stderr or "wmctrl failed").strip())
    workspaces = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 9)
        if len(parts) >= 2 and parts[0].isdigit():
            workspaces.append({"index": int(parts[0]), "active": parts[1] == "*", "description": line})
    return {"success": True, "workspaces": workspaces}


@router.post("/workspaces/switch", operation_id="switch_desktop_workspace")
def switch_workspace(request: WorkspaceRequest):
    """Switch to an exact Cinnamon/X11 workspace number."""
    environment = _x11()
    result = subprocess.run([_which("wmctrl"), "-s", str(request.workspace)], capture_output=True, text=True, timeout=10, check=False, env=environment)
    if result.returncode:
        raise HTTPException(502, (result.stderr or "Workspace switch failed").strip())
    return {"success": True, "workspace": request.workspace}


@router.post("/workspaces/move-window", operation_id="move_window_to_desktop_workspace")
def move_window_to_workspace(request: WindowWorkspaceRequest):
    """Move an exact listed window to a workspace and optionally follow it."""
    environment = _x11()
    windows = subprocess.run([_which("wmctrl"), "-lx"], capture_output=True, text=True, timeout=10, check=True, env=environment).stdout
    if request.window_id.casefold() not in windows.casefold():
        raise HTTPException(404, "Window ID was not found")
    result = subprocess.run([_which("wmctrl"), "-ir", request.window_id, "-t", str(request.workspace)], capture_output=True, text=True, timeout=10, check=False, env=environment)
    if result.returncode:
        raise HTTPException(502, (result.stderr or "Window move failed").strip())
    if request.follow:
        subprocess.run([_which("wmctrl"), "-s", str(request.workspace)], check=True, timeout=10, env=environment)
    return {"success": True, "window_id": request.window_id, "workspace": request.workspace, "followed": request.follow}


@router.post("/settings", operation_id="open_cinnamon_settings_panel")
def open_settings(request: SettingsPanelRequest):
    """Open an approved Cinnamon settings panel."""
    desktop = platform_status().get("desktop", "").casefold()
    if "xfce" in desktop:
        executable = _which("xfce4-settings-manager")
        command = [executable]
    else:
        executable = _which("cinnamon-settings")
        command = [executable, request.panel]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=graphical_environment(),
    )
    return {"success": True, "panel": request.panel, "process_id": process.pid}


@router.post("/lock", operation_id="lock_desktop_session")
def lock_desktop(request: ConfirmedRequest):
    """Lock the current desktop after explicit confirmation."""
    if not request.confirmed:
        raise HTTPException(403, "Locking the desktop requires explicit confirmation")
    if shutil.which("cinnamon-screensaver-command"):
        command = [_which("cinnamon-screensaver-command"), "--lock"]
    else:
        command = [_which("loginctl"), "lock-session"]
    _run(command)
    return {"success": True, "locked": True, "note": "Global GUI control pauses until the desktop is unlocked"}

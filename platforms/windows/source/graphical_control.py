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
import windows_commands as subprocess
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
    return platform_status()


@router.get("/network", operation_id="get_desktop_network_status")
def network_status():
    import psutil
    return {'interfaces':{k:v._asdict() for k,v in psutil.net_if_stats().items()}}


@router.get("/power-policy", operation_id="get_appliance_power_policy")
def get_power_policy():
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: get_power_policy')


@router.post("/power-policy/keep-awake", operation_id="enable_appliance_keep_awake")
def enable_keep_awake(request: ConfirmedRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: enable_keep_awake')


@router.get("/monitors", operation_id="get_desktop_monitor_layout")
def monitor_layout():
    import win32api
    return {'monitors':[win32api.GetMonitorInfo(m[0]) for m in win32api.EnumDisplayMonitors()]}


@router.post("/clipboard/read", operation_id="read_desktop_clipboard")
def read_clipboard(request: ClipboardReadRequest):
    if not request.confirmed: raise HTTPException(400,'Clipboard read requires confirmation')
    import pyperclip
    return {'success':True,'text':pyperclip.paste()}


@router.post("/clipboard/write", operation_id="write_desktop_clipboard")
def write_clipboard(request: ClipboardWriteRequest):
    import pyperclip
    pyperclip.copy(request.text)
    return {'success':True}


@router.get("/audio", operation_id="get_desktop_audio_status")
def audio_status():
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: audio_status')


@router.post("/audio/volume", operation_id="set_desktop_audio_volume")
def set_audio_volume(request: VolumeRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: set_audio_volume')


@router.post("/audio/mute", operation_id="set_desktop_audio_mute")
def set_audio_mute(request: MuteRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: set_audio_mute')


@router.get("/media", operation_id="list_desktop_media_players")
def media_players():
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: media_players')


@router.post("/media", operation_id="control_desktop_media")
def control_media(request: MediaRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: control_media')


@router.get("/workspaces", operation_id="list_desktop_workspaces")
def list_workspaces():
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: list_workspaces')


@router.post("/workspaces/switch", operation_id="switch_desktop_workspace")
def switch_workspace(request: WorkspaceRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: switch_workspace')


@router.post("/workspaces/move-window", operation_id="move_window_to_desktop_workspace")
def move_window_to_workspace(request: WindowWorkspaceRequest):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: move_window_to_workspace')


@router.post("/settings", operation_id="open_cinnamon_settings_panel")
def open_settings(request: SettingsPanelRequest):
    os.startfile('ms-settings:')
    return {'success':True}


@router.post("/lock", operation_id="lock_desktop_session")
def lock_desktop(request: ConfirmedRequest):
    if not request.confirmed: raise HTTPException(400,'Confirmation required')
    import ctypes
    if not ctypes.windll.user32.LockWorkStation(): raise HTTPException(500,'Windows could not lock the desktop')
    return {'success':True}

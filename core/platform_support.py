#!/usr/bin/env python3
"""Portable Linux/desktop discovery shared by every Hermes service.

Hermes keeps its cloud, file, terminal, browser-CDP, memory, and planning core
independent of the graphical session.  This module isolates the small portion
that varies by distribution, CPU architecture, display protocol, and browser.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(os.environ.get("HERMES_ROOT", Path(__file__).resolve().parent)).expanduser().resolve()
DATA_DIR = Path(os.environ.get("HERMES_DATA_DIR", Path.home() / ".local/share/hermes")).expanduser().resolve()
CONFIG_DIR = Path(os.environ.get("HERMES_CONFIG_DIR", Path.home() / ".config/hermes")).expanduser().resolve()


def _os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def normalized_arch(machine: Optional[str] = None) -> str:
    value = (machine or platform.machine()).lower()
    aliases = {
        "x86_64": "amd64", "amd64": "amd64",
        "aarch64": "arm64", "arm64": "arm64",
    }
    return aliases.get(value, value or "unknown")


def supported_debian_family(release: Optional[dict[str, str]] = None) -> bool:
    release = release or _os_release()
    family = {release.get("ID", ""), *release.get("ID_LIKE", "").split()}
    return bool(family & {"debian", "ubuntu"})


def _desktop_environment_from_processes() -> dict[str, str]:
    """Recover GUI variables when a lingering user service started before login."""
    wanted = {
        "DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
        "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
    }
    uid = os.getuid()
    best: dict[str, str] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            raw = (entry / "environ").read_bytes().split(b"\0")
        except (OSError, PermissionError):
            continue
        values = {}
        for item in raw:
            if b"=" not in item:
                continue
            key, value = item.split(b"=", 1)
            name = key.decode(errors="ignore")
            if name in wanted:
                values[name] = value.decode(errors="ignore")
        if values.get("WAYLAND_DISPLAY") or values.get("DISPLAY"):
            if values.get("XDG_SESSION_TYPE"):
                return values
            best = values
    return best


def graphical_environment(base: Optional[dict[str, str]] = None) -> dict[str, str]:
    result = dict(os.environ if base is None else base)
    discovered = {} if result.get("DISPLAY") or result.get("WAYLAND_DISPLAY") else _desktop_environment_from_processes()
    for key, value in discovered.items():
        if value and not result.get(key):
            result[key] = value
    result.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    session = result.get("XDG_SESSION_TYPE", "").lower()
    if session not in {"x11", "wayland"}:
        if result.get("WAYLAND_DISPLAY"):
            result["XDG_SESSION_TYPE"] = "wayland"
        elif result.get("DISPLAY"):
            result["XDG_SESSION_TYPE"] = "x11"
        else:
            result["XDG_SESSION_TYPE"] = "headless"
    return result


def session_type(environ: Optional[dict[str, str]] = None) -> str:
    if environ is not None:
        explicit = environ.get("XDG_SESSION_TYPE", "").lower()
        if explicit in {"x11", "wayland", "headless"}:
            return explicit
        if environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        if environ.get("DISPLAY"):
            return "x11"
    return graphical_environment(environ).get("XDG_SESSION_TYPE", "headless").lower()


def find_browser(preference: str = "chromium") -> Optional[str]:
    if preference == "firefox":
        candidates = ("firefox", "firefox-esr")
    else:
        # Chromium is available on both amd64 and arm64; Google Chrome is amd64-only.
        candidates = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def xdg_user_directory(name: str) -> Path:
    command = shutil.which("xdg-user-dir")
    if command:
        import subprocess
        result = subprocess.run([command, name], capture_output=True, text=True, timeout=3, check=False)
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            return Path(value).expanduser().resolve()
    fallback = name.title() if name != "DOWNLOAD" else "Downloads"
    return (Path.home() / fallback).resolve()


def writable_roots() -> tuple[Path, ...]:
    names = ("DESKTOP", "DOCUMENTS", "DOWNLOAD", "PICTURES", "MUSIC", "VIDEOS")
    roots = [xdg_user_directory(name) for name in names]
    roots.append(PROJECT_ROOT)
    return tuple(dict.fromkeys(roots))


def openwebui_data_dir() -> Path:
    configured = os.environ.get("HERMES_OPENWEBUI_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    legacy = Path.home() / "AI Assistant/open-webui-data"
    return legacy if legacy.exists() else DATA_DIR / "open-webui-data"


def require_x11_automation() -> dict[str, str]:
    environment = graphical_environment()
    current = session_type(environment)
    if current != "x11":
        raise RuntimeError(
            f"This global window/input action requires an X11 session; detected {current}. "
            "Hermes core and managed-browser tools remain available."
        )
    missing = [name for name in ("wmctrl", "xdotool") if not shutil.which(name)]
    if missing:
        raise RuntimeError("Missing X11 automation packages: " + ", ".join(missing))
    return environment


def screenshot_backend(environ: Optional[dict[str, str]] = None) -> Optional[str]:
    current = session_type(environ)
    candidates = ("grim", "gnome-screenshot") if current == "wayland" else ("gnome-screenshot", "scrot", "import")
    return next((name for name in candidates if shutil.which(name)), None)


def platform_status() -> dict:
    release = _os_release()
    environment = graphical_environment()
    current = session_type(environment)
    browser = find_browser()
    x11_ready = current == "x11" and all(shutil.which(name) for name in ("wmctrl", "xdotool"))
    try:
        memory_kib = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:")))
        memory_bytes = memory_kib * 1024
    except (OSError, StopIteration, ValueError):
        memory_bytes = 0
    try:
        storage = shutil.disk_usage(Path.home())
        storage_free_bytes = storage.free
    except OSError:
        storage_free_bytes = 0
    return {
        "distribution": {
            "id": release.get("ID", "unknown"),
            "name": release.get("PRETTY_NAME", release.get("NAME", "Unknown Linux")),
            "version": release.get("VERSION_ID", ""),
            "debian_family": supported_debian_family(release),
        },
        "architecture": normalized_arch(),
        "architecture_supported": normalized_arch() in {"amd64", "arm64"},
        "memory_bytes": memory_bytes,
        "storage_free_bytes": storage_free_bytes,
        "cpu_count": os.cpu_count() or 1,
        "session": current,
        "desktop": environment.get("XDG_CURRENT_DESKTOP", ""),
        "browser": browser,
        "screenshot_backend": screenshot_backend(environment),
        "capabilities": {
            "cloud_ai": True,
            "files_terminal_code": True,
            "web_and_managed_browser": bool(browser),
            "desktop_screenshot": screenshot_backend(environment) is not None,
            "global_window_keyboard_mouse": x11_ready,
        },
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "openwebui_data_dir": str(openwebui_data_dir()),
    }

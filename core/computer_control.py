#!/usr/bin/env python3
"""Hermes V5.3 computer operator capabilities.

Commands run as the logged-in user. Development commands are isolated with
bubblewrap so they can write only inside the selected working directory.
"""

from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from platform_support import PROJECT_ROOT, graphical_environment, platform_status, require_x11_automation, writable_roots


router = APIRouter(prefix="/computer", tags=["Hermes V5.3 computer operator"])
HOME = Path.home().resolve()
WRITE_ROOTS = writable_roots()
MAX_TEXT_BYTES = 2_000_000
MAX_COMMAND_OUTPUT = 40_000
ALLOWED_COMMANDS = {
    "bash", "bun", "cargo", "cmake", "deno", "df", "du", "file", "find",
    "git", "go", "head", "ls", "make", "node", "npm", "npx", "pnpm",
    "python", "python3", "pytest", "rg", "sed", "stat", "tail", "uname",
    "uptime", "wc", "which",
}
BLOCKED_ARGUMENTS = {"-c", "--eval", "-e"}


def _x11_run(command: list[str], **kwargs):
    try:
        environment = require_x11_automation()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        return subprocess.run(command, env=environment, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"Required desktop utility is missing: {command[0]}") from exc


def writable_path(value: str, *, may_not_exist: bool = False) -> Path:
    raw = Path(value).expanduser()
    target = raw.resolve(strict=not may_not_exist)
    if not any(target == root or root in target.parents for root in WRITE_ROOTS):
        raise HTTPException(403, "Path is outside Hermes writable folders")
    return target


def command_result(result: subprocess.CompletedProcess, command: list[str], cwd: Path):
    stdout = result.stdout[-MAX_COMMAND_OUTPUT:]
    stderr = result.stderr[-MAX_COMMAND_OUTPUT:]
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "command": command,
        "cwd": str(cwd),
        "stdout": stdout,
        "stderr": stderr,
        "output_truncated": (
            len(result.stdout) > MAX_COMMAND_OUTPUT
            or len(result.stderr) > MAX_COMMAND_OUTPUT
        ),
    }


class PathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


class WriteTextRequest(PathRequest):
    content: str = Field(max_length=2_000_000)
    overwrite: bool = False
    create_parents: bool = True


class AppendTextRequest(PathRequest):
    content: str = Field(max_length=500_000)
    create_parents: bool = True


class TwoPathRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2000)
    destination: str = Field(min_length=1, max_length=2000)
    overwrite: bool = False


class LaunchAppsRequest(BaseModel):
    applications: list[str] = Field(min_length=1, max_length=10)


class OpenTargetRequest(BaseModel):
    target: str = Field(min_length=1, max_length=4000)


class TerminalRequest(BaseModel):
    program: str = Field(min_length=1, max_length=100)
    arguments: list[str] = Field(default_factory=list, max_length=100)
    cwd: str = Field(default=str(PROJECT_ROOT), min_length=1, max_length=2000)
    timeout_seconds: int = Field(default=30, ge=1, le=180)


class CloseWindowRequest(BaseModel):
    window_id: str = Field(pattern=r"^0x[0-9a-fA-F]+$")


class KeySequenceRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=200)
    keys: list[str] = Field(min_length=1, max_length=20)


class MouseDragRequest(BaseModel):
    start_x: int = Field(ge=0)
    start_y: int = Field(ge=0)
    end_x: int = Field(ge=0)
    end_y: int = Field(ge=0)
    button: int = Field(default=1, ge=1, le=3)


class WindowLayoutRequest(BaseModel):
    window_id: str = Field(pattern=r"^0x[0-9a-fA-F]+$")
    action: str = Field(pattern=r"^(maximize|restore|minimize|move_resize)$")
    x: int | None = None
    y: int | None = None
    width: int | None = Field(default=None, ge=100)
    height: int | None = Field(default=None, ge=100)


class TypeWindowRequest(BaseModel):
    window_id: str = Field(pattern=r"^0x[0-9a-fA-F]+$")
    text: str = Field(max_length=20_000)
    replace_selection: bool = False


@router.get("/applications", operation_id="list_installed_applications")
def list_applications(query: str = "", limit: int = 100):
    limit = max(1, min(limit, 200))
    results = []
    directories = [Path("/usr/share/applications"), HOME / ".local/share/applications"]
    for directory in directories:
        if not directory.is_dir():
            continue
        for entry in directory.glob("*.desktop"):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(entry, encoding="utf-8")
                section = parser["Desktop Entry"]
                if section.get("NoDisplay", "false").lower() == "true":
                    continue
                name = section.get("Name", entry.stem)
                if query and query.casefold() not in name.casefold():
                    continue
                results.append({"id": entry.stem, "name": name})
            except (OSError, configparser.Error, KeyError):
                continue
    unique = {item["id"]: item for item in results}
    return {"applications": sorted(unique.values(), key=lambda x: x["name"].casefold())[:limit]}


@router.post("/applications/launch", operation_id="launch_multiple_applications")
def launch_applications(request: LaunchAppsRequest):
    launched = []
    for app_id in request.applications:
        if not app_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in app_id):
            raise HTTPException(400, f"Invalid application id: {app_id}")
        launcher = shutil.which("gtk-launch")
        desktop_file = next((directory / f"{app_id}.desktop" for directory in (HOME / ".local/share/applications", Path("/usr/share/applications")) if (directory / f"{app_id}.desktop").is_file()), None)
        if launcher:
            command = [launcher, app_id]
        elif shutil.which("gio") and desktop_file:
            command = [shutil.which("gio"), "launch", str(desktop_file)]
        else:
            raise HTTPException(404, "No compatible desktop application launcher is installed")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=graphical_environment(),
        )
        launched.append({"application": app_id, "process_id": process.pid})
    return {"success": True, "launched": launched}


@router.post("/open", operation_id="open_file_folder_or_url")
def open_target(request: OpenTargetRequest):
    parsed = urlparse(request.target)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(400, "Only HTTP and HTTPS URLs are allowed")
        target = request.target
    else:
        target = str(writable_path(request.target))
    launcher = shutil.which("xdg-open") or shutil.which("gio")
    if not launcher:
        raise HTTPException(404, "xdg-open/gio is not installed")
    command = [launcher, target] if Path(launcher).name == "xdg-open" else [launcher, "open", target]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=graphical_environment(),
    )
    return {"success": True, "target": target, "process_id": process.pid}


@router.post("/files/write", operation_id="write_text_file")
def write_text(request: WriteTextRequest):
    target = writable_path(request.path, may_not_exist=True)
    if target.exists() and not request.overwrite:
        raise HTTPException(409, "File already exists; overwrite was not approved")
    if target.exists() and not target.is_file():
        raise HTTPException(400, "Target is not a regular file")
    if request.create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.is_dir():
        raise HTTPException(400, "Parent folder does not exist")
    temporary = target.with_name(f".{target.name}.hermes-{os.getpid()}.tmp")
    try:
        temporary.write_text(request.content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"success": True, "path": str(target), "bytes": target.stat().st_size}


@router.post("/files/append", operation_id="append_text_file")
def append_text(request: AppendTextRequest):
    target = writable_path(request.path, may_not_exist=True)
    if request.create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_file():
        raise HTTPException(400, "Target is not a regular file")
    with target.open("a", encoding="utf-8") as stream:
        stream.write(request.content)
    return {"success": True, "path": str(target), "bytes": target.stat().st_size}


@router.post("/files/folder", operation_id="create_folder")
def create_folder(request: PathRequest):
    target = writable_path(request.path, may_not_exist=True)
    target.mkdir(parents=True, exist_ok=True)
    return {"success": True, "path": str(target)}


@router.post("/files/copy", operation_id="copy_file_or_folder")
def copy_path(request: TwoPathRequest):
    source = writable_path(request.source)
    destination = writable_path(request.destination, may_not_exist=True)
    if destination.exists() and not request.overwrite:
        raise HTTPException(409, "Destination already exists; overwrite was not approved")
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=request.overwrite)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return {"success": True, "source": str(source), "destination": str(destination)}


@router.post("/files/move", operation_id="move_file_or_folder")
def move_path(request: TwoPathRequest):
    source = writable_path(request.source)
    destination = writable_path(request.destination, may_not_exist=True)
    if destination.exists() and not request.overwrite:
        raise HTTPException(409, "Destination already exists; overwrite was not approved")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and request.overwrite:
        subprocess.run(["gio", "trash", str(destination)], check=True, timeout=10)
    shutil.move(str(source), str(destination))
    return {"success": True, "source": str(source), "destination": str(destination)}


@router.post("/files/trash", operation_id="move_file_or_folder_to_trash")
def trash_path(request: PathRequest):
    target = writable_path(request.path)
    subprocess.run(["gio", "trash", str(target)], check=True, timeout=15)
    return {"success": True, "trashed": str(target), "recoverable": True}


@router.post("/terminal/run", operation_id="run_development_command")
def run_terminal(request: TerminalRequest):
    cwd = writable_path(request.cwd)
    if not cwd.is_dir():
        raise HTTPException(400, "Working directory is not a folder")
    program_name = Path(request.program).name
    if program_name not in ALLOWED_COMMANDS:
        raise HTTPException(403, "Program is not in the Hermes development allowlist")
    if program_name in {"bash", "python", "python3", "node"} and any(arg in BLOCKED_ARGUMENTS for arg in request.arguments):
        raise HTTPException(403, "Inline code execution is disabled; create a source file first")
    executable = shutil.which(request.program)
    if not executable:
        raise HTTPException(404, f"Program is not installed: {request.program}")
    command = [executable, *request.arguments]
    sandboxed = [
        "bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
        "--tmpfs", "/tmp", "--bind", str(cwd), str(cwd), "--chdir", str(cwd),
        "--unshare-all", "--share-net", "--die-with-parent", *command,
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(
            sandboxed,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
            env={
                **os.environ,
                "HOME": str(cwd),
                "XDG_CACHE_HOME": "/tmp/.cache",
                "npm_config_cache": "/tmp/.npm",
                "NO_COLOR": "1",
                "CI": "1",
            },
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "timed_out": True,
            "command": [request.program, *request.arguments],
            "cwd": str(cwd),
            "stdout": (exc.stdout or "")[-MAX_COMMAND_OUTPUT:],
            "stderr": (exc.stderr or "")[-MAX_COMMAND_OUTPUT:],
        }
    response = command_result(result, [request.program, *request.arguments], cwd)
    response["elapsed_seconds"] = round(time.monotonic() - started, 3)
    response["sandboxed"] = True
    return response


@router.get("/system/status", operation_id="get_computer_status")
def system_status():
    disk = shutil.disk_usage(HOME)
    uptime = Path("/proc/uptime").read_text().split()[0]
    return {
        "hostname": os.uname().nodename,
        "system": os.uname().sysname,
        "release": os.uname().release,
        "uptime_seconds": int(float(uptime)),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "writable_roots": [str(path) for path in WRITE_ROOTS],
        "platform": platform_status(),
    }


@router.get("/system/processes", operation_id="list_running_processes")
def running_processes(query: str = "", limit: int = 100):
    result = subprocess.run(
        ["ps", "-eo", "pid,pcpu,pmem,etime,comm,args", "--sort=-pcpu"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    lines = result.stdout.splitlines()
    if query:
        lines = [lines[0], *(line for line in lines[1:] if query.casefold() in line.casefold())]
    return {"processes": lines[: max(2, min(limit + 1, 201))]}


@router.post("/notify", operation_id="show_desktop_notification")
def notify(title: str, message: str):
    executable = shutil.which("notify-send")
    if not executable:
        raise HTTPException(404, "Desktop notifications are not installed")
    subprocess.run([executable, title[:100], message[:500]], check=True, timeout=5, env=graphical_environment())
    return {"success": True}


@router.post("/windows/close", operation_id="close_desktop_window")
def close_window(request: CloseWindowRequest):
    before = _x11_run(["wmctrl", "-lx"], capture_output=True, text=True, check=True, timeout=5).stdout
    if request.window_id.casefold() not in before.casefold():
        raise HTTPException(404, "Window ID was not found")
    _x11_run(["wmctrl", "-ic", request.window_id], check=True, timeout=5)
    return {"success": True, "window_id": request.window_id, "close_requested": True}


@router.post("/keyboard/sequence", operation_id="send_key_sequence_to_application")
def key_sequence(request: KeySequenceRequest):
    for key in request.keys:
        if not re.fullmatch(r"[A-Za-z0-9_+.-]+", key):
            raise HTTPException(400, f"Invalid key combination: {key}")
    controller = PROJECT_ROOT / "desktop.py"
    sent = []
    for key in request.keys:
        result = subprocess.run(
            [os.sys.executable, str(controller), "key-to-class", request.class_name, key],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode:
            raise HTTPException(400, result.stderr.strip() or result.stdout.strip() or "Key action failed")
        sent.append(key)
    return {"success": True, "class_name": request.class_name, "keys_sent": sent}


@router.post("/mouse/drag", operation_id="drag_mouse")
def drag_mouse(request: MouseDragRequest):
    width, height = map(int, _x11_run(
        ["xdotool", "getdisplaygeometry"], capture_output=True, text=True, check=True, timeout=5
    ).stdout.split())
    for x, y in ((request.start_x, request.start_y), (request.end_x, request.end_y)):
        if not (0 <= x < width and 0 <= y < height):
            raise HTTPException(400, f"Coordinates ({x}, {y}) are outside the {width}x{height} screen")
    _x11_run(["xdotool", "mousemove", "--sync", str(request.start_x), str(request.start_y)], check=True, timeout=5)
    _x11_run(["xdotool", "mousedown", str(request.button)], check=True, timeout=5)
    try:
        _x11_run(
            ["xdotool", "mousemove", "--sync", str(request.end_x), str(request.end_y)],
            check=True, timeout=5,
        )
    finally:
        _x11_run(["xdotool", "mouseup", str(request.button)], check=False, timeout=5)
    return {"success": True, "from": [request.start_x, request.start_y], "to": [request.end_x, request.end_y]}


@router.post("/windows/layout", operation_id="manage_desktop_window")
def manage_window(request: WindowLayoutRequest):
    windows = _x11_run(["wmctrl", "-lx"], capture_output=True, text=True, check=True, timeout=5).stdout
    if request.window_id.casefold() not in windows.casefold():
        raise HTTPException(404, "Window ID was not found")
    if request.action == "maximize":
        command = ["wmctrl", "-ir", request.window_id, "-b", "add,maximized_vert,maximized_horz"]
    elif request.action == "restore":
        command = ["wmctrl", "-ir", request.window_id, "-b", "remove,maximized_vert,maximized_horz,hidden"]
    elif request.action == "minimize":
        command = ["xdotool", "windowminimize", str(int(request.window_id, 16))]
    else:
        if None in {request.x, request.y, request.width, request.height}:
            raise HTTPException(400, "move_resize requires x, y, width, and height")
        command = ["wmctrl", "-ir", request.window_id, "-e", f"0,{request.x},{request.y},{request.width},{request.height}"]
    _x11_run(command, check=True, timeout=5)
    return {"success": True, "window_id": request.window_id, "action": request.action}


@router.post("/windows/type", operation_id="type_into_exact_window")
def type_into_exact_window(request: TypeWindowRequest):
    decimal_id = str(int(request.window_id, 16))
    _x11_run(["xdotool", "windowactivate", decimal_id], check=True, timeout=5)
    if request.replace_selection:
        _x11_run(["xdotool", "key", "--clearmodifiers", "ctrl+a"], check=True, timeout=5)
    lines = request.text.split("\n")
    for index, line in enumerate(lines):
        if line:
            _x11_run(["xdotool", "type", "--clearmodifiers", "--delay", "1", "--", line], check=True, timeout=20)
        if index < len(lines) - 1:
            _x11_run(["xdotool", "key", "--clearmodifiers", "Return"], check=True, timeout=5)
    return {"success": True, "window_id": request.window_id, "characters_typed": len(request.text)}

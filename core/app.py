#!/usr/bin/env python3
"""Hermes 2.0 beta local computer and persistent personal-agent bridge."""

import os
import json
import secrets
import platform_commands as subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from computer_control import router as computer_router
from codebase_control import router as codebase_router
from browser_control import router as browser_router
from task_control import router as task_router, start_task_worker, stop_task_worker
from maintenance_control import router as maintenance_router
from memory_control import router as memory_router
from planning_control import router as planning_router
from governance_control import action_permitted, router as governance_router
from graphical_control import router as graphical_router
from agent_control import router as agent_router, start_agent_worker, stop_agent_worker
from model_runtime import configure_vision, public_status
from platform_support import PROJECT_ROOT, platform_status

BASE = PROJECT_ROOT
DESKTOP = BASE / "desktop.py"
MAX_READ_BYTES = 1_000_000

@asynccontextmanager
async def lifespan(_app):
    start_task_worker()
    start_agent_worker()
    try:
        yield
    finally:
        stop_agent_worker()
        stop_task_worker()


app = FastAPI(
    title="Hermes Personal Agent Bridge",
    description="Authenticated Hermes goals, missions, routines, desktop, browser, coding, memory, planning, and safety tools.",
    version="2.0.6",
    lifespan=lifespan,
)
app.include_router(computer_router)
app.include_router(codebase_router)
app.include_router(browser_router)
app.include_router(task_router)
app.include_router(maintenance_router)
app.include_router(memory_router)
app.include_router(planning_router)
app.include_router(governance_router)
app.include_router(graphical_router)
app.include_router(agent_router)
AUDIT_LOG = BASE / "logs" / "actions.jsonl"
AUDIT_MAX_BYTES = 5_000_000
AUDIT_RETAIN = 5
AUDIT_LOCK = threading.Lock()


def write_audit(method: str, path: str, status: int, request_id: str = "", duration_ms: int = 0):
    """Write metadata-only audit events and cap storage with five rotations."""
    with AUDIT_LOCK:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        if AUDIT_LOG.is_file() and AUDIT_LOG.stat().st_size >= AUDIT_MAX_BYTES:
            for index in range(AUDIT_RETAIN - 1, 0, -1):
                source = AUDIT_LOG.with_name(f"{AUDIT_LOG.name}.{index}")
                destination = AUDIT_LOG.with_name(f"{AUDIT_LOG.name}.{index + 1}")
                if source.exists():
                    os.replace(source, destination)
            os.replace(AUDIT_LOG, AUDIT_LOG.with_name(f"{AUDIT_LOG.name}.1"))
        with AUDIT_LOG.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "time": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
            }) + "\n")
        os.chmod(AUDIT_LOG, 0o600)


def secure_response(response, request_id: str):
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def authenticate_and_log(request, call_next):
    started = time.monotonic()
    request_id = secrets.token_hex(8)
    public_paths = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    if request.url.path not in public_paths:
        expected = os.environ.get("HERMES_TOOL_TOKEN", "")
        supplied = request.headers.get("Authorization", "")
        if not expected or not supplied.startswith("Bearer ") or not secrets.compare_digest(
            supplied.removeprefix("Bearer ").strip(), expected
        ):
            write_audit(request.method, request.url.path, 401, request_id, int((time.monotonic() - started) * 1000))
            return secure_response(JSONResponse({"detail": "Valid Hermes bearer token required"}, status_code=401), request_id)
        permitted, mode = action_permitted(request.method, request.url.path)
        if not permitted:
            write_audit(request.method, request.url.path, 423, request_id, int((time.monotonic() - started) * 1000))
            return secure_response(JSONResponse({"detail": f"Hermes safety mode '{mode}' blocks this action"}, status_code=423), request_id)
    try:
        response = await call_next(request)
    except Exception:
        if request.url.path not in public_paths:
            write_audit(request.method, request.url.path, 500, request_id, int((time.monotonic() - started) * 1000))
        raise
    if request.url.path not in public_paths:
        write_audit(request.method, request.url.path, response.status_code, request_id, int((time.monotonic() - started) * 1000))
    return secure_response(response, request_id)


class FocusRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class FocusClassRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=200)


def get_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def desktop_command(*args: str) -> str:
    if not DESKTOP.is_file():
        raise HTTPException(500, "desktop.py was not found")
    try:
        result = subprocess.run(
            [sys.executable, str(DESKTOP), *args],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Desktop action timed out")

    if result.returncode:
        raise HTTPException(
            400, (result.stderr or result.stdout or "Desktop action failed").strip()
        )
    return result.stdout.strip()


@app.get("/health", operation_id="health_check")
def health():
    return {
        "status": "ok",
        "service": "Hermes Personal Agent Bridge",
        "version": "2.0.6",
        "platform": platform_status(),
    }


@app.get("/platform/status", operation_id="get_platform_compatibility")
def get_platform_compatibility():
    return platform_status()


@app.get("/desktop/windows", operation_id="list_desktop_windows")
def windows():
    output = desktop_command("windows")
    return {"windows": output.splitlines() if output else []}


@app.post("/desktop/focus", operation_id="focus_desktop_window")
def focus(request: FocusRequest):
    return {"result": desktop_command("focus", request.title)}


@app.post("/desktop/focus-class", operation_id="focus_window_by_class")
def focus_class(request: FocusClassRequest):
    return {"result": desktop_command("focus-class", request.class_name)}



# Hermes V4 Phase 2: application and keyboard automation

ALLOWED_APPLICATIONS = {
    "xed",
    "nemo",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "firefox",
    "gnome-calculator",
    "gnome-terminal",
    "xfce4-terminal",
    "lxterminal",
    "mousepad",
    "thunar",
    "pcmanfm",
    "code",
    "libreoffice",
}

ALLOWED_SHORTCUTS = {
    "ctrl+a",
    "ctrl+c",
    "ctrl+v",
    "ctrl+s",
    "ctrl+z",
    "ctrl+shift+z",
    "ctrl+f",
    "Return",
    "Tab",
    "Escape",
}


class LaunchRequest(BaseModel):
    application: str = Field(min_length=1, max_length=100)


class TypeToClassRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=3000)


class ShortcutRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=200)
    shortcut: str = Field(min_length=1, max_length=100)


@app.post("/desktop/launch", operation_id="launch_desktop_application")
def launch_application(request: LaunchRequest):
    if request.application not in ALLOWED_APPLICATIONS:
        raise HTTPException(
            400,
            "Application not permitted. Allowed: "
            + ", ".join(sorted(ALLOWED_APPLICATIONS)),
        )
    return {
        "result": desktop_command("launch", request.application)
    }


@app.post("/desktop/type-to-class", operation_id="type_into_application")
def type_into_application(request: TypeToClassRequest):
    return {
        "result": desktop_command(
            "type-to-class", request.class_name, request.text
        )
    }


@app.post("/desktop/shortcut", operation_id="send_application_shortcut")
def send_application_shortcut(request: ShortcutRequest):
    if request.shortcut not in ALLOWED_SHORTCUTS:
        raise HTTPException(400, "Shortcut not permitted")

    return {
        "result": desktop_command(
            "key-to-class", request.class_name, request.shortcut
        )
    }



# =========================================================
# Hermes V4 Phase 3 — Mouse Automation
# =========================================================

class MouseMoveRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class MouseClickRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    button: int = Field(default=1, ge=1, le=3)
    clicks: int = Field(default=1, ge=1, le=2)


class MouseScrollRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    direction: str = Field(pattern="^(up|down)$")
    steps: int = Field(default=3, ge=1, le=10)


@app.get("/desktop/mouse/position", operation_id="get_mouse_position")
def mouse_position():
    return {
        "result": desktop_command("mouse-position")
    }


@app.post("/desktop/mouse/move", operation_id="move_mouse")
def mouse_move(request: MouseMoveRequest):
    return {
        "result": desktop_command(
            "mouse-move",
            str(request.x),
            str(request.y),
        )
    }


@app.post("/desktop/mouse/click", operation_id="click_mouse")
def mouse_click(request: MouseClickRequest):
    return {
        "result": desktop_command(
            "mouse-click",
            str(request.x),
            str(request.y),
            str(request.button),
            str(request.clicks),
        )
    }


@app.post("/desktop/mouse/scroll", operation_id="scroll_mouse")
def mouse_scroll(request: MouseScrollRequest):
    return {
        "result": desktop_command(
            "mouse-scroll",
            str(request.x),
            str(request.y),
            request.direction,
            str(request.steps),
        )
    }



# =========================================================
# Hermes V4 Phase 4 — Screenshot Capture
# =========================================================

@app.post(
    "/desktop/screenshot",
    operation_id="capture_desktop_screenshot",
)
def capture_desktop_screenshot():
    import json
    import platform_commands as subprocess
    import sys
    from pathlib import Path
    from fastapi import HTTPException

    script = Path(__file__).resolve().parent / "screenshot.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script), "capture"],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Screenshot capture timed out",
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stderr.strip() or result.stdout.strip(),
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid screenshot controller response",
        )



# =========================================================
# Hermes V4 Phase 4 — Local Vision Analysis
# =========================================================

class VisionRequest(BaseModel):
    question: str = Field(
        default="Describe what is currently visible on the desktop.",
        max_length=500,
    )
    provider: str = Field(default="", max_length=64, pattern=r"^[a-z0-9_-]*$")
    model: str = Field(default="", max_length=200, pattern=r"^[A-Za-z0-9._:/@+-]*$")


class VisionConfigRequest(BaseModel):
    provider: str = Field(max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    model: str = Field(max_length=200, pattern=r"^[A-Za-z0-9._:/@+-]+$")
    base_url: str = Field(default="", max_length=1000)
    enabled: bool | None = None
    confirmed: bool = False


@app.post(
    "/desktop/vision/analyze",
    operation_id="analyze_desktop_screen",
)
def analyze_desktop_screen(request: VisionRequest):
    import json
    import platform_commands as subprocess
    import sys
    from pathlib import Path
    from fastapi import HTTPException

    script = Path(__file__).resolve().parent / "vision.py"

    try:
        command = [sys.executable, str(script)]
        if request.provider:
            command.extend(["--provider", request.provider])
        if request.model:
            command.extend(["--model", request.model])
        command.append(request.question)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=210,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Vision analysis timed out",
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stdout.strip() or result.stderr.strip(),
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid vision controller response",
        )


@app.get("/models/runtime", operation_id="get_model_runtime_status")
def get_model_runtime_status():
    return public_status()


@app.post("/models/vision", operation_id="configure_vision_model")
def configure_vision_model(request: VisionConfigRequest):
    try:
        return configure_vision(
            request.provider,
            request.model,
            base_url=request.base_url,
            enabled=request.enabled,
            confirmed=request.confirmed,
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/files/list", operation_id="list_directory")
def list_directory(path: str = Query(default="~", min_length=1, max_length=2000)):
    target = get_path(path)
    if not target.is_dir():
        raise HTTPException(400, "Path is not a directory")
    try:
        items = sorted(
            target.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.casefold()),
        )
        return {
            "path": str(target),
            "items": [
                {
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                }
                for item in items
            ],
        }
    except PermissionError:
        raise HTTPException(403, "Permission denied")


@app.get("/files/search", operation_id="search_file_names")
def search_files(
    root: str = Query(min_length=1, max_length=2000),
    query: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=50, ge=1, le=200),
):
    start = get_path(root)
    if not start.is_dir():
        raise HTTPException(400, "Search root is not a directory")

    matches = []
    skipped = 0

    def on_error(_error):
        nonlocal skipped
        skipped += 1

    for current, dirs, files in os.walk(
        start, onerror=on_error, followlinks=False
    ):
        dirs[:] = [
            name for name in dirs
            if not (Path(current) / name).is_symlink()
        ]
        for name in dirs + files:
            if query.casefold() in name.casefold():
                matches.append(str(Path(current) / name))
                if len(matches) >= limit:
                    return {
                        "matches": matches,
                        "limit_reached": True,
                        "inaccessible_locations_skipped": skipped,
                    }

    return {
        "matches": matches,
        "limit_reached": False,
        "inaccessible_locations_skipped": skipped,
    }


@app.get("/files/read", operation_id="read_text_file")
def read_file(path: str = Query(min_length=1, max_length=2000)):
    target = get_path(path)
    if not target.is_file():
        raise HTTPException(400, "Path is not a regular file")

    try:
        size = target.stat().st_size
        if size > MAX_READ_BYTES:
            raise HTTPException(413, "File exceeds the 1 MB read limit")
        content = target.read_text(encoding="utf-8")
        return {"path": str(target), "content": content, "bytes": size}
    except UnicodeDecodeError:
        raise HTTPException(415, "File is not UTF-8 text")
    except PermissionError:
        raise HTTPException(403, "Permission denied")


# ============================================================
# HERMES V4.5 — AUTOMATION CONTROLLER
# ============================================================

from pydantic import BaseModel as AutomationBaseModel
from fastapi import HTTPException as AutomationHTTPException
import platform_commands as automation_subprocess
import sys as automation_sys
from pathlib import Path as AutomationPath


class AutomationLaunchRequest(AutomationBaseModel):
    application: str


@app.post(
    "/automation/launch-verify",
    operation_id="automation_launch_and_verify",
)
def automation_launch_and_verify(
    request: AutomationLaunchRequest,
):
    """
    Launch an approved application and verify its window.
    """

    script = AutomationPath(__file__).resolve().parent / "automation.py"

    try:
        result = automation_subprocess.run(
            [
                automation_sys.executable,
                str(script),
                "launch",
                request.application,
            ],
            capture_output=True,
            text=True,
            timeout=35,
        )

    except automation_subprocess.TimeoutExpired:
        raise AutomationHTTPException(
            status_code=504,
            detail="Automation controller timed out",
        )

    try:
        data = __import__("json").loads(result.stdout)

    except ValueError:
        raise AutomationHTTPException(
            status_code=500,
            detail={
                "error": "Automation returned invalid JSON",
                "stderr": result.stderr[-1000:],
            },
        )

    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

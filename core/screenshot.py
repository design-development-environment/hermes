#!/usr/bin/env python3

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from platform_support import PROJECT_ROOT, graphical_environment, screenshot_backend, session_type

SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_screen():
    environment = graphical_environment()
    backend = screenshot_backend(environment)
    if not backend:
        raise RuntimeError(
            f"No screenshot backend is installed for the {session_type(environment)} session"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"hermes_{timestamp}_{uuid.uuid4().hex[:8]}.png"
    destination = SCREENSHOT_DIR / filename

    commands = {
        "grim": [backend, str(destination)],
        "gnome-screenshot": [backend, "-f", str(destination)],
        "scrot": [backend, str(destination)],
        "import": [backend, "-window", "root", str(destination)],
    }
    subprocess.run(
        commands[backend],
        check=True,
        timeout=20,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=environment,
    )

    if not destination.is_file():
        raise RuntimeError("Screenshot file was not created")

    if destination.stat().st_size == 0:
        raise RuntimeError("Screenshot file is empty")

    return {
        "success": True,
        "filename": filename,
        "path": str(destination),
        "size_bytes": destination.stat().st_size,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] != "capture":
            raise ValueError("Usage: python screenshot.py capture")

        print(json.dumps(capture_screen()))

    except Exception as exc:
        print(
            json.dumps({
                "success": False,
                "error": str(exc),
            })
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

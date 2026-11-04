#!/usr/bin/env python3

import json
import windows_commands as subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from platform_support import PROJECT_ROOT, graphical_environment, screenshot_backend, session_type

SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_screen():
    from PIL import ImageGrab
    from platform_support import require_x11_automation
    require_x11_automation()
    filename = 'hermes_' + uuid.uuid4().hex + '.png'
    destination = SCREENSHOT_DIR / filename
    ImageGrab.grab().save(destination)
    return {'success': True, 'filename': filename, 'path': str(destination), 'size_bytes':destination.stat().st_size, 'captured_at':datetime.now(timezone.utc).isoformat()}


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

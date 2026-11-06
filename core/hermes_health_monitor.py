#!/usr/bin/env python3
"""Check Hermes endpoints and restart only an unhealthy user service."""

from __future__ import annotations

import platform_commands as subprocess
import time
import urllib.error
import urllib.request


SERVICES = {
    "hermes-action-bridge.service": "http://127.0.0.1:8765/health",
    "hermes-documents.service": "http://127.0.0.1:8766/health",
    "open-webui.service": "http://127.0.0.1:3000/health",
}


def healthy(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Hermes-health/6.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return 200 <= response.status < 400
    except (OSError, urllib.error.URLError):
        return False


def retry_health(url: str, attempts: int, delay: float) -> bool:
    for attempt in range(attempts):
        if healthy(url):
            return True
        if attempt + 1 < attempts:
            time.sleep(delay)
    return False


def main() -> int:
    failed = []
    for service, url in SERVICES.items():
        if retry_health(url, attempts=3, delay=3):
            print(f"healthy: {service}")
            continue

        print(f"restarting unhealthy service: {service}")
        restart = subprocess.run(
            ["systemctl", "--user", "restart", service],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if restart.returncode or not retry_health(url, attempts=18, delay=5):
            failed.append(service)
            detail = (restart.stderr or restart.stdout).strip()
            print(f"recovery failed: {service}: {detail or 'endpoint stayed unavailable'}")
        else:
            print(f"recovered: {service}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

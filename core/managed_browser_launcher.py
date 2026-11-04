#!/usr/bin/env python3
"""Launch the managed Chromium session on amd64/arm64 and GUI/headless Linux."""

from __future__ import annotations

import os
from pathlib import Path

from platform_support import DATA_DIR, find_browser, graphical_environment, platform_status, session_type


def command() -> tuple[list[str], dict[str, str]]:
    browser = find_browser()
    if not browser:
        raise RuntimeError("No Chromium-compatible browser was found")
    profile = DATA_DIR / "managed-browser/profile"
    profile.mkdir(parents=True, exist_ok=True)
    os.chmod(profile.parent, 0o700)
    os.chmod(profile, 0o700)
    environment = graphical_environment()
    current_session = session_type(environment)
    require_graphical = os.environ.get("HERMES_REQUIRE_GRAPHICAL", "").strip().lower() in {"1", "true", "yes"}
    if require_graphical and current_session not in {"x11", "windows", "macos"}:
        raise RuntimeError(
            f"Hermes appliance mode requires an unlocked graphical desktop; detected {current_session}. "
            "Headless browser fallback is disabled."
        )
    status = platform_status()
    renderer_limit = "2" if status.get("memory_bytes", 0) < 3_000_000_000 else "4"
    args = [
        browser,
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=http://127.0.0.1:9222",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-sync",
        "--metrics-recording-only",
        f"--renderer-process-limit={renderer_limit}",
    ]
    if current_session == "headless":
        args.extend(["--headless=new", "--disable-gpu"])
    args.append("about:blank")
    return args, environment


def main() -> int:
    args, environment = command()
    os.execve(args[0], args, environment)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit(f"Managed browser startup failed: {exc}")

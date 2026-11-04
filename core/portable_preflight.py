#!/usr/bin/env python3
"""Read-only compatibility check for a Hermes installation target."""

from __future__ import annotations

import argparse
import json
import shutil

from platform_support import platform_status


def report(headless: bool = False) -> dict:
    status = platform_status()
    errors = []
    warnings = []
    if not status["distribution"]["debian_family"]:
        errors.append("The automated installer supports Debian/Ubuntu-family Linux only")
    if not status["architecture_supported"]:
        errors.append("Only amd64/x86_64 and arm64/aarch64 are supported")
    if not shutil.which("systemctl"):
        errors.append("systemd is required by the supported installer")
    if not shutil.which("python3"):
        errors.append("Python 3 is required")
    if not headless and status["session"] == "headless":
        warnings.append("No graphical session is active; desktop control will remain disabled")
    recommended_memory = 1_500_000_000 if headless else 2_000_000_000
    if status.get("memory_bytes") and status["memory_bytes"] < recommended_memory:
        label = "1.5" if headless else "2"
        warnings.append(f"Low memory: {'headless' if headless else 'desktop'} Hermes is most reliable with at least {label} GB RAM")
    if status.get("storage_free_bytes") and status["storage_free_bytes"] < 8_000_000_000:
        errors.append("At least 8 GB of free storage is required for the standardized runtime")
    if not status["browser"]:
        warnings.append("A Chromium-compatible browser must be installed for managed-browser tools")
    if status["session"] == "wayland":
        warnings.append("Global window/keyboard/mouse control is limited on Wayland; managed browser control still works")
    status["preflight"] = {"compatible": not errors, "errors": errors, "warnings": warnings}
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    result = report(args.headless)
    print(json.dumps(result, indent=2))
    return 0 if result["preflight"]["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

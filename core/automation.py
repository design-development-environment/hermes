#!/usr/bin/env python3
"""
Hermes legacy exact-window automation for supported X11 sessions.

Features:
- Application allowlist
- Existing-window reuse
- Bounded execution deadlines
- Safe launch recovery
- Exact window-ID focus verification
- Window disappearance detection
- Structured failure classifications
- Execution timing
- Backward-compatible JSON output
"""

import json
import os
import platform_commands as subprocess
import sys
import time
from pathlib import Path
from platform_support import graphical_environment, require_x11_automation

BASE_DIR = Path(__file__).resolve().parent
DESKTOP = BASE_DIR / "desktop.py"

ALLOWED_APPLICATIONS = {
    "xed",
    "nemo",
    "google-chrome",
    "firefox",
    "gnome-calculator",
}

APP_WINDOW_CLASSES = {
    "xed": ["xed"],
    "nemo": ["nemo"],
    "google-chrome": ["google-chrome", "chrome"],
    "firefox": ["firefox"],
    "gnome-calculator": ["gnome-calculator"],
}

MAX_EXECUTION_SECONDS = 25
WINDOW_WAIT_SECONDS = 10
FOCUS_ATTEMPTS = 3


class AutomationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def run_command(args, timeout=5):
    if args and args[0] in {"wmctrl", "xdotool"}:
        try:
            require_x11_automation()
        except RuntimeError as exc:
            raise AutomationError("UNSUPPORTED_DESKTOP", str(exc)) from exc
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=graphical_environment(),
        )

    except subprocess.TimeoutExpired as exc:
        raise AutomationError(
            "COMMAND_TIMEOUT",
            f"Command timed out: {args[0]}",
        ) from exc

    except OSError as exc:
        raise AutomationError(
            "COMMAND_ERROR",
            str(exc),
        ) from exc

    if result.returncode != 0:
        raise AutomationError(
            "COMMAND_FAILED",
            result.stderr.strip()
            or result.stdout.strip()
            or f"Command failed: {args[0]}",
        )

    return result.stdout.strip()


def get_windows():
    output = run_command(
        ["wmctrl", "-lx"],
        timeout=3,
    )

    windows = []

    for line in output.splitlines():
        parts = line.split(None, 4)

        if len(parts) >= 4:
            windows.append({
                "id": parts[0],
                "desktop": parts[1],
                "class": parts[2],
                "title": parts[4] if len(parts) > 4 else "",
            })

    return windows


def matching_windows(application):
    expected = APP_WINDOW_CLASSES[application]

    return [
        window
        for window in get_windows()
        if any(
            name in window["class"].lower()
            for name in expected
        )
    ]


def get_active_window_id():
    output = run_command(
        ["xdotool", "getactivewindow"],
        timeout=2,
    )

    return int(output.strip())


def window_exists(window_id):
    expected = int(window_id, 16)

    return any(
        int(window["id"], 16) == expected
        for window in get_windows()
    )


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise AutomationError(
            "EXECUTION_TIMEOUT",
            "Overall automation deadline exceeded",
        )


def wait_for_window(application, deadline, timeout=10):
    end = min(
        deadline,
        time.monotonic() + timeout,
    )

    while time.monotonic() < end:
        windows = matching_windows(application)

        if windows:
            return windows

        time.sleep(
            min(0.3, max(0, end - time.monotonic()))
        )

    check_deadline(deadline)

    return []


def focus_window(window_id, deadline, attempts=3):
    expected = int(window_id, 16)

    for attempt in range(1, attempts + 1):
        check_deadline(deadline)

        if not window_exists(window_id):
            raise AutomationError(
                "WINDOW_DISAPPEARED",
                f"Window disappeared: {window_id}",
            )

        run_command(
            ["wmctrl", "-ia", window_id],
            timeout=min(
                2,
                max(0.1, deadline - time.monotonic()),
            ),
        )

        focus_end = min(
            deadline,
            time.monotonic() + 1.5,
        )

        while time.monotonic() < focus_end:
            try:
                active = get_active_window_id()

                if active == expected:
                    if not window_exists(window_id):
                        raise AutomationError(
                            "WINDOW_DISAPPEARED",
                            "Window disappeared after focus",
                        )

                    return {
                        "success": True,
                        "attempts": attempt,
                        "active_window_id": hex(active),
                    }

            except AutomationError as exc:
                if exc.code == "WINDOW_DISAPPEARED":
                    raise

            except ValueError:
                pass

            time.sleep(0.1)

    raise AutomationError(
        "FOCUS_FAILED",
        f"Could not focus window {window_id}",
    )


def launch_application(application, deadline):
    check_deadline(deadline)

    timeout = min(
        5,
        max(0.1, deadline - time.monotonic()),
    )

    return run_command(
        [
            sys.executable,
            str(DESKTOP),
            "launch",
            application,
        ],
        timeout=timeout,
    )


def launch_and_verify(application):
    started = time.monotonic()
    deadline = started + MAX_EXECUTION_SECONDS

    report = {
        "success": False,
        "application": application,
        "verified": False,
        "window_verified": False,
        "focus_verified": False,
        "launched_new_instance": False,
        "reused_existing_window": False,
        "recovery_attempted": False,
        "action": None,
        "failure_code": None,
        "elapsed_seconds": 0,
        "steps": [],
        "windows": [],
    }

    steps = report["steps"]

    def add_step(name, success=True, **details):
        steps.append({
            "step": name,
            "success": success,
            **details,
        })

    try:
        if application not in ALLOWED_APPLICATIONS:
            raise AutomationError(
                "APPLICATION_NOT_ALLOWED",
                "Application not permitted",
            )

        existing = matching_windows(application)

        add_step(
            "check_existing_windows",
            existing_count=len(existing),
        )

        if existing:
            report["action"] = "reused_existing_window"
            report["reused_existing_window"] = True
            windows = existing

        else:
            report["action"] = "launched_new_instance"

            try:
                launch_result = launch_application(
                    application,
                    deadline,
                )

                report["launched_new_instance"] = True

                add_step(
                    "launch_application",
                    result=launch_result,
                    attempt=1,
                )

            except AutomationError as exc:
                add_step(
                    "launch_application",
                    success=False,
                    attempt=1,
                    error=str(exc),
                    failure_code=exc.code,
                )

                # An uncertain launch outcome must not
                # automatically trigger another launch.
                if exc.code == "COMMAND_TIMEOUT":
                    raise AutomationError(
                        "LAUNCH_OUTCOME_UNKNOWN",
                        "Launch command timed out; "
                        "a process may already be starting",
                    ) from exc

                report["recovery_attempted"] = True

                # Recheck before considering recovery.
                windows = matching_windows(application)

                if not windows:
                    add_step(
                        "retry_launch",
                        attempt=2,
                    )

                    launch_result = launch_application(
                        application,
                        deadline,
                    )

                    report["launched_new_instance"] = True

                    add_step(
                        "launch_application",
                        result=launch_result,
                        attempt=2,
                    )

            windows = wait_for_window(
                application,
                deadline,
                timeout=WINDOW_WAIT_SECONDS,
            )

            if not windows:
                raise AutomationError(
                    "WINDOW_TIMEOUT",
                    "Application launch was requested, "
                    "but no matching window appeared",
                )

        check_deadline(deadline)

        target = windows[0]

        if not window_exists(target["id"]):
            report["recovery_attempted"] = True

            add_step(
                "window_disappeared",
                success=False,
                window_id=target["id"],
            )

            windows = matching_windows(application)

            if not windows:
                raise AutomationError(
                    "WINDOW_DISAPPEARED",
                    "No matching application window remains",
                )

            target = windows[0]

        report["windows"] = windows
        report["window_verified"] = True

        add_step(
            "verify_window",
            window_id=target["id"],
        )

        try:
            focus_result = focus_window(
                target["id"],
                deadline,
                attempts=FOCUS_ATTEMPTS,
            )

        except AutomationError as exc:
            if exc.code not in {
                "WINDOW_DISAPPEARED",
                "FOCUS_FAILED",
            }:
                raise

            report["recovery_attempted"] = True

            add_step(
                "focus_recovery",
                success=False,
                error=str(exc),
                failure_code=exc.code,
            )

            refreshed = matching_windows(application)

            if not refreshed:
                raise

            target = refreshed[0]

            focus_result = focus_window(
                target["id"],
                deadline,
                attempts=2,
            )

            report["windows"] = refreshed

        report["focus_verified"] = focus_result["success"]

        add_step(
            "verify_focus",
            **focus_result,
        )

        # Final verification
        check_deadline(deadline)

        if not window_exists(target["id"]):
            raise AutomationError(
                "WINDOW_DISAPPEARED",
                "Target window disappeared before completion",
            )

        if get_active_window_id() != int(target["id"], 16):
            raise AutomationError(
                "FOCUS_LOST",
                "Target window lost focus before completion",
            )

        report["success"] = True
        report["verified"] = True

        add_step(
            "final_verification",
            window_id=target["id"],
        )

    except AutomationError as exc:
        report["failure_code"] = exc.code
        report["error"] = str(exc)

        add_step(
            "error",
            success=False,
            failure_code=exc.code,
            error=str(exc),
        )

    except Exception as exc:
        report["failure_code"] = "UNEXPECTED_ERROR"
        report["error"] = str(exc)

        add_step(
            "error",
            success=False,
            failure_code="UNEXPECTED_ERROR",
            error=str(exc),
        )

    finally:
        report["elapsed_seconds"] = round(
            time.monotonic() - started,
            3,
        )

    return report


def build_execution_summary(report):
    """Build a compact, machine-readable execution summary."""

    steps = report.get("steps", [])
    windows = report.get("windows", [])

    launch_attempts = sum(
        1
        for step in steps
        if step.get("step") == "launch_application"
    )

    selected_window = None

    for step in reversed(steps):
        if step.get("step") in {
            "final_verification",
            "verify_window",
        } and step.get("window_id"):
            selected_window = next(
                (
                    window
                    for window in windows
                    if int(window["id"], 16)
                    == int(step["window_id"], 16)
                ),
                None,
            )
            break

    return {
        "outcome": (
            "success"
            if report.get("success")
            else "failure"
        ),
        "failure_code": report.get("failure_code"),
        "action": report.get("action"),
        "launch_attempts": launch_attempts,
        "recovery_attempted": report.get(
            "recovery_attempted", False
        ),
        "window_verified": report.get(
            "window_verified", False
        ),
        "focus_verified": report.get(
            "focus_verified", False
        ),
        "selected_window": selected_window,
        "elapsed_seconds": report.get(
            "elapsed_seconds", 0
        ),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "launch":
        print(json.dumps({
            "success": False,
            "error": "Usage: automation.py launch APPLICATION",
        }))
        sys.exit(1)

    result = launch_and_verify(sys.argv[2])

    result["summary"] = build_execution_summary(result)

    print(json.dumps(result, indent=2))

    sys.exit(0 if result["success"] else 1)

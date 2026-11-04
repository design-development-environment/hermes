#!/usr/bin/env python3

import json
import platform_commands as subprocess
import sys
import tempfile
import time
from pathlib import Path

import automation
from platform_support import graphical_environment, require_x11_automation

WORKFLOW_TIMEOUT = 25


def run_command(args, timeout=5):
    if args and args[0] in {"wmctrl", "xdotool"}:
        require_x11_automation()
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        env=graphical_environment(),
    )


def verified_text_input(text):
    started = time.monotonic()

    report = {
        "success": False,
        "workflow": "verified_text_input",
        "application": "xed",
        "window_verified": False,
        "focus_verified": False,
        "input_sent": False,
        "content_verified": False,
        "verification_method": "saved_file_readback",
        "elapsed_seconds": 0,
        "steps": [],
    }

    temp_dir = tempfile.TemporaryDirectory(
        prefix="hermes-v471-"
    )

    owned_window_id = None
    document_saved = False

    report["cleanup"] = {
        "attempted": False,
        "window_closed": False,
        "temporary_files_removed": False,
    }

    try:
        file_path = Path(temp_dir.name) / "verification.txt"
        file_path.write_text("", encoding="utf-8")

        report["steps"].append({
            "step": "create_test_file",
            "success": True,
        })

        # Refuse to interact with existing Xed windows.
        existing = automation.matching_windows("xed")

        if existing:
            raise RuntimeError(
                "Xed is already open. Close Xed before this test "
                "to avoid modifying existing documents."
            )

        # Open the temporary file in a new Xed window.
        process = subprocess.Popen(
            ["xed", "--new-window", str(file_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=graphical_environment(),
        )

        deadline = started + WORKFLOW_TIMEOUT

        windows = automation.wait_for_window(
            "xed",
            deadline,
            timeout=10,
        )

        if not windows:
            raise RuntimeError("Xed window not detected")

        target = windows[0]
        owned_window_id = target["id"]
        report["window_verified"] = True

        report["steps"].append({
            "step": "verify_window",
            "success": True,
            "window_id": target["id"],
        })

        focus = automation.focus_window(
            target["id"],
            deadline,
        )

        report["focus_verified"] = focus["success"]

        report["steps"].append({
            "step": "verify_focus",
            **focus,
        })

        # Send the text using the existing desktop controller.
        run_command(
            [sys.executable, "desktop.py", "type", text],
            timeout=8,
        )

        report["input_sent"] = True

        report["steps"].append({
            "step": "type_text",
            "success": True,
        })

        # Verify focus again before saving.
        if automation.get_active_window_id() != int(
            target["id"], 16
        ):
            raise RuntimeError(
                "Editor lost focus before saving"
            )

        run_command(
            ["xdotool", "key", "--clearmodifiers", "ctrl+s"],
            timeout=3,
        )

        report["steps"].append({
            "step": "save_document",
            "success": True,
        })

        # Wait for the file contents to match.
        verified = False

        while time.monotonic() < deadline:
            actual = file_path.read_text(
                encoding="utf-8"
            )

            # Xed may automatically append one final newline.
            # Accept only that specific normalization.
            normalized_actual = (
                actual[:-1]
                if actual.endswith("\n")
                and not text.endswith("\n")
                else actual
            )

            if normalized_actual == text:
                verified = True
                break

            time.sleep(0.2)

        if not verified:
            raise RuntimeError(
                "Saved file does not match expected text"
            )

        report["content_verified"] = True
        document_saved = True

        report["steps"].append({
            "step": "verify_saved_content",
            "success": True,
            "expected_length": len(text),
            "actual_length": len(actual),
        })

        report["success"] = True

    except Exception as exc:
        report["error"] = str(exc)

        report["steps"].append({
            "step": "error",
            "success": False,
            "error": str(exc),
        })

    finally:
        report["cleanup"]["attempted"] = True

        # Close only the window identified during this workflow.
        if owned_window_id is not None:
            try:
                if automation.window_exists(owned_window_id):
                    run_command(
                        ["wmctrl", "-ic", owned_window_id],
                        timeout=3,
                    )

                    # Allow Xed time to close normally.
                    close_deadline = time.monotonic() + 5

                    while time.monotonic() < close_deadline:
                        if not automation.window_exists(
                            owned_window_id
                        ):
                            break

                        time.sleep(0.2)

                report["cleanup"]["window_closed"] = (
                    not automation.window_exists(
                        owned_window_id
                    )
                )

            except Exception as exc:
                report["cleanup"]["error"] = str(exc)

        else:
            # No window was created or identified.
            report["cleanup"]["window_closed"] = True

        # Never delete the temporary file while Xed
        # may still have it open.
        if report["cleanup"]["window_closed"]:
            try:
                temp_dir.cleanup()

                report["cleanup"][
                    "temporary_files_removed"
                ] = True

            except Exception as exc:
                report["cleanup"]["error"] = str(exc)

        else:
            report["cleanup"]["error"] = (
                "Xed window remains open. "
                "Temporary files were preserved."
            )

        report["elapsed_seconds"] = round(
            time.monotonic() - started,
            3,
        )

        if not report["cleanup"]["window_closed"]:
            report["success"] = False
            report["error"] = (
                "Workflow completed but window cleanup failed"
            )

    return report


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "type":
        print("Usage: workflows.py type TEXT")
        sys.exit(1)

    result = verified_text_input(sys.argv[2])

    print(json.dumps(result, indent=2))

    sys.exit(0 if result["success"] else 1)

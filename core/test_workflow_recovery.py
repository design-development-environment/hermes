#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path

import workflow_engine


def forced_verification_failure(*args, **kwargs):
    raise RuntimeError(
        "INTENTIONAL TEST FAILURE: verification rejected"
    )


def get_xed_windows():
    result = subprocess.run(
        ["wmctrl", "-lx"],
        capture_output=True,
        text=True,
        check=True,
        timeout=3,
    )

    return [
        line
        for line in result.stdout.splitlines()
        if len(line.split()) >= 3
        and line.split()[2].lower() == "xed.xed"
    ]


def main():
    before = get_xed_windows()

    original_verification = (
        workflow_engine.wait_for_saved_content
    )

    try:
        workflow_engine.wait_for_saved_content = (
            forced_verification_failure
        )

        report = workflow_engine.create_document_workflow(
            "Hermes V4.7.3 recovery test.\n"
            "This verification must fail intentionally."
        )

    finally:
        workflow_engine.wait_for_saved_content = (
            original_verification
        )

    after = get_xed_windows()

    cleanup = report.get("cleanup", {})

    checks = {
        "workflow_failed_as_expected": (
            report["success"] is False
        ),
        "verification_failure_recorded": any(
            step["step"] == "verify_saved_content"
            and step["success"] is False
            for step in report["steps"]
        ),
        "window_cleanup_verified": (
            cleanup.get("window_closed") is True
            and before == after
        ),
        "temporary_files_removed": (
            cleanup.get("temporary_files_removed") is True
        ),
    }

    result = {
        "test": "hermes_v473_failure_recovery",
        "passed": all(checks.values()),
        "checks": checks,
        "workflow_error": report.get("error"),
        "cleanup": cleanup,
    }

    print(json.dumps(result, indent=2))

    raise SystemExit(
        0 if result["passed"] else 1
    )


if __name__ == "__main__":
    main()

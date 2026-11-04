#!/usr/bin/env python3

import json
import platform_commands as subprocess
import tempfile
import time
from pathlib import Path
from platform_support import graphical_environment, require_x11_automation


class WorkflowError(Exception):
    pass


class WorkflowEngine:

    def __init__(self, name):
        self.name = name
        self.steps = []
        self.started = time.monotonic()

    def execute(self, name, operation):
        started = time.monotonic()

        result = {
            "step": name,
            "success": False,
            "elapsed_seconds": 0,
        }

        try:
            output = operation()

            result["success"] = True

            if output is not None:
                result["output"] = output

            return output

        except Exception as error:
            result["error"] = str(error)
            raise WorkflowError(
                f"Step '{name}' failed: {error}"
            ) from error

        finally:
            result["elapsed_seconds"] = round(
                time.monotonic() - started,
                3,
            )

            self.steps.append(result)

    def report(self, success, error=None):

        result = {
            "workflow": self.name,
            "success": success,
            "steps": self.steps,
            "elapsed_seconds": round(
                time.monotonic() - self.started,
                3,
            ),
        }

        if error:
            result["error"] = str(error)

        return result


def run_command(command, timeout=10):

    if command and command[0] in {"wmctrl", "xdotool"}:
        require_x11_automation()

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=graphical_environment(),
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or f"Command failed: {command}"
        )

    return result.stdout.strip()



def type_multiline_text(text):
    """Type multiline text using explicit Enter keypresses."""

    lines = text.split("\n")

    for index, line in enumerate(lines):

        if line:
            run_command(
                [
                    "xdotool",
                    "type",
                    "--clearmodifiers",
                    "--delay",
                    "1",
                    "--",
                    line,
                ],
                timeout=15,
            )

        if index < len(lines) - 1:
            run_command(
                [
                    "xdotool",
                    "key",
                    "--clearmodifiers",
                    "Return",
                ],
                timeout=5,
            )

    return {
        "lines_typed": len(lines),
        "newline_keys_sent": len(lines) - 1,
    }


def verify_file(path, expected):

    path = Path(path)

    if not path.exists():
        raise RuntimeError("File does not exist")

    actual = path.read_text()

    if actual != expected:
        raise RuntimeError(
            "Saved file content does not match expected text"
        )

    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "content_verified": True,
    }




def get_xed_windows():
    """Return top-level Xed windows managed by Cinnamon."""

    output = run_command(["wmctrl", "-lx"], timeout=3)
    windows = {}

    for line in output.splitlines():
        parts = line.split(None, 4)

        if len(parts) >= 5 and parts[2].lower() == "xed.xed":
            windows[str(int(parts[0], 16))] = parts[4]

    return windows


def wait_for_owned_xed(path, previous_windows, timeout=10):
    """Identify a newly opened Xed window for this document."""

    deadline = time.monotonic() + timeout
    document_directory = str(path.parent)
    home = str(Path.home())

    display_directory = (
        "~" + document_directory[len(home):]
        if document_directory.startswith(home + "/")
        else document_directory
    )

    while time.monotonic() < deadline:
        windows = get_xed_windows()

        candidates = [
            window_id
            for window_id, title in windows.items()
            if window_id not in previous_windows
            and (
                document_directory in title
                or display_directory in title
            )
            and path.name in title
        ]

        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) > 1:
            raise RuntimeError(
                "Multiple matching Xed windows detected"
            )

        time.sleep(0.1)

    raise RuntimeError(
        "Workflow-owned Xed window not found"
    )


def focus_owned_xed(window_id):
    """Activate the exact workflow window and verify focus."""

    run_command(
        ["xdotool", "windowactivate", window_id],
        timeout=3,
    )

    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        active = run_command(
            ["xdotool", "getactivewindow"],
            timeout=2,
        )

        if active == window_id:
            return {
                "window_id": window_id,
                "focus_verified": True,
            }

        time.sleep(0.1)

    raise RuntimeError(
        "Workflow-owned window focus verification failed"
    )


def close_owned_xed(window_id):
    """Close only the window identified by this workflow."""

    windows = get_xed_windows()

    if window_id not in windows:
        return {"window_closed": True}

    run_command(
        ["wmctrl", "-ic", hex(int(window_id))],
        timeout=3,
    )

    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        if window_id not in get_xed_windows():
            return {"window_closed": True}

        time.sleep(0.1)

    raise RuntimeError(
        "Workflow-owned Xed window did not close"
    )


def create_document_workflow(text):

    engine = WorkflowEngine(
        "hermes_multistep_document"
    )

    temp_dir = tempfile.TemporaryDirectory(
        prefix="hermes-workflow-"
    )

    path = Path(temp_dir.name) / "document.txt"
    owned_window_id = None
    error = None

    cleanup = {
        "attempted": False,
        "window_closed": False,
        "temporary_files_removed": False,
    }

    try:
        previous_windows = get_xed_windows()

        engine.execute(
            "create_document",
            lambda: path.write_text(""),
        )

        engine.execute(
            "launch_xed",
            lambda: launch_xed(path),
        )

        owned_window_id = engine.execute(
            "wait_for_owned_xed",
            lambda: wait_for_owned_xed(
                path,
                previous_windows,
            ),
        )

        engine.execute(
            "focus_owned_xed",
            lambda: focus_owned_xed(
                owned_window_id,
            ),
        )

        engine.execute(
            "type_text",
            lambda: type_multiline_text(text),
        )

        engine.execute(
            "save_document",
            lambda: run_command(
                [
                    "xdotool",
                    "key",
                    "--clearmodifiers",
                    "ctrl+s",
                ],
            ),
        )

        engine.execute(
            "verify_saved_content",
            lambda: wait_for_saved_content(
                path,
                text,
            ),
        )

    except Exception as exc:
        error = str(exc)

    finally:
        cleanup["attempted"] = True

        try:
            if owned_window_id is not None:
                result = close_owned_xed(
                    owned_window_id,
                )

                cleanup["window_closed"] = result[
                    "window_closed"
                ]

            else:
                cleanup["window_closed"] = True

        except Exception as exc:
            cleanup["error"] = str(exc)

        if cleanup["window_closed"]:
            try:
                temp_dir.cleanup()

                cleanup[
                    "temporary_files_removed"
                ] = True

            except Exception as exc:
                cleanup["error"] = str(exc)

        else:
            cleanup["error"] = (
                "Window remains open. "
                "Temporary files preserved."
            )

    success = (
        error is None
        and cleanup["window_closed"]
        and cleanup["temporary_files_removed"]
    )

    report = engine.report(
        success,
        error,
    )

    report["cleanup"] = cleanup

    if not success and "error" not in report:
        report["error"] = cleanup.get(
            "error",
            "Workflow cleanup failed",
        )

    return report



def launch_xed(path):
    """Launch Xed without waiting for the GUI process to exit."""

    process = subprocess.Popen(
        ["xed", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=graphical_environment(),
    )

    return {
        "launch_requested": True,
        "process_id": process.pid,
        "document": str(path),
    }



def wait_for_xed(timeout=10):
    """Find a top-level Xed window managed by Cinnamon."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        output = run_command(
            ["wmctrl", "-lx"],
            timeout=3,
        )

        for line in output.splitlines():
            parts = line.split(None, 4)

            if len(parts) >= 3 and parts[2].lower() == "xed.xed":
                return str(int(parts[0], 16))

        time.sleep(0.2)

    raise RuntimeError(
        "No top-level Xed window found"
    )


def focus_xed():
    """Activate Xed and independently verify focus."""

    window_id = wait_for_xed()

    run_command([
        "xdotool",
        "windowactivate",
        window_id,
    ], timeout=3)

    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:

        active = run_command([
            "xdotool",
            "getactivewindow",
        ], timeout=2)

        if active == window_id:
            return {
                "window_id": window_id,
                "focus_verified": True,
            }

        time.sleep(0.1)

    raise RuntimeError(
        f"Xed focus verification failed. "
        f"Expected window: {window_id}"
    )


def wait_for_saved_content(path, expected, timeout=5):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if path.exists():

            actual = path.read_text()

            if actual == expected or actual == expected + "\n":
                return {
                    "content_verified": True,
                    "bytes": path.stat().st_size,
                }

        time.sleep(0.1)

    actual = (
        path.read_text()
        if path.exists()
        else None
    )

    raise RuntimeError(
        "Saved content verification failed. "
        f"Expected: {expected!r}; "
        f"Actual: {actual!r}"
    )


def main():

    text = (
        "Hermes V4.7.3 multi-step workflow test.\n"
        "Document created through desktop automation.\n"
        "Launch, focus, type, save, and verification."
    )

    report = create_document_workflow(text)

    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    raise SystemExit(
        0 if report["success"] else 1
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Portable, atomic document creation independent of any desktop editor."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from platform_support import xdg_user_directory


WORKSPACE = xdg_user_directory("DOCUMENTS") / "Hermes"


def validate_filename(filename: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.txt", filename):
        raise ValueError("Invalid filename. Use a simple .txt filename")
    if filename.startswith(".") or ".." in filename:
        raise ValueError("Unsafe filename")
    return filename


def persistent_document_workflow(filename: str, text: str) -> dict:
    path: Path | None = None
    try:
        filename = validate_filename(filename)
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        path = WORKSPACE / filename
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        actual = path.read_text(encoding="utf-8")
        if actual != text:
            raise RuntimeError("Saved file content did not match the requested text")
        return {
            "workflow": "hermes_portable_document",
            "success": True,
            "file": str(path),
            "file_exists": True,
            "bytes": path.stat().st_size,
            "content_verified": True,
            "desktop_required": False,
        }
    except FileExistsError:
        return {"workflow": "hermes_portable_document", "success": False, "error": "File already exists; nothing was overwritten", "file": str(path) if path else ""}
    except Exception as exc:
        return {"workflow": "hermes_portable_document", "success": False, "error": f"{type(exc).__name__}: {exc}", "file": str(path) if path else ""}


def main() -> int:
    report = persistent_document_workflow("hermes-document-test.txt", "Hermes portable document test.\n")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build the standalone Hermes User installer for Windows x64."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT.parent / "VERSION").read_text(encoding="utf-8").strip()
NUMERIC = ".".join(re.match(r"^(\d+)\.(\d+)\.(\d+)", VERSION).groups())


def main() -> None:
    env = os.environ.copy()
    env.update(npm_config_arch="x64", npm_config_platform="win32")
    shutil.rmtree(ROOT / "node_modules", ignore_errors=True)
    subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=ROOT, env=env, check=True)
    subprocess.run(["node", "node_modules/electron/install.js"], cwd=ROOT, env=env, check=True)
    makensis = shutil.which("makensis")
    if not makensis:
        for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
            candidate = Path(base) / "NSIS/makensis.exe"
            if candidate.is_file():
                makensis = str(candidate)
                break
    if not makensis:
        raise SystemExit("NSIS is required")
    define = "/" if os.name == "nt" else "-"
    subprocess.run([
        makensis, "-V2", f"{define}DPRODUCT_VERSION={VERSION}",
        f"{define}DPRODUCT_VERSION_QUAD={NUMERIC}.1", str(ROOT / "windows-user.nsi")
    ], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

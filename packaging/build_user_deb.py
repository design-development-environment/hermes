#!/usr/bin/env python3
"""Build the lightweight Hermes User Debian package."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "client"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def copy(source: Path, destination: Path, mode: int = 0o644) -> None:
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(f"Missing or unsafe package input: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def build(architecture: str, output: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hermes-user-deb-", dir=output.parent) as folder:
        root = Path(folder) / "package"
        copy(CLIENT / "hermes_client.py", root / "opt/hermes-user/hermes_client.py", 0o755)
        copy(CLIENT / "hermes-user", root / "usr/bin/hermes-user", 0o755)
        copy(CLIENT / "hermes-user.desktop", root / "usr/share/applications/hermes-user.desktop")
        copy(ROOT / "packaging/branding/icon-dark.png", root / "usr/share/icons/hicolor/1024x1024/apps/hermes.png")
        control = root / "DEBIAN/control"
        control.parent.mkdir(parents=True)
        control.write_text(f"""Package: hermes-user
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {architecture}
Maintainer: Anshul & Miheer <anshul.pandhare@mitwpu.edu.in>
Depends: python3, python3-tk, xdg-utils, ca-certificates
Description: Hermes User interface
 Lightweight remote interface for a Hermes Host over Tailscale.
""", encoding="utf-8")
        built = Path(folder) / "Hermes-User.deb"
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(root), str(built)], check=True)
        os.replace(built, output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=("amd64", "arm64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.architecture, args.output))

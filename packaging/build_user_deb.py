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
DEB_VERSION = f"{VERSION}+official" if "-" not in VERSION else VERSION


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
        npm_arch = {"amd64": "x64", "arm64": "arm64"}[architecture]
        environment = os.environ.copy()
        environment["npm_config_arch"] = npm_arch
        environment["npm_config_platform"] = "linux"
        shutil.rmtree(CLIENT / "node_modules", ignore_errors=True)
        # npm 11 rejects Electron's legacy npm_config_arch/platform keys as
        # npm settings.  Only Electron's install script needs them.
        subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=CLIENT, check=True)
        subprocess.run(["node", "node_modules/electron/install.js"], cwd=CLIENT, env=environment, check=True)
        runtime = root / "opt/hermes-user/runtime"
        shutil.copytree(CLIENT / "node_modules/electron/dist", runtime)
        for item in [runtime, *runtime.rglob("*")]:
            item.chmod(item.stat().st_mode & 0o755)
        (runtime / "chrome-sandbox").chmod(0o4755)
        shutil.copytree(CLIENT / "desktop", root / "opt/hermes-user/desktop")
        copy(ROOT / "packaging/branding/icon-dark.png", root / "opt/hermes-user/desktop/icon.png")
        for mode in ("dark", "light"):
            copy(ROOT / f"packaging/branding/hermes-{mode}.svg", root / f"opt/hermes-user/desktop/hermes-{mode}.svg")
        copy(CLIENT / "hermes-user", root / "usr/bin/hermes-user", 0o755)
        copy(CLIENT / "hermes-user.desktop", root / "usr/share/applications/hermes-user.desktop")
        # The Host owns "hermes.png". The User must have its own desktop
        # icon path so both Debian packages can be installed together.
        copy(ROOT / "packaging/branding/icon-dark.png", root / "usr/share/icons/hicolor/1024x1024/apps/hermes-user.png")
        control = root / "DEBIAN/control"
        control.parent.mkdir(parents=True)
        control.write_text(f"""Package: hermes-user
Version: {DEB_VERSION}
Section: utils
Priority: optional
Architecture: {architecture}
Maintainer: Anshul & Miheer <anshul.pandhare@mitwpu.edu.in>
Depends: libgtk-3-0, libnss3, libasound2, libgbm1, libxss1, libatk-bridge2.0-0, ca-certificates, fonts-inter
Description: Hermes User interface
 Lightweight remote interface for a Hermes Host over Tailscale.
""", encoding="utf-8")
        built = Path(folder) / "Hermes-User.deb"
        subprocess.run(["dpkg-deb", "-Zzstd", "-z8", "--build", "--root-owner-group", str(root), str(built)], check=True)
        os.replace(built, output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=("amd64", "arm64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.architecture, args.output))

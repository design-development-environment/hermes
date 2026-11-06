#!/usr/bin/env python3
"""Build Hermes User as a native Apple Silicon app, PKG, and DMG."""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
DIST = ROOT.parent
VERSION = (DIST / "VERSION").read_text(encoding="utf-8").strip()
APP = ROOT / "Hermes User.app"
PKG = DIST / "Hermes-user-macOS-Apple-Silicon.pkg"
DMG = DIST / "Hermes-user-macOS-Apple-Silicon.dmg"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def make_icon(resources: Path) -> None:
    iconset = ROOT / "HermesUser.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir()
    image = Image.open(ROOT / "desktop/icon.png").convert("RGBA")
    for size in (16, 32, 128, 256, 512):
        image.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        image.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
    run("iconutil", "--convert", "icns", "--output", str(resources / "Hermes.icns"), str(iconset))
    shutil.rmtree(iconset)


def main() -> None:
    env = os.environ.copy()
    env.update(npm_config_arch="arm64", npm_config_platform="darwin")
    shutil.rmtree(ROOT / "node_modules", ignore_errors=True)
    # Keep Electron's target variables away from npm 11, which warns that they
    # are unknown npm settings.  The Electron downloader consumes them below.
    subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=ROOT, check=True)
    subprocess.run(["node", "node_modules/electron/install.js"], cwd=ROOT, env=env, check=True)
    shutil.rmtree(APP, ignore_errors=True)
    shutil.copytree(ROOT / "node_modules/electron/dist/Electron.app", APP, symlinks=True)
    resources = APP / "Contents/Resources"
    (resources / "default_app.asar").unlink(missing_ok=True)
    shutil.copytree(ROOT / "desktop", resources / "app")
    shutil.copy2(ROOT / "desktop-package.json", resources / "app/package.json")
    make_icon(resources)
    info_path = APP / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    info.update({
        "CFBundleName": "Hermes", "CFBundleDisplayName": "Hermes",
        "CFBundleIdentifier": "com.anshulmiheer.hermes.user",
        "CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
        "CFBundleIconFile": "Hermes.icns",
        "NSMicrophoneUsageDescription": "Hermes uses your microphone only for voice conversations you start.",
        "NSCameraUsageDescription": "Hermes uses your camera only when you attach a live image.",
        "NSHumanReadableCopyright": "Copyright © 2026 Anshul & Miheer. All rights reserved.",
    })
    info_path.write_bytes(plistlib.dumps(info, sort_keys=True))
    identity = os.environ.get("MACOS_APPLICATION_IDENTITY", "-").strip() or "-"
    command = ["codesign", "--force", "--deep", "--sign", identity]
    if identity != "-": command += ["--options", "runtime", "--timestamp"]
    run(*command, str(APP))
    run("codesign", "--verify", "--deep", "--strict", str(APP))
    component = ROOT / "Hermes-user-component.pkg"
    run("pkgbuild", "--component", str(APP), "--install-location", "/Applications",
        "--identifier", "com.anshulmiheer.hermes.user", "--version", VERSION, str(component))
    identity = os.environ.get("MACOS_INSTALLER_IDENTITY", "").strip()
    command = ["productbuild", "--package", str(component)]
    if identity: command += ["--sign", identity, "--timestamp"]
    run(*command, str(PKG))
    component.unlink()
    with tempfile.TemporaryDirectory(prefix="hermes-user-dmg-") as folder:
        stage = Path(folder)
        shutil.copytree(APP, stage / APP.name, symlinks=True)
        (stage / "Applications").symlink_to("/Applications")
        run("hdiutil", "create", "-volname", f"Hermes User {VERSION}", "-srcfolder", str(stage),
            "-format", "UDZO", "-imagekey", "zlib-level=9", str(DMG))


if __name__ == "__main__":
    main()

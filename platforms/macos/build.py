#!/usr/bin/env python3
"""Build Hermes.app plus native Apple Silicon PKG and DMG installers."""

from __future__ import annotations

import ast
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
NUMERIC_VERSION = ".".join((re.match(r"^(\d+)\.(\d+)\.(\d+)", VERSION) or (_ for _ in ()).throw(ValueError(f"Invalid version: {VERSION}"))).groups())
BUNDLE = ROOT / "Hermes.app"
CONTENTS = BUNDLE / "Contents"
RESOURCES = CONTENTS / "Resources"
MACOS = CONTENTS / "MacOS"
PKG = ROOT / f"Hermes-{VERSION}-macOS-Apple-Silicon.pkg"
DMG = ROOT / f"Hermes-{VERSION}-macOS-Apple-Silicon.dmg"


def run(*args: str):
    subprocess.run(list(args), check=True)


def make_icon():
    source = ROOT / "source/branding/icon-dark.png"
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        Image.open(source).save(RESOURCES / "Hermes.icns")
        return
    iconset = ROOT / "Hermes.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir()
    image = Image.open(source).convert("RGBA")
    for size in (16, 32, 128, 256, 512):
        image.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        image.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
    run("iconutil", "--convert", "icns", "--output", str(RESOURCES / "Hermes.icns"), str(iconset))
    shutil.rmtree(iconset)


def build_app():
    shutil.rmtree(BUNDLE, ignore_errors=True)
    MACOS.mkdir(parents=True)
    RESOURCES.mkdir(parents=True)
    for path in (ROOT / "source").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), str(path))
    shutil.copytree(ROOT / "source", RESOURCES / "source", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("bootstrap.command", "python-package.sha256", "README-MACOS.md", "LICENSE"):
        shutil.copy2(ROOT / name, RESOURCES / name)
    shutil.copy2(ROOT / "launcher", MACOS / "Hermes")
    (MACOS / "Hermes").chmod(0o755)
    (RESOURCES / "bootstrap.command").chmod(0o755)
    make_icon()
    info = {
        "CFBundleName": "Hermes",
        "CFBundleDisplayName": "Hermes",
        "CFBundleIdentifier": "com.anshulmiheer.hermes",
        "CFBundleVersion": NUMERIC_VERSION.replace(".", "") + "1",
        "CFBundleShortVersionString": VERSION,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "Hermes",
        "CFBundleIconFile": "Hermes.icns",
        "LSMinimumSystemVersion": "14.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSArchitecturePriority": ["arm64"],
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Hermes controls applications only when you request a desktop action.",
        "NSMicrophoneUsageDescription": "Hermes uses microphone access for voice conversations you start.",
        "NSScreenCaptureUsageDescription": "Hermes captures the screen only when you request visual analysis.",
        "NSHumanReadableCopyright": "Copyright © 2026 Anshul & Miheer. All rights reserved.",
    }
    (CONTENTS / "Info.plist").write_bytes(plistlib.dumps(info, sort_keys=True))
    if sys.platform == "darwin":
        identity = os.environ.get("MACOS_APPLICATION_IDENTITY", "-").strip() or "-"
        args = ["codesign", "--force", "--deep", "--sign", identity]
        if identity != "-":
            args += ["--options", "runtime", "--timestamp"]
        args.append(str(BUNDLE))
        run(*args)
        run("codesign", "--verify", "--deep", "--strict", str(BUNDLE))


def build_installers():
    if sys.platform != "darwin":
        print("Hermes.app assembled; PKG and DMG require a native macOS runner.")
        return
    component = ROOT / "Hermes-component.pkg"
    component.unlink(missing_ok=True)
    PKG.unlink(missing_ok=True)
    DMG.unlink(missing_ok=True)
    run("pkgbuild", "--component", str(BUNDLE), "--install-location", "/Applications",
        "--identifier", "com.anshulmiheer.hermes", "--version", NUMERIC_VERSION, str(component))
    identity = os.environ.get("MACOS_INSTALLER_IDENTITY", "").strip()
    with tempfile.TemporaryDirectory(prefix="hermes-product-") as raw:
        product = Path(raw)
        resources = product / "resources"
        resources.mkdir()
        shutil.copy2(ROOT / "LICENSE", resources / "LICENSE")
        (resources / "welcome.html").write_text(
            "<html><body style='font-family:-apple-system'>"
            "<h1>Hermes</h1><p>Highly Efficient Real-time Machine for Everyday Support.</p>"
            "<p>This installs Hermes for every user in the Applications folder. "
            "Your API keys and personal data are not included.</p></body></html>",
            encoding="utf-8",
        )
        distribution = product / "Distribution.xml"
        distribution.write_text(
            f'''<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>Hermes {VERSION}</title>
  <organization>com.anshulmiheer</organization>
  <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
  <options customize="never" require-scripts="false" hostArchitectures="arm64"/>
  <welcome file="welcome.html"/>
  <license file="LICENSE"/>
  <choices-outline><line choice="hermes"/></choices-outline>
  <choice id="hermes" visible="false"><pkg-ref id="com.anshulmiheer.hermes"/></choice>
  <pkg-ref id="com.anshulmiheer.hermes" version="{NUMERIC_VERSION}" onConclusion="none">Hermes-component.pkg</pkg-ref>
</installer-gui-script>
''',
            encoding="utf-8",
        )
        command = ["productbuild", "--distribution", str(distribution), "--resources", str(resources),
                   "--package-path", str(ROOT)]
        if identity:
            command += ["--sign", identity, "--timestamp"]
        command.append(str(PKG))
        run(*command)
    component.unlink()
    with tempfile.TemporaryDirectory(prefix="hermes-dmg-") as raw:
        staging = Path(raw)
        shutil.copytree(BUNDLE, staging / "Hermes.app", symlinks=True)
        shutil.copy2(PKG, staging / PKG.name)
        (staging / "Applications").symlink_to("/Applications")
        run("hdiutil", "create", "-volname", f"Hermes {VERSION}", "-srcfolder", str(staging),
            "-format", "UDZO", "-imagekey", "zlib-level=9", str(DMG))
    run("hdiutil", "verify", str(DMG))


def checksums():
    outputs = [path for path in (PKG, DMG) if path.is_file()]
    if not outputs:
        outputs = [CONTENTS / "Info.plist"]
    (ROOT / "SHA256SUMS-macos-apple-silicon.txt").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in outputs),
        encoding="utf-8",
    )
    for path in outputs:
        print("Built", path, "bytes:", path.stat().st_size)


if __name__ == "__main__":
    build_app()
    build_installers()
    checksums()

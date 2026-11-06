#!/bin/bash
set -euo pipefail
umask 077
resources="$(cd "$(dirname "$0")" && pwd)"
base="$HOME/Library/Application Support/Hermes"
trap 'printf "\nSetup stopped. Read the error above. Press Return to close.\n"; read -r reply' ERR
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    printf 'Hermes requires an Apple Silicon Mac running natively, without Rosetta.\n'
    exit 1
fi
major="$(sw_vers -productVersion | cut -d. -f1)"
if ((major < 14)); then printf 'macOS 14 or newer is required.\n'; exit 1; fi
python=""
for candidate in /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12; do
    if [[ -x "$candidate" ]] && "$candidate" -c 'import platform,tkinter; assert platform.machine()=="arm64"' >/dev/null 2>&1; then
        python="$candidate"; break
    fi
done
if [[ -z "$python" ]]; then
    printf 'Hermes requires Python 3.12 with Tk. Download the official signed installer? [y/N] '
    read -r answer
    if [[ "$answer" != y && "$answer" != Y ]]; then exit 1; fi
    download="$(mktemp -d -t hermes-python)"
    pkg="$download/python-3.12.10-macos11.pkg"
    /usr/bin/curl --fail --location --retry 2 --proto '=https' --tlsv1.2 \
      -o "$pkg" 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg'
    expected="$(cat "$resources/python-package.sha256")"
    actual="$(/usr/bin/shasum -a 256 "$pkg" | cut -d' ' -f1)"
    if [[ "$expected" != "$actual" ]]; then printf 'Python checksum mismatch.\n'; exit 1; fi
    /usr/sbin/pkgutil --check-signature "$pkg"
    /usr/bin/open -W "$pkg"
    printf 'Finish Python installation, then press Return here.\n'
    read -r answer
    python=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
    "$python" -c 'import tkinter,platform; assert platform.machine()=="arm64"'
    rm -f "$pkg"
    rmdir "$download"
fi
mkdir -p "$base/config" "$base/data"
chmod 700 "$base" "$base/config" "$base/data"
# Use a stable private runtime so LaunchAgents do not depend on a USB or Downloads path.
if [[ ! -x "$base/runtime/bin/python" ]]; then "$python" -m venv "$base/runtime"; fi
# Keep the setup UI dependency identical to the full runtime lock.  This avoids
# replacing a native module while the graphical installer is using it.
"$base/runtime/bin/python" -m pip install --no-cache-dir 'Pillow==13.0.0'
mkdir -p "$base/source"
cp -R "$resources/source/." "$base/source/"
export PYTHONUTF8=1
export PIP_CACHE_DIR="$base/data/cache/pip"
if [[ -x "$base/runtime/bin/open-webui" ]]; then
    "$base/runtime/bin/python" "$base/source/mac_runtime.py" upgrade
    /usr/bin/open 'http://127.0.0.1:3000'
    exit 0
fi
"$base/runtime/bin/python" "$base/source/mac_setup.py"

#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
INSTALL_ROOT="${HOME}/hermes-v4"
HEADLESS=0
PREFLIGHT_ONLY=0
SKIP_OPENWEBUI=0
WITH_TAILSCALE=0

usage() {
  echo "Usage: ./install.sh [--headless] [--preflight] [--skip-openwebui] [--with-tailscale] [--install-dir PATH]"
}

while (($#)); do
  case "$1" in
    --headless) HEADLESS=1 ;;
    --preflight) PREFLIGHT_ONLY=1 ;;
    --skip-openwebui) SKIP_OPENWEBUI=1 ;;
    --with-tailscale) WITH_TAILSCALE=1 ;;
    --install-dir) shift; INSTALL_ROOT="${1:?--install-dir requires a path}" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

INSTALL_ROOT="$(realpath -m -- "$INSTALL_ROOT")"
if [[ "$INSTALL_ROOT" != "$HOME"/* ]]; then
  echo "Hermes must be installed inside the current user's home folder." >&2
  exit 2
fi
if [[ ! "$INSTALL_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  echo "The installation path may contain only letters, numbers, dots, underscores, dashes, and slashes." >&2
  exit 2
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) HERMES_ARCH=amd64 ;;
  aarch64|arm64) HERMES_ARCH=arm64 ;;
  *) echo "Unsupported CPU architecture: $ARCH (supported: amd64, arm64)" >&2; exit 1 ;;
esac

# NumPy 2.3+ wheels use x86-64-v2 instructions. A Core 2 Duo lacks SSE4.2,
# so choose a supported dependency graph with NumPy 2.2.6 on such CPUs.
LEGACY_X86=0
if [[ "$HERMES_ARCH" == "amd64" ]] && ! grep -qw sse4_2 /proc/cpuinfo 2>/dev/null; then
  LEGACY_X86=1
  echo "Legacy x86 CPU detected; using the compatible WebUI runtime."
fi

# shellcheck disable=SC1091
source /etc/os-release
FAMILY=" ${ID:-} ${ID_LIKE:-} "
if [[ "$FAMILY" != *" debian "* && "$FAMILY" != *" ubuntu "* ]]; then
  echo "This installer supports Ubuntu/Debian-family Linux and Raspberry Pi OS." >&2
  exit 1
fi
if ! command -v systemctl >/dev/null || ! command -v python3 >/dev/null; then
  echo "systemd and Python 3 are required." >&2
  exit 1
fi

if ((PREFLIGHT_ONLY)); then
  PYTHONPATH="$SOURCE_ROOT" python3 "$SOURCE_ROOT/portable_preflight.py" $([[ $HEADLESS -eq 1 ]] && echo --headless)
  exit
fi
echo "Hermes target: ${PRETTY_NAME:-Linux} / $HERMES_ARCH / $INSTALL_ROOT"

if ! command -v sudo >/dev/null; then
  echo "sudo is required to install operating-system packages." >&2
  exit 1
fi

run_privileged() {
  if [[ -n "${SUDO_ASKPASS:-}" ]]; then
    sudo -A "$@"
  else
    sudo "$@"
  fi
}

# A broken third-party APT source must not prevent a Hermes install. We never
# weaken signature validation or alter the user's repositories; if refresh
# fails, APT retains its last known trusted package lists and the following
# installation step remains the authoritative success/failure check.
refresh_package_lists() {
  if run_privileged apt-get update; then
    return 0
  fi
  echo "Warning: APT refresh failed, usually because an unrelated third-party repository is misconfigured." >&2
  echo "Hermes will continue using existing trusted package metadata. Fix that repository after setup if a required package is unavailable." >&2
  return 0
}

# Node.js is useful for optional coding workflows, but package names and versions
# differ across supported Debian-family distributions. It must never block the
# Hermes runtime installation.
PACKAGES=(python3 python3-venv python3-pip ca-certificates curl bubblewrap xdg-utils libglib2.0-bin dbus-user-session build-essential git ripgrep jq inxi pciutils usbutils lshw smartmontools lm-sensors ethtool xclip xsel x11-xserver-utils pulseaudio-utils playerctl ffmpeg)
if ((HEADLESS == 0)); then
  PACKAGES+=(libnotify-bin wmctrl xdotool)
fi
refresh_package_lists
run_privileged apt-get install -y "${PACKAGES[@]}"
if ((HEADLESS == 0)); then
  OPTIONAL_DESKTOP_PACKAGES=()
  for package in grim scrot gnome-screenshot pipewire-audio; do
    if apt-cache show "$package" >/dev/null 2>&1; then
      OPTIONAL_DESKTOP_PACKAGES+=("$package")
    fi
  done
  if ((${#OPTIONAL_DESKTOP_PACKAGES[@]})); then
    run_privileged apt-get install -y "${OPTIONAL_DESKTOP_PACKAGES[@]}"
  fi
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x "$HOME/.local/bin/uv" ]]; then
  UV_BIN="$HOME/.local/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  UV_INSTALLER="$(mktemp)"
  trap 'rm -f "${UV_INSTALLER:-}" "${TAILSCALE_INSTALLER:-}"' EXIT
  curl --proto '=https' --tlsv1.2 -fLSs https://astral.sh/uv/install.sh -o "$UV_INSTALLER"
  UV_INSTALL_DIR="$HOME/.local/bin" sh "$UV_INSTALLER"
  UV_BIN="$HOME/.local/bin/uv"
fi
UV_PYTHON_INSTALL_DIR="$HOME/.local/share/hermes/python" "$UV_BIN" python install 3.12

if ! command -v google-chrome >/dev/null && ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null; then
  if apt-cache show chromium >/dev/null 2>&1; then
    run_privileged apt-get install -y chromium
  elif apt-cache show chromium-browser >/dev/null 2>&1; then
    run_privileged apt-get install -y chromium-browser
  else
    echo "Warning: no Chromium package was found; managed-browser tools will remain disabled." >&2
  fi
fi

if ((WITH_TAILSCALE == 1)); then
  if ! command -v tailscale >/dev/null; then
    TAILSCALE_INSTALLER="$(mktemp)"
    trap 'rm -f "${UV_INSTALLER:-}" "${TAILSCALE_INSTALLER:-}"' EXIT
    curl --proto '=https' --tlsv1.2 -fLSs https://tailscale.com/install.sh -o "$TAILSCALE_INSTALLER"
    run_privileged sh "$TAILSCALE_INSTALLER"
  fi
  run_privileged systemctl enable --now tailscaled.service
fi

mkdir -p "$INSTALL_ROOT"
if [[ "$SOURCE_ROOT" != "$INSTALL_ROOT" ]]; then
  tar -C "$SOURCE_ROOT" --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=logs --exclude=screenshots -cf - . | tar -C "$INSTALL_ROOT" -xf -
fi

APP_VENV="$INSTALL_ROOT/.venv"
APP_VENV_NEXT="$INSTALL_ROOT/.venv.next"
APP_VENV_OLD="$INSTALL_ROOT/.venv.previous"
rm -rf -- "$APP_VENV_NEXT" "$APP_VENV_OLD"
UV_NO_CACHE=1 UV_PYTHON_INSTALL_DIR="$HOME/.local/share/hermes/python" "$UV_BIN" venv --relocatable --python 3.12 "$APP_VENV_NEXT"
UV_NO_CACHE=1 "$UV_BIN" pip install --python "$APP_VENV_NEXT/bin/python" -r "$INSTALL_ROOT/requirements-hermes.lock"
"$APP_VENV_NEXT/bin/python" -m py_compile "$INSTALL_ROOT"/*.py
if [[ -d "$APP_VENV" ]]; then
  mv -- "$APP_VENV" "$APP_VENV_OLD"
fi
mv -- "$APP_VENV_NEXT" "$APP_VENV"
rm -rf -- "$APP_VENV_OLD"

mkdir -p "$HOME/.config/hermes" "$HOME/.config/systemd/user" "$HOME/.local/share/hermes/open-webui-data"
chmod 700 "$HOME/.config/hermes" "$HOME/.local/share/hermes"
if [[ ! -s "$HOME/.config/hermes/tool-token" ]]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > "$HOME/.config/hermes/tool-token"
fi
chmod 600 "$HOME/.config/hermes/tool-token"
if ((HEADLESS == 0)); then
  if [[ ! -e "$HOME/.config/hermes/appliance.env" ]]; then
    cp "$INSTALL_ROOT/appliance.env.example" "$HOME/.config/hermes/appliance.env"
  fi
  chmod 600 "$HOME/.config/hermes/appliance.env"
fi

if ((SKIP_OPENWEBUI == 0)); then
  WEBUI_VENV="$HOME/.local/share/hermes/open-webui-venv"
  WEBUI_VENV_NEXT="$HOME/.local/share/hermes/open-webui-venv.next"
  WEBUI_VENV_OLD="$HOME/.local/share/hermes/open-webui-venv.previous"
  if ((LEGACY_X86)); then
    WEBUI_LOCK="$INSTALL_ROOT/requirements-openwebui-core2-amd64.lock"
  else
    WEBUI_LOCK="$INSTALL_ROOT/requirements-openwebui-${HERMES_ARCH}.lock"
  fi
  if [[ ! -s "$WEBUI_LOCK" ]]; then
    echo "Missing architecture lock: $WEBUI_LOCK" >&2
    exit 1
  fi
  rm -rf -- "$WEBUI_VENV_NEXT" "$WEBUI_VENV_OLD"
  UV_NO_CACHE=1 UV_PYTHON_INSTALL_DIR="$HOME/.local/share/hermes/python" "$UV_BIN" venv --relocatable --python 3.12 "$WEBUI_VENV_NEXT"
  UV_NO_CACHE=1 "$UV_BIN" pip install --python "$WEBUI_VENV_NEXT/bin/python" --index-strategy unsafe-best-match -r "$WEBUI_LOCK"
  "$WEBUI_VENV_NEXT/bin/open-webui" --help >/dev/null
  echo 'Checking native libraries on this CPU…'
  "$WEBUI_VENV_NEXT/bin/python" -c 'import numpy, torch, cv2; print("Native runtime imports passed")'
  if [[ -d "$WEBUI_VENV" ]]; then
    mv -- "$WEBUI_VENV" "$WEBUI_VENV_OLD"
  fi
  mv -- "$WEBUI_VENV_NEXT" "$WEBUI_VENV"
  rm -rf -- "$WEBUI_VENV_OLD"
  if [[ ! -e "$HOME/.config/systemd/user/open-webui.service" ]]; then
    cp "$INSTALL_ROOT/open-webui.service.portable" "$HOME/.config/systemd/user/open-webui.service"
  fi
  LEGACY_WEBUI_OVERRIDE="$HOME/.config/systemd/user/open-webui.service.d/network.conf"
  if [[ -f "$LEGACY_WEBUI_OVERRIDE" ]]; then
    sed -i "s|ExecStart=$HOME/.local/bin/open-webui |ExecStart=$WEBUI_VENV/bin/open-webui |" "$LEGACY_WEBUI_OVERRIDE"
  fi
fi

for unit in hermes-action-bridge.service hermes-documents.service hermes-managed-browser.service hermes-backup.service hermes-backup.timer hermes-health-monitor.service hermes-health-monitor.timer; do
  sed "s|%h/hermes-v4|$INSTALL_ROOT|g" "$INSTALL_ROOT/$unit" > "$HOME/.config/systemd/user/$unit"
done

systemctl --user daemon-reload
systemctl --user enable --now hermes-action-bridge.service hermes-documents.service hermes-health-monitor.timer hermes-backup.timer
if ((SKIP_OPENWEBUI == 0)); then
  systemctl --user enable --now open-webui.service
  systemctl --user restart open-webui.service
  echo 'Waiting for Open WebUI to become ready…'
  python3 - <<'PY'
import time, urllib.request
for attempt in range(180):
    try:
        with urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=2) as response:
            if response.status == 200:
                print('Open WebUI is ready.')
                break
    except OSError:
        pass
    time.sleep(2)
else:
    raise SystemExit('Open WebUI failed to start. Check its service log before continuing.')
PY
fi
run_privileged loginctl enable-linger "$USER"

PYTHONPATH="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/python" "$INSTALL_ROOT/portable_preflight.py" $([[ $HEADLESS -eq 1 ]] && echo --headless)
echo
echo "Hermes core is installed. Open http://127.0.0.1:3000 and create the owner account."
echo "Then run: $INSTALL_ROOT/.venv/bin/python $INSTALL_ROOT/bootstrap_openwebui.py"
echo "API keys are entered in Open WebUI and are never embedded in this installer."
if ((WITH_TAILSCALE == 1)); then
  echo "Run 'sudo tailscale up', authenticate, then configure Tailscale Serve for port 3000."
fi

# Hermes portability and installation

Hermes separates its portable core from optional desktop automation. The cloud
model, Open WebUI, files, terminal, coding, web reading, managed Chromium,
documents, memory, planning, backups, and safety layer work on both `amd64` and
`arm64`. Global window, keyboard, and mouse control is enabled only on X11.

## Supported targets

| Target | Core | Managed browser | Screenshot | Global GUI control |
|---|---:|---:|---:|---:|
| Ubuntu/Mint/Debian amd64, X11 | Yes | Yes | Yes | Yes |
| Ubuntu/Mint/Debian amd64, Wayland | Yes | Yes | With portal/backend | Limited |
| Raspberry Pi OS 64-bit ARM64, X11 | Yes | Yes | Yes | Yes |
| Raspberry Pi OS 64-bit ARM64, Wayland/labwc | Yes | Yes | With `grim` | Limited |
| Debian-family headless ARM64/amd64 | Yes | Yes, headless | No desktop | No |

The automated installer intentionally rejects unsupported CPU architectures and
non-Debian-family distributions instead of making an unsafe partial installation.
Arch and Fedora require separate package and service adapters.

## Install

Run a read-only compatibility check first:

```bash
./install.sh --preflight
```

Install the desktop edition:

```bash
./install.sh
```

Install on Raspberry Pi OS Lite or another server without a desktop:

```bash
./install.sh --headless
```

To install and enable Tailscale from its official HTTPS installer as well:

```bash
./install.sh --with-tailscale
```

The installer validates the distribution and CPU, installs APT dependencies,
selects a Chromium variant, provisions an isolated Python 3.12 runtime through
`uv` so distribution Python versions cannot conflict, creates environments and an
owner-only tool token, installs username-independent user services, enables boot
timers, and runs a final compatibility report.

Hermes core dependencies are exactly pinned in `requirements-hermes.lock` for
repeatable installs. Open WebUI's complete transitive graph is pinned in separate
amd64 and arm64 lock files generated from the same two direct requirements.
Environment updates are built and validated beside the live
environment, then swapped into place, so an interrupted download cannot damage a
working installation. The build environments are relocatable, so their launchers
remain valid after the atomic swap. On both amd64 and arm64 systems, Open WebUI
receives PyTorch from its CPU-only wheel repository; this avoids several
gigabytes of unused NVIDIA CUDA libraries, including CUDA packages that the
generic ARM64 dependency resolver would otherwise select.

After installation, create the first Open WebUI account at
`http://127.0.0.1:3000`, then run:

```bash
~/hermes-v4/.venv/bin/python ~/hermes-v4/bootstrap_openwebui.py
```

That creates the canonical tool and Alpha, Beta, and Gamma profiles. Enter the
NVIDIA, Deepgram, and ElevenLabs keys in Open WebUI, then rerun the bootstrap
once so the NVIDIA document embedding connection is linked. Keys are never
embedded in the installer.

## Display behavior

Hermes detects X11, Wayland, or headless operation at runtime. It can recover GUI
environment variables from the logged-in user's processes when a lingering
service started before desktop login.

- X11 uses `wmctrl` and `xdotool` for exact global window/input actions.
- Wayland keeps cloud, files, terminal, code, web, and Chromium DevTools working.
  It uses `grim` where available and refuses unsupported global input actions.
- Headless mode launches managed Chromium using its headless backend.

The refusal is deliberate: silently pretending Wayland permits unrestricted
global input would be unreliable and unsafe.

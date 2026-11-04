# Hermes Linux Mint desktop profile

This profile targets any amd64 PC with Linux Mint Cinnamon or XFCE. AI inference
remains cloud-only. CPU model, GPU model, RAM size and storage type are not
hardcoded; lower-end systems may be slower, but Hermes does not require a
specific Intel/AMD/NVIDIA device.
It is intentionally not an installer: `appliance-packages-amd64.txt` is the
reviewed input for a later installer build.

## Hardware baseline

- Any 64-bit amd64 PC supported by Linux Mint.
- An SSD is strongly preferred over a mechanical disk.
- Wired Ethernet is preferred for dependable remote access.
- Linux Mint Cinnamon or XFCE with X11 preferred, automatic security updates,
  and Tailscale.
- The machine must remain powered on and configured not to suspend while it is
  acting as a remote Hermes appliance.

## Driver policy

GPU drivers are intentionally outside Hermes. Install and verify the correct
Intel, AMD, or NVIDIA driver before running Hermes. Hermes detects `i915`,
`amdgpu`, `nvidia`, or `/dev/dri`, but never installs or replaces a driver.

Hardware-dependent configuration must occur on the target PC. Network adapters,
audio codecs, disks, monitors, and any optional discrete GPU cannot be selected
safely before that machine is inspected.

## Runtime policy

- Hermes Python and Open WebUI remain isolated and exactly locked. System Python
  is never overwritten.
- Node.js/npm are available for coding tasks, while each project owns its own
  JavaScript dependencies. Hermes does not install arbitrary global npm modules.
- Open WebUI uses CPU-only Torch solely because it is a dependency; no local AI
  model, Ollama, CUDA library, or model cache is installed.
- The Action Bridge and document API stay on loopback. Only Open WebUI is exposed
  through authenticated Tailscale Serve.
- Cinnamon/X11 or XFCE/X11 enables exact windows, keyboard, mouse, clipboard, monitor,
  workspace, audio, media, settings-panel, notification, and screen-lock tools.
- Appliance mode sets `HERMES_REQUIRE_GRAPHICAL=1`: browser/GUI work waits for an
  unlocked X11 session and never silently falls back to a headless browser.

## Acceptance checks for the physical PC

1. Install and verify the PC's own GPU driver before Hermes.
2. Run the read-only preflight before installation.
3. Confirm the readiness endpoint reports amd64, Linux Mint, Cinnamon or XFCE,
   X11/Wayland, a detected GPU driver/device, and no missing utilities.
4. Verify OpenGL/VA-API, audio input/output, Ethernet, SSD SMART health, display
   resolution, browser DevTools control, and Tailscale access.
5. Run the full regression suite and live tests for files, code, terminal,
   managed browser, vision, audio, clipboard, workspaces, and service recovery.
6. Reboot twice and confirm all services recover without manual commands.

Physical hardware validation is a release gate. Passing simulations on the
development laptop is not a substitute for that final test.

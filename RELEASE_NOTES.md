# Hermes 2.0.0 — Host and User

Hermes 2 is the first official split-platform release.

## What is new

- Separate **Hermes Setup** and **Hermes User** installers on Linux, Windows, and macOS.
- Hermes Setup installs the secure backend and includes Hermes User for the Host computer.
- Hermes User connects through Tailscale and uses the normal Open WebUI login.
- A native Electron shell provides microphone permissions, saved Host selection, platform icons, and Hermes branding.
- The model picker is restricted to **Hermes Alpha**, **Hermes Beta**, and **Hermes Gamma**.
- Open WebUI remains the standard, upgradeable interface and authentication backend.
- Health monitoring now uses the canonical `/health` endpoint.
- Linux ARM64 packages use the correct Electron runtime.
- Installer names and version metadata are consistent across every platform.

## Privacy and security

Provider keys, control tokens, passwords, chats, databases, and backups are never included in releases. Remote access remains private to the user's Tailscale network.

Unsigned builds may require the normal Windows SmartScreen or macOS Gatekeeper confirmation.

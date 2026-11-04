# Hermes 1.0 for Windows

Hermes ships as **Hermes-1.0.0-Windows-x64-Setup.exe** for 64-bit Windows 10 and Windows 11. The installer is per-user, preserves existing data during upgrades, installs one Start-menu entry, configures startup at sign-in, and provides a guarded uninstaller.

## Installation

1. Run the setup file using the Windows account that will own Hermes.
2. Review the license and destination, then continue. An unsigned build may show an Unknown Publisher warning; a public release should be signed through the CI signing hook.
3. The bundled, officially signed Python 3.12 bootstrap creates a private runtime. Pinned Hermes and Open WebUI dependencies are then installed and checked.
4. The Hermes wizard starts automatically. Create the first owner account, install the Alpha, Beta and Gamma presets, and add your own cloud-provider keys in Open WebUI.
5. Connect Tailscale if remote access is wanted. Hermes binds its privileged APIs to loopback and starts whenever the owner signs in.

Upgrading with a newer setup file keeps conversations, API connections, goals, routines, memories and backups. It replaces application source, republishes the canonical tool, restarts the local supervisor and verifies the three local services.

## Included capabilities

- Persistent goals, missions, approval inbox, recurring routines, command center, timeline, workspace context, operator preferences and skills registry.
- Alpha, Beta and Gamma cloud presets, cloud vision, web search, Deepgram speech input and ElevenLabs speech output when configured.
- Files, multi-file coding, terminal permission, applications, windows, keyboard, mouse, screenshots, clipboard, notifications and managed Chromium workflows.
- Restart-safe background work, memory, planning, safety modes, emergency stop, encrypted-backup readiness and owner-only local backups.
- Automatic startup, service supervision, log rotation, repair/upgrade flow and ownership-aware uninstall.

No Ollama, local model weights, API keys, conversations or personal credentials are included.

## Windows-specific behavior

Hermes runs with the signed-in user's permissions. UAC secure screens, locked desktops, CAPTCHAs and operating-system security boundaries cannot be controlled. Terminal execution remains disabled until the owner enables it. Windows does not provide Hermes' Linux Bubblewrap command sandbox, so enabled commands use normal Windows account permissions.

Optional Git, Node.js, Visual Studio Code and Tailscale installation uses `winget`. Existing installations are never claimed as Hermes-owned. The uninstaller offers dependency removal only when Hermes has a verifiable receipt for a fresh, unchanged installation.

Automatic desktop login remains an explicit Microsoft Autologon choice because the installer must never collect a Windows password.

## Uninstall and data

Uninstall from Windows Settings or `Uninstall.exe`. Runtime and source are removed. Personal data is kept by default; a separately confirmed option permanently deletes Hermes chats, keys, settings, caches and backups. Documents outside Hermes data are always kept.

Data: `%LOCALAPPDATA%\Hermes\data`
Private configuration: `%LOCALAPPDATA%\Hermes\config`
Application: `%LOCALAPPDATA%\Programs\Hermes`

## Release verification

The native Windows CI job assembles the shared core, runs platform regressions, verifies the official Python signature, builds with NSIS, optionally signs with the publisher certificate, recalculates SHA-256, and uploads the setup executable. Before wider distribution, install the exact artifact on a clean Windows machine and verify provider login, a real tool call, desktop control, managed browser, startup, Tailscale, backup, upgrade and both uninstall choices.

Publisher: **Anshul & Miheer** · All rights reserved.
Support: anshul.pandhare@mitwpu.edu.in · miheer.sabnis@mitwpu.edu.in

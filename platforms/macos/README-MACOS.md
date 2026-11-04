# Hermes 1.0 for macOS

Hermes provides two native Apple Silicon deliverables for macOS 14 and newer:

- **Hermes-1.0.0-macOS-Apple-Silicon.pkg** — standard Installer package.
- **Hermes-1.0.0-macOS-Apple-Silicon.dmg** — Finder disk image containing Hermes.app and the PKG.

The package installs Hermes.app in `/Applications`. First launch prepares the owner-only runtime and opens the same Hermes setup experience used by the other editions.

## Installation

1. Open the DMG and run the PKG, or run the standalone PKG directly.
2. Open Hermes from Applications. If Python 3.12 with Tk is unavailable, Hermes offers the official Python.org package, verifies its pinned hash and Apple-recognized signature, and lets Apple's Installer handle it.
3. Complete the Hermes wizard, create the first owner account, install Alpha, Beta and Gamma, and add your own provider keys in Open WebUI.
4. Grant Accessibility and Screen Recording only if desktop control and vision are wanted. Grant microphone access to the browser for voice.
5. Connect Tailscale if remote access is wanted. Hermes starts through a per-user LaunchAgent after login.

Installing a newer package preserves conversations, provider connections, goals, routines, memories and backups. First launch republishes the canonical tool, restarts the local supervisor and verifies the services.

## Included capabilities

- Goals, missions, approvals, routines, command center, timeline, workspace context, preferences and skill registry.
- Alpha, Beta and Gamma cloud presets, web search, cloud vision, optional Deepgram and ElevenLabs voice.
- File and code workflows, opt-in commands, application launch, windows, keyboard, pointer, screenshots, clipboard, audio and managed Chromium browsing.
- Persistent background work, memory, planning, safety modes, emergency stop, supervision, backups, repair and guarded uninstall.

No Ollama, local model weights, API keys, conversations or personal credentials are included.

## macOS security model

Hermes works with the signed-in user's permissions. Accessibility, Screen Recording and microphone grants remain under System Settings. Locked desktops, authentication dialogs, CAPTCHAs and macOS security boundaries cannot be bypassed. Command execution stays disabled until the owner enables it and then uses normal Mac account permissions.

CI ad-hoc-signs the app when no Apple certificate is configured. For public distribution, configure Developer ID Application and Installer identities plus notarization secrets; the workflow then signs, timestamps, notarizes and staples the artifacts. Without those credentials, macOS displays its normal unidentified-developer confirmation.

## Uninstall and data

Use Uninstall from the Hermes Ready page, then move Hermes.app to Trash if it remains. Runtime and automatic startup are removed. Personal data is kept by default; a separately confirmed option deletes chats, keys, settings and backups. Documents elsewhere are always kept.

Runtime and data: `~/Library/Application Support/Hermes`
Startup: `~/Library/LaunchAgents/com.hermes.assistant.plist`

## Release verification

The Apple Silicon CI job assembles Hermes, runs native regressions, builds and verifies Hermes.app, PKG and DMG, optionally signs/notarizes them, recalculates SHA-256 and uploads both installers. Before wider distribution, install the exact artifacts on a clean Mac and verify privacy grants, provider login, a real tool call, desktop control, managed browser, startup, sleep/wake, Tailscale, backup, upgrade and uninstall.

Publisher: **Anshul & Miheer** · All rights reserved.
Support: anshul.pandhare@mitwpu.edu.in · miheer.sabnis@mitwpu.edu.in

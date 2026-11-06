<p align="center">
  <img src="packaging/branding/hermes-dark.svg" alt="Hermes" width="280">
</p>

<h1 align="center">Your computer. Ready to help.</h1>

<p align="center">
  A cloud-powered personal AI that can understand, plan and act on your computer.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.1.0-0d0d0d">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-Linux%20%C2%B7%20Windows%20%C2%B7%20macOS-0d0d0d">
  <img alt="AI" src="https://img.shields.io/badge/AI-cloud-0d0d0d">
</p>

---

## Meet Hermes

Hermes combines a cloud AI model with secure tools running on your own computer. You talk through Open WebUI. Hermes can then work with your files, apps, browser, code, memory and multi-step tasks—with confirmation gates around sensitive actions.

```text
You → Open WebUI → Cloud AI → Hermes tools → Your computer
```

## What it can do

- **Work with files and code** — create, read, search and edit projects.
- **Use apps and browsers** — open apps, control windows and run managed web workflows.
- **Plan real work** — persistent goals, missions, routines, approvals and progress.
- **Remember context** — preferences, memories, timelines and workspace state.
- **Stay available** — starts automatically and supports private Tailscale access.
- **Talk naturally** — optional Deepgram speech input and ElevenLabs speech output.

Hermes uses your own cloud-provider keys. It does not install Ollama or local model weights.

## Download

Open the repository's **[Releases](https://github.com/design-development-environment/hermes/releases)** page and choose your platform:

| Platform | Installer | Requirements |
|---|---|---|
| Linux x86-64 | `.deb` | Debian, Ubuntu or Linux Mint |
| Linux ARM64 | `.deb` | Debian-family ARM64 system |
| Windows | `.exe` | 64-bit Windows 10 or 11 |
| macOS | `.pkg` or `.dmg` | Apple Silicon, macOS 14+ |

API keys and personal data are never included in releases. Unsigned test builds may show a Windows SmartScreen or macOS Gatekeeper confirmation.

## Inside Hermes

Open WebUI handles conversation. A local authenticated bridge performs approved actions and stores private state. Cloud providers handle language, vision and optional voice. Tailscale can make the web interface reachable only from your private network.

Hermes includes **122 tools** across computer control, managed browsing, documents, coding, memory, planning, backups, workflows and its persistent personal-agent command center.

## Build

Every commit is tested on native Linux, Windows and macOS runners. A version tag builds all installers, verifies their hashes and publishes them to GitHub Releases.

```text
core/                 Shared Hermes engine
platforms/windows/    Windows runtime and installer
platforms/macos/      macOS runtime and installer
packaging/            Linux installer and branding
tools/                Build and repository checks
```

Start with the [Linux guide](core/README.md), [Windows guide](platforms/windows/README-WINDOWS.md), or [macOS guide](platforms/macos/README-MACOS.md).

## Privacy

Hermes keeps local databases, tokens, logs, backups and provider keys out of source control. Cloud providers only receive the content needed for requests you make. Back up a test computer before trying a new installer.

---

<p align="center">
  <strong>Hermes 1.1.0</strong><br>
  Highly Efficient Real-time Machine for Everyday Support.<br><br>
  Created by Anshul & Miheer
</p>

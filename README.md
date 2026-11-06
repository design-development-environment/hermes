<p align="center">
  <img src="packaging/branding/hermes-dark.svg" alt="Hermes" width="280">
</p>

## Hermes 2.0 — Host and User

Hermes 2 is the official split-platform release. Install **Hermes Setup** on
the computer Hermes should control. Install **Hermes User** on another device
when you want to reach that Host privately through Tailscale. The User app
opens the normal Open WebUI sign-in page and never receives provider keys,
computer-control tokens, chats, or Host data. See [the Host and User guide](HOST_USER.md).

<h1 align="center">Your computer. Ready to help.</h1>

<p align="center">
  A cloud-powered personal AI that can understand, plan, and act on your computer.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-2.0.0-0d0d0d">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-Linux%20%C2%B7%20Windows%20%C2%B7%20macOS-0d0d0d">
  <img alt="AI" src="https://img.shields.io/badge/AI-cloud-0d0d0d">
</p>

---

## Meet Hermes

Hermes combines a cloud AI model with secure tools running on your own computer. You talk through Open WebUI. Hermes can then work with your files, apps, browser, code, memory and multi-step tasks—with confirmation gates around sensitive actions.

```text
You → Open WebUI → Cloud AI → Hermes tools → Your computer
```

### Three focused presets

The model picker intentionally shows only these three Hermes presets:

| Preset | Best for |
|---|---|
| **Hermes Alpha** | Deep reasoning and complex computer workflows |
| **Hermes Beta** | A balanced everyday assistant |
| **Hermes Gamma** | Fast, lightweight requests |

Your cloud-provider connection can contain more underlying models, but Hermes
keeps the everyday picker focused on Alpha, Beta, and Gamma.

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
| Linux x86-64 | `Hermes-setup-Linux-amd64.deb` or `Hermes-user-Linux-amd64.deb` | Debian, Ubuntu or Linux Mint |
| Linux ARM64 | `Hermes-setup-Linux-arm64.deb` or `Hermes-user-Linux-arm64.deb` | Debian-family ARM64 system |
| Windows | `Hermes-setup-Windows-x64.exe` or `Hermes-user-Windows-x64.exe` | 64-bit Windows 10 or 11 |
| macOS | `Hermes-setup-macOS-Apple-Silicon.*` or `Hermes-user-macOS-Apple-Silicon.*` | Apple Silicon, macOS 14+ |

API keys and personal data are never included in releases. Unsigned test builds may show a Windows SmartScreen or macOS Gatekeeper confirmation.

### Which installer do I need?

| If you want to… | Download |
|---|---|
| Let Hermes control this computer | **Hermes Setup** |
| Use a different device to connect to an existing Host | **Hermes User** |

For a remote device: sign both devices into the same Tailscale network, enter
the Host’s `.ts.net` address in Hermes User, then sign in with your usual Open
WebUI username and password. No pairing code or API key is copied to the User device.

## Inside Hermes

Open WebUI handles conversation. A local authenticated bridge performs approved actions and stores private state. Cloud providers handle language, vision and optional voice. Tailscale can make the web interface reachable only from your private network.

Hermes includes tools for computer control, managed browsing, documents,
coding, memory, planning, backups, workflows, and its persistent personal-agent command center.

## Development and releases

Every commit is tested on native Linux, Windows, and macOS runners. An official
version tag builds Host and User installers, verifies their SHA-256 hashes, and
publishes the results to GitHub Releases.

```text
core/                 Shared Hermes engine
platforms/windows/    Windows runtime and installer
platforms/macos/      macOS runtime and installer
packaging/            Linux installer and branding
tools/                Build and repository checks
```

Start with the [Linux guide](core/README.md), [Windows guide](platforms/windows/README-WINDOWS.md), or [macOS guide](platforms/macos/README-MACOS.md).

## Privacy

Hermes keeps local databases, tokens, logs, backups, and provider keys out of
source control. Cloud providers receive only the content needed for requests you
make. Back up a test computer before trying a new installer.

---

<p align="center">
  <strong>Hermes 2.0.0</strong><br>
  Highly Efficient Real-time Machine for Everyday Support.<br><br>
  Created by Anshul & Miheer
</p>

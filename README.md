<p align="center">
  <img src="packaging/branding/hermes-dark.svg" alt="Hermes" width="300">
</p>

<h1 align="center">Your computer. Ready to help.</h1>

<p align="center">
  Highly Efficient Real-time Machine for Everyday Support.
</p>

<p align="center">
  A personal AI assistant that connects cloud intelligence to the files, apps, and workflows on your own computer.
</p>

---

## A conversation that can get things done

Ask Hermes to pursue a goal, coordinate a multi-step mission, run an approved routine, find a file, revise a project, open a browser, draft a document, or check progress. Open WebUI provides the conversation. Hermes supplies authenticated local tools plus persistent goals, approvals, memory, planning, and computer actions. Your chosen cloud providers supply language, vision, speech recognition, and spoken replies.

Hermes is designed for one owner and one machine. It runs locally as an action bridge and keeps its private data on that machine. The current cloud edition does not install Ollama or local model weights. Requests to cloud models and optional voice services leave your computer; screen images sent for cloud vision do too.

## What it can do

| Area | Current capability |
|---|---|
| Conversation | Alpha, Beta, and Gamma workspace presets; cloud model connections through Open WebUI |
| Files and code | Read, create, edit, search, review, and organize permitted paths and projects |
| Browser | Web reading and a managed Chromium browser with page actions |
| Desktop | Screenshots, apps, windows, keyboard, and pointer where the operating system grants access |
| Personal agent | Persistent goals, missions, approvals, routines, briefings, timeline, skills, and command center |
| Workflows | Plans, background tasks, progress, memory, recovery, backups, and audit records |
| Remote access | Optional Tailscale access to the local web interface |
| Voice | Deepgram input and ElevenLabs output when configured in Open WebUI |

Tools run under the signed-in user's permissions. Some actions require explicit confirmation or a mode change. Terminal execution and desktop permissions differ by operating system; read the platform notes before enabling them.

## Choose your platform

| Edition | Package | Status | Desktop control |
|---|---|---|---|
| Debian-family Linux, x86-64 | `.deb` | Development build; current Mint setup is the reference | X11 is the complete target; Wayland is limited |
| Debian-family Linux, ARM64 | `.deb` | Build supported; hardware validation pending | X11 where available |
| Windows 10/11 x64 | `.exe` | Preview; native installation unverified | Windows APIs; some Linux features remain unported |
| Apple Silicon macOS 14+ | `.zip` containing `Hermes.app` | Preview; unsigned and native installation unverified | Accessibility and Screen Recording permission required |

The build workflow produces artifacts on every run. A version tag creates a **draft prerelease** for manual review. Build success is evidence that a package was assembled, not that native desktop control passed on every machine. Production distribution requires native acceptance tests and code signing; Apple distribution also requires notarization.

### Linux requirements

- Debian, Ubuntu, Linux Mint, or another Debian-family distribution with `apt` and `systemd`; 64-bit x86 or ARM64.
- A graphical desktop for visible app control. X11 supports the existing global window and input tools. Wayland keeps cloud, file, code, and managed browser tools but limits global desktop actions.
- At least **2 GB RAM recommended for a desktop session** and **8 GB free disk space** according to the current installer preflight. Allow more space during dependency installation; **4 GB RAM and 12 GB free disk** are practical initial targets for new hardware.
- Internet for package downloads and cloud AI; provider keys are entered during setup. A Chromium-compatible browser is needed for managed browser tools.
- CPU compatibility depends on Python wheels selected by the pinned Open WebUI dependencies. AVX support alone is not a guarantee. Run the preflight and native import checks on each target CPU before relying on the build.

For the tested Linux installation flow, see [Portability](core/PORTABILITY.md) and [Setup](core/README.md). Run `python core/portable_preflight.py` on a target before installing. `core/install.sh` is the current runtime installer; the `.deb` installs the graphical first-run wizard.

### Windows and Mac

Read the [Windows preview guide](platforms/windows/README-WINDOWS.md) or [Mac preview guide](platforms/macos/README-MACOS.md). These contain the actual requirements, permission steps, gaps, and acceptance tests. Neither preview carries your API keys or private data. An unsigned Windows executable or Mac app can trigger operating-system trust warnings; do not disable system protections to run a blocked preview.

## How Hermes works

```text
Your device ── Open WebUI ── Cloud model
                   │
                   └── Hermes tool bridge ── Goals, files, apps, browser, memory, tasks
                                │
                                └── Your computer's operating system
```

Open WebUI sends a tool call to Hermes through a local authenticated endpoint. The bridge checks authorization and the current safety mode, then calls the appropriate local tool. The response returns to the conversation. The tool bridge binds to loopback; Tailscale can expose the web interface to your own network when you opt in. Provider credentials stay in local Open WebUI settings and are never embedded in a release.

## Source layout

```text
core/                 Canonical Linux application and shared cross-platform modules
packaging/            Linux .deb wizard, branding, and Debian package builder
platforms/windows/    Windows runtime, desktop adapter, setup wizard, and NSIS packaging
platforms/macos/      Mac runtime, desktop adapter, setup wizard, and app packaging
tools/                Build assembly and repository checks
.github/workflows/     CI checks, platform artifacts, and draft releases
```

`tools/assemble.py` copies the 22 shared modules into a temporary platform build tree. Operating-system commands and paths stay behind platform adapters. Desktop and browser modules still have platform-specific implementations. The repository does **not** yet have complete cross-platform feature parity.

## Build and release

The workflow in [build.yaml](.github/workflows/build.yaml) runs on pushes, pull requests, and manual dispatch. It builds Linux packages for `amd64` and `arm64`, a Windows `.exe` preview, and a Mac `.app` preview ZIP. It runs shared tests on Linux, Mac overlay tests on a Mac runner, and Windows overlay tests on a Windows runner. These checks do not replace installing and exercising each package on a real target. CI uploads each artifact separately. A `v*` tag drafts a prerelease; a person must validate and publish it.

Local builds use `python packaging/build_deb.py --architecture amd64 --output dist/Hermes-linux-amd64.deb` for Linux. Windows and Mac builds first run `python tools/assemble.py windows dist/windows` or `python tools/assemble.py macos dist/macos`, then their platform build scripts with the dependencies described in the workflow. Build on a disposable machine or CI runner: installers download large dependencies.

## Security and privacy

The repository excludes databases, logs, API keys, backups, model caches, and built artifacts. The tool bridge uses an owner-only bearer token and records metadata-only audit events. File operations restrict writable paths. A cloud provider can see content you choose to send to it; select providers and model settings with that in mind. Remote access is optional. Back up the target machine before testing installers.

Source publication is private during development. “All rights reserved” applies to the Hermes project code. Python, Open WebUI, Inter, Pillow, and other dependencies keep their own licenses; their upstream notices must be reviewed before any public or commercial release.

See [Release checklist](RELEASE.md) for versioning and native validation gates.

## Project status

The active Linux installation is the reference. This repository copy does not replace it. The first cross-platform milestone is native smoke testing of each installer and the file, browser, screenshot, startup, and uninstall paths. After those pass, we can trim remaining duplicated adapters, add signing, and promote the previews to supported releases.

Created by **Anshul & Miheer**. Support: anshul.pandhare@mitwpu.edu.in · miheer.sabnis@mitwpu.edu.in.

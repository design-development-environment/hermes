# Hermes for Windows — 1.0.0-preview.2

This is the first native Windows port of Hermes. It is a test build, not a verified replacement for the Linux edition. The Linux installers were preserved.

## Install

1. Copy **Hermes-Windows-Setup.exe** to a Windows 10/11 x64 computer. Windows 11 on supported hardware is the intended target. This is not an ARM installer.
2. Double-click it using your normal Windows account. The installer is unsigned, so Windows may display an unknown-publisher warning. Only continue if you trust this build.
3. The first preparation window installs/reuses Python 3.12 and opens the dark Hermes wizard. The Python bootstrap is included; the remaining dependencies download from PyPI. Allow 12 GB free space.
4. Choose Install, wait for the three local services, open Hermes, and create the first owner account. Return to the wizard to add Alpha, Beta and Gamma.
5. In Open WebUI, add your NVIDIA connection and optionally Deepgram and ElevenLabs keys. No personal keys or conversations ship in this installer.
6. Connect Tailscale and enable Serve. This step uses Windows App Installer's `winget` and may request administrator approval. If winget is unavailable, install Tailscale from https://tailscale.com/download/windows and use its sign-in interface.
7. Hermes starts at Windows sign-in. To use automatic login, the wizard opens Microsoft's Autologon instructions. Enter Windows credentials only in that Microsoft utility. This cannot be completed without your credentials.
8. Run the wizard's checks, then complete the acceptance tests below.

Use the **Hermes** Start-menu entry to reopen setup or open your assistant. There is one Start-menu entry. The initial bootstrap window is standard Windows installer UI; the main wizard reuses the Linux v1 design, logos, Inter typography, rounded controls and progress bar.

## What is included

The existing cloud chat presets, tool definitions, file and code editing, persistent documents, memory, planning, background task engine, cloud vision routing, web search, managed browser tools, backups, authentication, audit logs and safety controls are included. Windows implementations cover application shortcuts, window enumeration/focus/layout, Unicode text entry, keyboard/mouse input, screenshots, clipboard, process status, desktop locking and notifications.

No Ollama or local model weights are installed. Open WebUI still depends on some machine-learning libraries internally. Its local model and local speech defaults are disabled.

## Differences and unfinished verification

- No Windows machine or VM was available for this build. Native execution, Python setup, dependency installation, application control, Tailscale, reboot behavior, cloud chat and voice still need Windows testing. Dependency resolution and Python checks on Linux do not establish these.
- Linux virtual-desktop movement, power policy, audio volume/mute and media-player discovery have not yet been ported. Those endpoints return explicit unsupported errors. This build does **not** yet have complete Linux feature parity.
- Terminal commands require explicit permission in setup. They run with your Windows account's permissions; Linux bubblewrap isolation is unavailable. Keep this off until you accept that difference. Administrator/UAC secure screens cannot be controlled.
- Startup occurs at sign-in, not as a system service before sign-in. Automatic login needs the separate Microsoft Autologon step. Locked desktops cannot be controlled.
- Setup installs Git, Node.js LTS and VS Code through winget. Windows App Installer must be available. Additional project-specific runtimes still need separate installation. Hardware drivers are not installed.
- Provider availability, quotas, model retirement and voice/vision compatibility depend on your cloud accounts.
- Desktop appearance uses the same Tk components, but Windows supplies the native titlebar and DPI behavior.

## Acceptance tests on Windows

1. Fresh installation finishes without errors; `http://127.0.0.1:3000` opens.
2. Create an account; all three presets appear; each can answer a chat and call a tool.
3. Ask Hermes to create a two-line document, read it, edit one line and confirm the saved text. Use a new test folder.
4. Open Notepad, list its window, type multiple lines, resize it, take a screenshot and describe it using cloud vision.
5. Open two managed browser pages, read text and take a page screenshot.
6. Save a memory, create a plan and run a background file task. Confirm completion from your phone.
7. Check voice input/output, Tailscale HTTPS access and access restrictions.
8. Restart Windows and sign in; wait for the services. Confirm there is only one runtime supervisor and desktop control works.
9. Test disabling terminal permission, locked desktop errors, failed downloads/retry and API provider failures.
10. Uninstall from Windows Settings. Test the default Keep Data option, then a separate installation with Delete Data and selected dependency removal. Confirm pre-existing software is preserved.

Logs: `%LOCALAPPDATA%\Hermes\data`. Bootstrap log: `%LOCALAPPDATA%\Programs\Hermes\bootstrap.log`.
Private settings: `%LOCALAPPDATA%\Hermes\config`. Data and keys are protected with a Windows user ACL. Uninstall keeps them by default. You may permanently delete Hermes chats, keys, settings, caches and backups, with a separate confirmation. Files created in Documents or other folders are kept.

Uninstall also offers individual Python, Git, Node.js, VS Code and Tailscale removal choices. A choice is available only when this installer recorded a fresh installation. Existing software, missing receipts and dependencies changed since installation are preserved. Older preview installations cannot retroactively prove ownership. Optional dependency removal may need administrator approval and can affect other applications using that software. Manually configured Windows Autologon is not changed. Third-party uninstallers may retain their own user settings.

Failures stop the uninstall with a retry message. The diagnostic log remains at `%LOCALAPPDATA%\Hermes-uninstall.log`. This updated flow still requires Windows testing.

## Build provenance

`source` contains the isolated Windows source snapshot. `port_source.py` records the initial port transformations; it is not a repeatable generator for later hand-edited Windows changes. Rebuild the existing source using `build.py`. `requirements-windows.lock` contains pinned versions and distribution hashes resolved specifically for Windows x64/Python 3.12. `SHA256SUMS` records the deliverable hashes.

Upstream documentation: https://docs.openwebui.com/getting-started/quick-start/ , https://docs.python.org/3.12/using/windows.html , https://learn.microsoft.com/en-us/sysinternals/downloads/autologon .

Publisher: Anshul & Miheer. Hermes project code: All rights reserved. Bundled Python, Pillow, Inter and other third-party components retain their respective licenses. Support: anshul.pandhare@mitwpu.edu.in / miheer.sabnis@mitwpu.edu.in.

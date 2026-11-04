# Hermes macOS preview — Apple Silicon

This is an unsigned development preview for **Apple Silicon (M1 and newer), macOS 14+**, with Python 3.12. It has not been run on a Mac. It is not a signed/notarized production installer or a verified full equivalent of the Linux version. Test on a spare Mac/user account first.

## Which file to use

Copy **Hermes-macOS-Preview.zip** to your Mac and extract it. Move **Hermes.app** into your user's Applications folder, then open it. The other files in the development folder are source and build inputs.

The app opens Terminal for preparation. If Python 3.12 with Tk is missing, it asks before downloading the official Python installer, checks a pinned SHA-256 hash and invokes macOS signature checking, then opens Apple's package installer. You must complete that installer and return to Terminal. Afterward the dark Hermes wizard opens. Internet and at least 12 GB free space are required.

Gatekeeper may block this unsigned app. It has not been approved by Apple. Do not disable Gatekeeper or other Mac security settings to make it work. A signed release needs an Apple Developer ID, notarization and real Mac validation.

## Setup

1. Run the compatibility check and install the dependencies in the wizard.
2. Open Hermes, create your owner account and return to add Alpha, Beta and Gamma.
3. Enter your own NVIDIA API key in Open WebUI; optionally add Deepgram and ElevenLabs. No keys, chats or local model weights are included.
4. Grant Accessibility and Screen Recording permissions in System Settings. Grant microphone permission to the browser for voice. Depending on macOS attribution, the permission entry may be Python, Terminal or Hermes. This identity and background launch behavior need Mac testing.
5. Install/sign into Tailscale using the official link in setup, then enable Serve. Tailscale installation and system-extension approval are manual in this preview.
6. Run verification and test the operations listed below.

Hermes starts through a per-user LaunchAgent after login. Keep the Mac awake and unlocked for desktop control. Automatic Mac login is not configured. Terminal execution stays disabled until you explicitly enable it; enabled commands have your account permissions and no filesystem sandbox.

## Implemented versus unverified

The cloud presets, web search integration, file/code operations, memory, planning, task engine, document creation, backups and authentication are carried over. Mac implementations are provided for app discovery/launch, window listing and focus, text/keyboard/mouse input, screenshots, clipboard, audio volume/mute, screen layout and managed Chrome/Edge browsing. Every native Mac implementation is still unverified on a Mac. Screen capture and vision can transmit your screenshot to your configured cloud provider.

Space/workspace management, media-player control, power-policy controls and maximize/restore are not implemented. Window drag behavior and legacy TextEdit automation are not equivalent to the Linux editor workflows. Ambiguous window titles are rejected. Keyboard support is limited to the implemented common shortcuts. Managed browsing needs an existing Chrome/Edge/Chromium installation; Safari is not the managed automation backend. Git, Node.js, editors, Tailscale and other development applications are not automatically installed.

This app bundle is a shell launcher plus the shared Tk wizard, not a compiled native Cocoa application. It is distributed as a ZIP, not a signed PKG or DMG. The initial Terminal preparation and Python installation differ from the Linux installer. Inter may fall back to the system font.

## Data, uninstall and privacy

Runtime and data live in `~/Library/Application Support/Hermes`. Startup uses `~/Library/LaunchAgents/com.hermes.assistant.plist`. Services bind to loopback. Runtime and private data directories use owner-only permissions.

The Ready page offers **Uninstall**. It stops the Hermes LaunchAgent and removes its private runtime and code. Keep personal data by default or explicitly delete chats, keys, settings and backups. Your documents elsewhere and shared Python/Tailscale/browser installations are kept. Move Hermes.app to Trash afterward. The uninstaller has not been tested on a Mac.

## Required Mac acceptance tests

- First launch, Python preparation, download failure/retry and private runtime installation.
- Owner signup, three presets, provider authentication, web search and actual tool calls.
- Accessibility and Screen Recording consent; locked desktop and permission-denied behavior.
- New document creation/read/edit, memory, plan and background workflow.
- Open TextEdit and a managed browser; target a unique window; type Unicode/multiline text; capture and analyze a screenshot.
- Tailscale phone access, microphone input and spoken output.
- Reboot/login startup, sleep/wake, service failures and restart behavior.
- Keep-data and delete-data uninstall paths; preserved documents and shared software.

Build validation performed on Linux is recorded in VALIDATION.md in the development folder. It cannot establish that these Mac tests pass.

Apple permissions: https://support.apple.com/guide/mac-help/control-access-screen-system-audio-recording-mchld6aa7d23/mac
Apple distribution requirements: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
Python: https://www.python.org/downloads/release/python-31210/

Publisher: Anshul & Miheer. Hermes code: All rights reserved. Third-party components retain their own licenses. Support: anshul.pandhare@mitwpu.edu.in / miheer.sabnis@mitwpu.edu.in.

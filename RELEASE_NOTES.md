# Hermes 2.0.1 — Bug fixes

Hermes 2.0.1 is a clean-machine installer reliability update.

## Fixed

- Windows backend setup no longer stops on MCP's `PyJWT[crypto]` dependency while pip hash verification is enabled.
- The matching macOS dependency lock has the same explicit cryptography extra.
- CI now resolves the complete hashed Windows and macOS installer locks on native runners before packaging or publishing.
- Repository checks reject unpinned, unhashed, or accidentally stripped dependency extras.
- SQLite health, preset, planning, and setup checks now commit transactions and close connections cleanly instead of leaking handles.
- Electron builds no longer pass deprecated target settings through npm, removing npm 11 warnings while preserving the requested platform runtime.
- Setup screens, service APIs, backup manifests, desktop packages, and documentation now report one consistent version.

All Hermes 2.0 features remain unchanged: Host/User installers, Open WebUI,
Tailscale access, Hermes Alpha/Beta/Gamma, desktop tools, memory, planning,
workflows, cloud vision, and optional cloud voice.

## Privacy and security

Provider keys, control tokens, passwords, chats, databases, and backups are never included in releases. Remote access remains private to the user's Tailscale network.

Unsigned builds may require the normal Windows SmartScreen or macOS Gatekeeper confirmation.

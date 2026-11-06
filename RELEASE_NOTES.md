# Hermes 2.0.2 — Windows installation repair

Hermes 2.0.2 fixes a Windows native-module lock that could stop backend setup.

## Fixed

- The graphical setup dependency now exactly matches the pinned runtime dependency, so Windows never tries to replace a loaded `_imaging` DLL.
- Failed or partial Windows installations can be repaired by running the updated installer again.
- Host upgrades now reinstall and verify the complete pinned dependency set before restarting services.
- macOS uses the same deterministic bootstrap/runtime dependency rule.
- Repository checks now fail if a future bootstrap dependency drifts away from either platform lock.

All Hermes 2.0 features remain unchanged: Host/User installers, Open WebUI,
Tailscale access, Hermes Alpha/Beta/Gamma, desktop tools, memory, planning,
workflows, cloud vision, and optional cloud voice.

## Privacy and security

Provider keys, control tokens, passwords, chats, databases, and backups are never included in releases. Remote access remains private to the user's Tailscale network.

Unsigned builds may require the normal Windows SmartScreen or macOS Gatekeeper confirmation.

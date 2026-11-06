# Hermes 2.0.4 — clean Windows first-run

Hermes 2.0.4 fixes the two remaining failures reproduced during a clean
Windows Host installation.

## Fixed

- Fresh Windows installs now restart the private Python interpreter after the
  pinned dependency set is installed. This lets Python process pywin32's new
  path configuration before Hermes imports `win32api`, `win32security`, or
  `win32com`.
- The **Apply startup choice** action now creates the Windows startup shortcut
  in a fresh runtime process. The setup wizard advances normally instead of
  remaining on the Tailscale and startup page.
- Partial installations remain repairable by rerunning the same setup action.
- The lightweight Hermes User regression suite now respects Windows permission
  semantics while retaining the owner-only mode assertion on POSIX systems.

## Validation

- New Windows regressions verify that first-run configuration and startup
  shortcut creation are delegated to fresh Python processes.
- Repository hygiene, dependency locks, shared backend tests, desktop-client
  tests, and assembled Windows tests run before release publication.
- Native CI builds and inspects Linux amd64, Linux arm64, Windows x64, and
  Apple Silicon macOS Host and User packages.

All Hermes 2.0 capabilities remain unchanged. Provider keys, passwords,
tokens, chats, databases, and backups are not included in release artifacts.
Unsigned builds may show the normal Windows SmartScreen or macOS Gatekeeper
warning.

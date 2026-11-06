# Hermes 2.0.3 — resilient cross-platform setup

Hermes 2.0.3 fixes the Windows setup failure that appeared after Git had
already installed successfully.

## Fixed

- A successful Git, Node.js, VS Code, or Tailscale installation no longer fails
  merely because Windows exposes a different registry display name.
- Hermes records such a package as usable but not owned, so uninstall keeps it
  safely instead of guessing.
- `winget` operations retry transient failures and verify that a reported
  installation is actually detectable.
- Git, Node.js, and VS Code are treated as repairable desktop add-ons. A failure
  in one no longer prevents the core Hermes services from starting.
- Optional dependency failures are saved in the Hermes data directory for
  diagnosis and cleared automatically after a successful repair.
- macOS CI retries intermittent `hdiutil verify` failures before rejecting a
  valid DMG.

## Simulated setup states

Automated tests cover pre-existing packages, fresh installs, missing registry
inventory, unverifiable ownership, package-manager failure, false-success
installs, changed packages, safe uninstall, partial reruns, lock resolution,
native platform packaging, and repository credential checks.

All Hermes 2.0 capabilities remain unchanged. Provider keys, control tokens,
passwords, chats, databases, and backups are never included in releases.

Unsigned builds may require the normal Windows SmartScreen or macOS Gatekeeper
confirmation. Clean-machine acceptance testing remains required for each OS;
software cannot truthfully guarantee every future third-party or hardware error.

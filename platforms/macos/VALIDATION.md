# macOS V8 validation

Hermes 8.0.0 is built on an Apple Silicon `macos-15` GitHub Actions runner.
The release gate assembles the shared V8 source, runs the macOS port
regressions, builds and verifies `Hermes.app`, creates native `.pkg` and `.dmg`
installers, optionally signs and notarizes them, verifies the disk image, and
uploads both installers plus `SHA256SUMS`.

Repository validation currently covers authentication, path boundaries,
explicit terminal and clipboard consent, multiline Unicode file writes,
document collision handling, 122 unique tool schemas, the V8 command center,
and inclusion of `agent.db` in backups. The application bundle metadata,
Apple-Silicon requirement, executable permissions, shared source, and version
are checked before packaging.

Public releases still require Apple Developer Application and Installer
certificates, notarization credentials, and clean macOS 14+ acceptance tests for
permissions, restart, upgrade, Tailscale, provider connections, audio, and
removal. Ad-hoc-signed builds remain usable for local testing with the normal
Gatekeeper confirmation.

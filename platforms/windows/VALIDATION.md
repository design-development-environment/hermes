# Windows V8 validation

Hermes 8.0.0 is built as a native NSIS installer on `windows-2025` in GitHub
Actions. The release gate assembles the shared V8 source, runs the Windows port
regressions, validates the official Python bootstrap signature, compiles the
installer, optionally signs it, recalculates its SHA-256 digest, and uploads the
`.exe` plus `SHA256SUMS`.

Repository validation currently covers authentication, path boundaries,
explicit terminal and clipboard consent, multiline Unicode file writes,
document collision handling, dependency ownership-safe uninstall behavior,
122 unique tool schemas, the V8 command center, and inclusion of `agent.db` in
backups. NSIS also compiles the complete payload into a valid Windows PE
installer during cross-build validation.

Public releases still require a publisher certificate and clean Windows 10/11
acceptance tests for setup, desktop controls, restart, upgrade, Tailscale,
provider connections, audio, and uninstall. An unsigned build is valid for
local testing but Windows may show a SmartScreen warning.

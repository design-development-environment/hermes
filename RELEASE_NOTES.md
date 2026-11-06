# Hermes 2.0.6 — Linux installation reliability

- Fixed the Debian Host/User package collision: each now owns a separate app-icon path, so the User app installs normally after Hermes Setup.
- Hermes Setup now runs the bundled User installation in its own visible progress view. Success opens Hermes User; any failure stays visible in the installer instead of being lost behind a background authorization prompt.
- Added a release gate that reads both generated Debian package manifests and fails the build if they own any overlapping files.
- A broken unrelated third-party APT source no longer stops Hermes before dependency installation. Hermes retains normal APT signature protection and uses only existing trusted package metadata when refresh fails.
- Release automation is tag-driven, so every published version builds and releases the exact tagged source without a manually edited version condition.

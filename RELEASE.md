# Release checklist

## Hermes 2.0.4 — clean Windows first-run

- Restarts Python after installing pywin32 before importing Windows modules.
- Runs startup-shortcut creation outside the long-lived setup UI process.
- Keeps partial Windows installations safe to retry.
- Covers the first-run and startup handoff with Windows-native regressions.
- Keeps separate Hermes Setup and Hermes User installers for every platform.

The repository builds release installers. A successful CI run proves that
source checks, platform regressions and native packaging passed. Final
publication still requires clean-machine acceptance testing and signatures.

1. Keep provider keys, chat data, tokens, backups, and local `.env` files out of
   the repository. Run `python tools/repo_check.py` before every push.
2. Run shared and platform tests. Build both Debian architectures, Windows NSIS
   setup, and Apple Silicon PKG/DMG on their native CI runners.
3. Update the single root `VERSION` file. Every package reads that version.
4. Install each artifact on a clean, supported machine or VM. Check signup,
   provider connection, all three presets, a real tool call, file and code
   edits, managed browser, desktop capture, startup after reboot, Tailscale,
   backup, repair, and uninstall. Record OS, CPU, and test results.
5. For Windows and macOS, sign packages with the publisher's own credentials.
   Notarize the Mac package. Do not put signing credentials in source control.
6. Push a matching `v*` tag only after validation. CI publishes the native
   installers and platform-specific checksum files to GitHub Releases.

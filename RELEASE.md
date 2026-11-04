# Release checklist

The private repository builds development artifacts. A successful CI run means
the source was checked and packages were assembled. It does not certify a new
computer, operating system, CPU, or native desktop permission flow.

1. Keep provider keys, chat data, tokens, backups, and local `.env` files out of
   the repository. Run `python tools/repo_check.py` before every push.
2. Run the shared and platform overlay tests. Build both Debian architectures,
   Windows NSIS setup, and the macOS app ZIP in CI.
3. Update package versions in `packaging/build_deb.py`,
   `platforms/windows/installer.nsi`, and `platforms/macos/build.py` together.
   Compare the release tag with these versions before creating it.
4. Install each artifact on a clean, supported machine or VM. Check signup,
   provider connection, all three presets, a real tool call, file and code
   edits, managed browser, desktop capture, startup after reboot, Tailscale,
   backup, repair, and uninstall. Record OS, CPU, and test results.
5. For Windows and macOS, sign packages with the publisher's own credentials.
   Notarize the Mac package. Do not put signing credentials in source control.
6. Push a `v*` tag only after validation. CI creates a **draft prerelease**;
   review artifact hashes and native test evidence before publishing it.

The first cross-platform releases remain previews until these gates pass.

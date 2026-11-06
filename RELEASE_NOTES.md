# Hermes 2.0.5 — Quality of life improvements

- Windows setup starts through a graphical launcher and keeps background command output in the wizard. Host and User now have distinct Start menu shortcuts.
- Windows looks for Tailscale in its standard directory and on PATH, limits the login wait, then enables Serve after successful login.
- Windows and macOS reopen the setup wizard after an incomplete installation. Completed setups continue through the upgrade path.
- macOS bootstrap uses a graphical Python download prompt and writes diagnostics to ~/Library/Logs/Hermes/setup.log.
- Linux Host installs its bundled User package using the same filename the builder produces.
- Windows uninstall waits for Hermes processes to exit. The User uninstaller reports a locked runtime so the owner can close the app and retry.
- Host and User application icons use rounded Hermes artwork.

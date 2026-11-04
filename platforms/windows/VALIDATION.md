# Validation — Windows preview 1.0.0-preview.2

Completed on the Linux development computer:

- NSIS produced a Windows PE executable without compiler warnings in the final build.
- The dependency solver resolved 257 pinned packages for Windows x64 / Python 3.12 and generated distribution hashes. This is dependency resolution, not proof that every dependency installs or imports on Windows.
- All 36 Python source modules parsed successfully.
- Eight core tests passed: authenticated tool access, Unicode multiline writes, overwrite rejection, writable-folder boundaries, terminal consent, document collision handling, backup creation, clipboard consent and generated tool schema uniqueness (some tests cover more than one assertion). Windows directory lookup was replaced with temporary directories for these tests. Native Windows APIs were not exercised.
- All seven wizard pages rendered using Tk on Linux; navigation buttons were mapped and remained within the 1000 × 720 window. The preview image is from Linux, not Windows.
- SHA-256 comparisons confirm every pre-existing Desktop .deb is unchanged.

Not validated: Windows bootstrap execution, PowerShell execution, fresh dependency installation, native input/screenshot APIs, winget installation, Windows logon startup, uninstall on Windows, Tailscale access, provider calls and audio. No Windows environment was attached to this session.

Read README-WINDOWS.md for feature gaps, installation steps and the required Windows acceptance tests. Do not describe this artifact as feature-complete or production-tested.

Uninstall update: nine isolated ownership tests passed, covering existing software, failed detection/install/removal, updated dependencies, verified removal and unknown package IDs. These use mocked package-manager calls; real Windows uninstall is still untested.

Both PowerShell entry points passed the PowerShell 7 parser on Linux. The actual cleanup helper passed temporary-tree removal and symlink refusal tests on Linux. Windows PowerShell 5.1, registry inventory, package uninstallers and the graphical uninstall choices still need Windows validation.

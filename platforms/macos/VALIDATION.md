# Validation — macOS preview 1

Performed on Linux:

- Resolved 249 pinned dependencies with hashes for Python 3.12 / Apple Silicon / macOS 14. The initial macOS 13 resolution failed because the required ONNX Runtime wheel starts at macOS 14. No dependency versions were silently downgraded.
- Parsed all packaged Python sources and checked bootstrap/launcher Bash syntax.
- Eight core regression tests passed: authentication, multiline Unicode file writes, overwrite rejection, path restrictions, terminal consent, document collision handling, backup creation, clipboard consent and tool schema uniqueness (multiple assertions in some tests). Tests used temporary directories and did not exercise Apple APIs.
- All seven Tk wizard pages rendered on Linux with visible navigation controls at 1000 × 720. The preview screenshot is from Linux, not a Mac.
- Built and checked the ZIP, app metadata, executable permissions and pinned Python package hash. Existing Windows and Linux installer hashes are unchanged.

Not performed: any Mac execution, Finder/Gatekeeper launch, Python installation on a Mac, actual PyObjC calls, consent identity under LaunchAgents, native screenshots/input, provider requests, phone/voice access, startup/restart or uninstall on macOS. The package is unsigned and unnotarized. The acceptance test list and unsupported features are in README-MACOS.md.

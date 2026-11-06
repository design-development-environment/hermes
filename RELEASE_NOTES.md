# Hermes 1.1.0 — Bug fixes

Hermes 1.1.0 is a reliability release for Linux, Windows and macOS.

## Fixed

- Restored Open WebUI's original interface by removing Hermes-specific UI
  defaults, custom model artwork and conversation starters.
- Fixed symbolic-link deletion so Hermes removes the link, never its target.
- Fixed concurrent file creation so a newly created file cannot be silently
  overwritten, including when `overwrite` was requested before the race.
- Fixed large-file reads so the actual bytes read remain bounded if a file grows
  after its initial size check.
- Fixed upgrades from empty, malformed or non-object legacy model metadata.
- Fixed release validation gaps by compiling the assembled Windows and macOS
  sources before native tests.
- Fixed wasted CI work by cancelling superseded branch builds while preserving
  every version-tag release build.

Existing chats, accounts, API keys, provider connections, tools, model presets
and local data are preserved during the upgrade.

# Hermes roadmap numbering

Hermes has two historical numbering tracks. They must not be mixed.

## Current implementation track

- V5.0: authenticated local computer and codebase operator.
- V5.1: reliability, health monitoring, tests, and backups.
- V5.2: structured managed-browser workflows.
- V5.3: scheduled and restart-safe background workflows.
- V6.0: long-term memory and smarter approval-first planning.
- V6.1: safety dashboard, emergency stop, resilient plan revision, memory hygiene,
  MCP readiness, and optional encrypted-backup support.

This track is complete through **V6.1.0**.

- Hermes Alpha: smarter natural-language intent routing, screen-aware requests,
  concise tool policy, and verify-before-reporting behavior.

## Original product roadmap

The original `context.md` uses product milestones: local AI, phone access, voice,
safe actions, MCP, home automation, remote access, and wearable input. Several
were completed out of order: secure Tailscale access and broad computer actions
already exist, while full MCP, wake-word voice, home automation, and wearable
input remain future product work.

The next release can focus on user-selected MCP integrations. Native voice, a
separate mobile app, and Home Assistant integration are intentionally deferred;
Open WebUI remains Hermes's interface for now.

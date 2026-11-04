# Hermes V8

Hermes V8 serves chat through Open WebUI with three cloud model presets and
uses one authenticated local Workspace Tool for desktop, managed-browser, coding,
terminal, file, document, backup, and persistent background-task actions. Open
WebUI is available through Tailscale Serve. The Open WebUI Workspace Tool is the
single source of truth; duplicate OpenAPI connections are not used.

The Mint Cinnamon/XFCE desktop edition also controls clipboard, displays, audio,
media, workspaces, settings panels, network status, keep-awake policy, and
session lock, with confirmation gates on sensitive actions.

Hermes includes a portable Debian/Ubuntu-family runtime for Linux Mint, Ubuntu,
Debian, and 64-bit Raspberry Pi OS on amd64 and ARM64. See `PORTABILITY.md` for
the installer and exact X11, Wayland, and headless capability matrix.
The generic amd64 Mint Cinnamon/XFCE desktop design is documented in
`APPLIANCE_PROFILE.md`; its package manifest is deliberately not an installer.

## Source of truth

- `openwebui_tool.py`: all Hermes functions offered to the model.
- `agent_control.py`: persistent goals, missions, approvals, routines, timeline,
  explicit workspace context, operator preferences, skills, and command center.
- `model_instructions.txt`: concise smart-routing and safety instructions for Hermes Alpha.
- `sync_openwebui_tool.py`: publishes both files into Open WebUI.
- `platform_support.py`: distribution, architecture, session, browser, localized
  folder, and capability detection shared by the services.
- `graphical_control.py`: authenticated Cinnamon controls for monitors,
  clipboard, audio, media, workspaces, settings panels, and desktop locking.
- `install.sh` and `bootstrap_openwebui.py`: clean-machine installation and
  first-owner Workspace setup without embedding credentials.
- `requirements-hermes.lock`: the single, exact core dependency set used by the
  installer on every supported machine.
- `requirements-openwebui-*.lock`: architecture-validated, exact WebUI graphs;
  both select CPU Torch and exclude CUDA packages.
- `model_runtime.py` and `vision.py`: validated hot-swappable OpenAI-compatible
  cloud vision providers.
- `workspace_preset.py`: creates Workspace presets around API base models
  while attaching the canonical Hermes tool, web search, and a vision selection.
- `app.py`: desktop and file-inspection API on loopback port 8765.
- `computer_control.py`: V5 application, filesystem, coding, terminal, process,
  keyboard, mouse, and notification capabilities.
- `codebase_control.py`: repository inspection, search, ranged reads, validated
  multi-file creation and editing, Git review, commits, and VS Code opening.
- `browser_control.py` and `cdp_client.py`: ordinary browser launch plus a
  dedicated visible Chrome session with page snapshots, numbered elements,
  verified interaction, uploads, screenshots, and confirmation gates.
- `task_control.py`: private SQLite queue for scheduled, checkpointed background
  workflows with restart recovery, retry, pause, resume, and cancellation.
- `memory_control.py`: private, searchable long-term memory with secret rejection
  and archive-based forgetting.
- `planning_control.py`: approval-first plans with dependencies, risk labels, and
  handoff to the persistent task queue.
- `governance_control.py`: dashboard, safety modes, emergency stop, audit summary,
  and non-secret MCP integration readiness.
- `maintenance_control.py` and `backup_manager.py`: unified health reporting and
  owner-only atomic backups.
- `hermes_tools.py`: authenticated document API on loopback port 8766.
- `persistent_workflow.py`: portable atomic document creation and verification.
- `hermes-action-bridge.service` and `hermes-documents.service`: user services.
- `hermes-health-monitor.timer`: checks the three Hermes services every two
  minutes and restarts only an unhealthy component.
- `hermes-managed-browser.service`: on-demand managed Chrome lifecycle.
- `hermes-backup.timer`: creates one daily backup and retains the newest 14.

Three selectable presets are installed:

- **Hermes Alpha** uses `nvidia/nemotron-3-ultra-550b-a55b` for maximum
  reasoning, with Super VL for vision.
- **Hermes Beta** uses `nvidia/nemotron-3.5-super-vl-120b-a12b` for balanced
  chat, tools, and vision.
- **Hermes Gamma** uses `nvidia/nemotron-3.5-lightning-30b-a3b` for speed, with
  Super VL for vision.

Deepgram `nova-3` provides cloud speech-to-text, ElevenLabs provides cloud
text-to-speech, and `nvidia/nemotron-3-embed-1b` provides Open WebUI document
embeddings. Cloud vision reuses the matching owner-configured Open WebUI
connection credential without copying the key into source or model settings.
The document token stays at `~/.config/hermes/tool-token` and is never placed
in the tool source or model instructions.

Development commands run with normal user permissions inside a Bubblewrap
filesystem sandbox. They can write to the selected project folder while the rest
of the computer is mounted read only. Every authenticated bridge action is logged
to `logs/actions.jsonl` without storing request contents or credentials.

Backups are stored in `~/.local/share/hermes/backups` with mode `0600`. They
contain sensitive Open WebUI data, vector state, and private runtime configuration
and must never be uploaded or shared. Persistent
task state is stored in `~/.local/share/hermes/tasks.db` with mode `0600`.
Goals, routines, approvals, and timeline metadata are stored in the owner-only
`~/.local/share/hermes/agent.db`. Memory, plans, agent state, and safety settings
are included in every local backup as well.
GPG-encrypted copies are available only when the owner configures a recipient in
the backup service environment; Hermes never stores a passphrase or private key.

All Hermes services, Tailscale, and the health timer are enabled at startup. The
user service manager has lingering enabled, so the local APIs and
Open WebUI start in the background after boot. GUI control becomes available
after the Linux desktop session is logged in and unlocked.

## Checks

```bash
systemctl --user status hermes-action-bridge hermes-documents open-webui hermes-health-monitor.timer hermes-backup.timer
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8766/health
tailscale serve status
.venv/bin/python -m unittest discover -v
```

After editing the Workspace Tool or model instructions, run
`python3 sync_openwebui_tool.py` and restart `open-webui.service`.
The core does not require a graphical session. Exact global window, keyboard,
and mouse actions require X11; Wayland and headless systems retain managed
browser and all non-GUI capabilities.

See `IMPLEMENTATION_STATUS.md` for the verified feature matrix and `ROADMAP.md`
for the distinction between release numbering and the original product roadmap.
See `MODEL_PROVIDERS.md` for API-model, vision-preset, and web-search setup.

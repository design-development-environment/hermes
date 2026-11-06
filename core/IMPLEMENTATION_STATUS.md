# Hermes implementation status

Current release: **Hermes 2.0.5**

## 1.0 — persistent personal agent

- Persistent goals and milestones survive chats, service restarts, and reboots.
- Multi-workstream missions use planner, researcher, browser, coder, operator,
  and reviewer roles to structure work, then hand approved steps to the existing
  restart-safe task engine.
- Owner approval inbox records expiring decisions without treating approval as
  automatic execution.
- On-demand, interval, daily, and weekly routines are created disabled, require
  explicit enabling, and stop queuing work outside normal safety mode.
- The command center combines goals, tasks, approvals, routines, safety state,
  and proactive suggestions. The timeline records metadata, not message or file
  contents.
- Current-workspace context reports open windows, managed browser pages, and
  bounded recent-file metadata only when requested; snapshots are opt-in.
- The operator manual stores only explicit non-secret preferences. Core skills
  cannot be disabled from chat, while optional/integration skills remain owner
  controlled and still require authorized connections.

## Generic Mint desktop profile

- Targets any amd64 Linux Mint Cinnamon or XFCE PC, with X11 preferred,
  Tailscale, and cloud-only AI.
- Adds authenticated controls for clipboard, monitor layout, PipeWire/PulseAudio
  volume and mute, MPRIS media, Cinnamon workspaces, settings panels, network
  status, AC stay-awake policy, and session locking.
- Clipboard reads, desktop locking, and power-policy changes require explicit
  confirmation. Passwords, Wi-Fi secrets, and clipboard contents are never
  written to the audit log.
- Adds a read-only physical-machine readiness report covering distribution,
  architecture, Cinnamon/XFCE, display session, detected GPU driver/device,
  and required utilities.
- Defines a reviewed future package manifest with desktop automation, audio/media,
  diagnostics, Python, Node.js, and development tools without installing GPU
  drivers, local AI, or CUDA.
- Rotates metadata-only action logs at 5 MB, retains five rotations, gives each
  API response a request ID, disables caching, and adds MIME-sniff protection.

## Portable Ubuntu/Raspberry Pi runtime

- Supports amd64/x86-64 and ARM64/aarch64 on Debian/Ubuntu-family systems,
  including Linux Mint and 64-bit Raspberry Pi OS.
- Detects X11, Wayland, or headless operation and reports exact capabilities.
- Removes personal home paths from services and resolves localized XDG folders.
- Selects Google Chrome, Chromium, or Chromium Browser dynamically; managed CDP
  automation works visibly or headlessly without global desktop input.
- Uses `gnome-screenshot`/`scrot` on X11 and `grim` on wlroots Wayland.
- Provides a preflight check, APT installer, first-owner bootstrap, portable
  user services, and fresh-database creation of all three model profiles.
- Uses one exact dependency lock, transactional relocatable environments, and
  CPU-only PyTorch on amd64 and ARM64 to avoid unused CUDA packages.
- Document creation is atomic and desktop-independent instead of requiring Xed.

## Cloud-only model layer

- Adds Alpha (Ultra), Beta (Super VL), and Gamma (Lightning) Workspace profiles.
- Uses NVIDIA Super VL for desktop vision in all three profiles; the matching API
  credential remains in Open WebUI's protected store.
- Uses NVIDIA Nemotron 3 Embed 1B for Open WebUI document embeddings.
- Uses Deepgram Nova-3 for speech-to-text and ElevenLabs for text-to-speech.
- Keeps every filesystem, desktop, browser, terminal, memory, planning, safety,
  backup, and background-workflow action on the local Hermes bridge.
- Removes Ollama from the runtime, health contract, and Open WebUI model layer.

## Hermes Alpha — smart operator behavior

- Replaces the long, repetitive model prompt with concise intent routing and a
  verify-before-reporting execution loop.
- Adds automatic read-only desktop vision selection for natural requests such as
  "what am I watching?" and "what is on my screen?".
- Keeps the canonical capabilities while directing the model toward
  the smallest correct tool sequence, reducing tool-choice hesitation.
- Enables Open WebUI's built-in DDGS/DuckDuckGo web search globally and by
  default for Hermes and newly connected models.
- Replaces the hardcoded Moondream path with validated OpenAI-compatible cloud
  vision providers selected per Workspace preset.
- Includes a preset builder that wraps any connected API model with the
  canonical Hermes desktop tool, web search, and its chosen vision model.

## V6.1 — safety, resilience, and integration readiness

- Security dashboard with normal, read-only, and emergency-stopped modes.
  Emergency stop cancels active background jobs at the next safe checkpoint and
  blocks new privileged actions until the owner explicitly resumes Hermes.
- Compact memory briefings for task context and exact duplicate detection that
  never deletes anything automatically.
- Plans now show linked task state and can be revised into a new approval-first
  draft after a failure or changed requirement.
- Open WebUI integration readiness reports configured MCP/tool-server connections
  without exposing URLs, credentials, or tokens.
- Optional GPG public-key encrypted backup copies are supported only when the
  owner configures a recipient outside Hermes. No passphrase or private key is
  stored in the assistant.

## V6.0 — memory and planning

- Private SQLite memory store with remember, recall, list, and confirmation-gated
  forgetting. Credential-like content is rejected and memory files are owner-only.
- Approval-first planning with dependency validation, risk classification, plan
  persistence, and execution through the existing checkpointed task engine.
- V6 health, backups, model instructions, and the single canonical Workspace Tool
  are synchronized and covered by regression tests.

## V5.1 — reliability

- Automatic boot for Tailscale, Open WebUI, and both Hermes APIs.
- Two-minute health checks with component-level recovery.
- Unified authenticated health report.
- Daily atomic local backups with 14-backup retention and owner-only permissions.
- Standard-library regression suite covering safety, atomic edits, persistent
  task state, controls, restart recovery, and backup integrity.
- Loopback-only service bindings, bearer authentication, and action audit log.

## V5.2 — managed browser

- Dedicated visible Chrome profile started on demand through a user service.
- Local-only Chrome DevTools connection on `127.0.0.1:9222`.
- Page listing, visible-text snapshots, and numbered interactive elements.
- Navigation, click, type, select, check, submit, back, forward, and reload.
- Expected-text waits, exact-page closing, PNG screenshots, and file upload.
- Explicit confirmation enforced for risky submit/publish/purchase/delete/sign-in
  actions and all local-file uploads.

## V5.3 — persistent work

- SQLite-backed background workflow queue with schedules and desktop completion
  notifications.
- Checkpoint after every successful step and automatic continuation after an
  Action Bridge restart.
- Pause, resume, cancel, retry, bounded attempts, task history, and result logs.
- Safe background steps for code inspection, exact multi-file work, sandboxed
  commands, Git review, webpage reading, bounded downloads, notifications, and
  delays.
- Background jobs intentionally cannot perform GUI clicks or Git commits.

## Verified live

- 122 Open WebUI tool functions use the one canonical Workspace Tool.
- The 55-test regression suite passes; local and Tailscale health endpoints,
  NVIDIA model discovery, and the managed-browser open/read/close lifecycle pass.
- The active WebUI runtime is CPU-only and 2.5 GB, replacing a 7.3 GB CUDA-heavy
  environment and recovering roughly 4.8 GB of disk space.
- Multi-file coding, sandboxed execution, browser reading and structured clicking,
  consequential-action denial, local backups, and forced-restart task recovery pass.
- Open WebUI remains reachable through Tailscale while all privileged APIs and
  Chrome debugging listen only on loopback.

## Intentional limits

- ARM64 wheel resolution and architecture/session simulations pass, but this
  development laptop cannot substitute for a final boot test on physical Pi
  hardware. Use `./install.sh --preflight` on the target before installation.
- The machine must be powered on, awake, and online. Exact global GUI control
  additionally requires an unlocked X11 session; Wayland/headless limitations
  are reported explicitly.
- Hermes does not bypass Linux permissions, passwords, CAPTCHAs, two-factor
  authentication, or website security.
- Background workflows avoid focus-stealing GUI actions. Interactive GUI work is
  performed in the foreground with verification and approval gates.
- Local backups protect against configuration mistakes, not disk failure. Copying
  encrypted backups to another device remains an owner-controlled decision.

#!/usr/bin/env python3
"""Local safety controls, audit summaries, and integration readiness for Hermes."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backup_manager import encryption_status
from task_control import DATABASE as TASK_DATABASE, initialize_database
from platform_support import PROJECT_ROOT, openwebui_data_dir


router = APIRouter(prefix="/governance", tags=["Hermes safety"])
DATA_DIR = __import__("platform_support").DATA_DIR
DATABASE = DATA_DIR / "governance.db"
AUDIT_LOG = PROJECT_ROOT / "logs/actions.jsonl"
OPENWEBUI_DB = openwebui_data_dir() / "webui.db"
SAFE_POSTS = {"/memory/recall", "/plans/draft"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    db = sqlite3.connect(DATABASE, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize_governance():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL)")
        db.execute("INSERT OR IGNORE INTO settings VALUES ('safety_mode', 'normal')")
    os.chmod(DATABASE, 0o600)


def safety_mode() -> str:
    initialize_governance()
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key='safety_mode'").fetchone()
    return row["value"] if row else "normal"


def action_permitted(method: str, path: str) -> tuple[bool, str]:
    """Used by the bridge middleware before privileged actions run."""
    mode = safety_mode()
    if mode == "normal":
        return True, mode
    if path.startswith("/governance"):
        return True, mode
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True, mode
    if mode == "read_only" and path in SAFE_POSTS:
        return True, mode
    return False, mode


def cancel_active_tasks(reason: str) -> int:
    initialize_database()
    with closing(sqlite3.connect(TASK_DATABASE)) as db, db:
        cursor = db.execute(
            "UPDATE tasks SET status='cancelled', error=?, updated_at=? WHERE status IN ('queued','running','paused')",
            (reason[:4000], now()),
        )
    return cursor.rowcount


class SafetyModeRequest(BaseModel):
    mode: str = Field(pattern=r"^(normal|read_only|stopped)$")
    confirmed: bool = False


def record(event: str, details: dict):
    with connect() as db:
        db.execute("INSERT INTO events(created_at,event,details) VALUES(?,?,?)", (now(), event, json.dumps(details)))


@router.get("/dashboard", operation_id="get_security_dashboard")
def get_security_dashboard():
    initialize_governance()
    initialize_database()
    with closing(sqlite3.connect(TASK_DATABASE)) as db, db:
        task_counts = dict(db.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
    audit_counts: dict[str, int] = {}
    last_event = None
    if AUDIT_LOG.is_file():
        lines = AUDIT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        for line in lines:
            try:
                item = json.loads(line)
                status = str(item.get("status", "unknown"))
                audit_counts[status] = audit_counts.get(status, 0) + 1
                last_event = item
            except json.JSONDecodeError:
                continue
    with connect() as db:
        events = [dict(row) for row in db.execute("SELECT created_at,event,details FROM events ORDER BY id DESC LIMIT 10").fetchall()]
    return {
        "safety_mode": safety_mode(),
        "task_counts": task_counts,
        "recent_audit_status_counts": audit_counts,
        "last_audit_event": last_event,
        "recent_safety_events": events,
        "backup_encryption": encryption_status(),
        "emergency_stop_note": "Stopped mode blocks new privileged actions and cancels queued, paused, and running background tasks at the next safe checkpoint.",
    }


@router.post("/safety-mode", operation_id="set_safety_mode")
def set_safety_mode(request: SafetyModeRequest):
    if not request.confirmed:
        raise HTTPException(403, "Changing Hermes safety mode requires explicit confirmation")
    initialize_governance()
    cancelled = 0
    if request.mode == "stopped":
        cancelled = cancel_active_tasks("Cancelled by Hermes emergency stop")
    with connect() as db:
        db.execute("UPDATE settings SET value=? WHERE key='safety_mode'", (request.mode,))
    record("safety_mode_changed", {"mode": request.mode, "cancelled_tasks": cancelled})
    return {"success": True, "safety_mode": request.mode, "cancelled_tasks": cancelled}


@router.post("/emergency-stop", operation_id="emergency_stop_hermes")
def emergency_stop(confirmed: bool = False):
    if not confirmed:
        raise HTTPException(403, "Emergency stop requires explicit confirmation")
    cancelled = cancel_active_tasks("Cancelled by Hermes emergency stop")
    with connect() as db:
        db.execute("UPDATE settings SET value='stopped' WHERE key='safety_mode'")
    record("emergency_stop", {"cancelled_tasks": cancelled})
    return {"success": True, "safety_mode": "stopped", "cancelled_tasks": cancelled}


@router.get("/integrations", operation_id="get_integration_status")
def get_integration_status():
    """Report configuration readiness without exposing connection URLs or secrets."""
    configured = 0
    if OPENWEBUI_DB.is_file():
        with closing(sqlite3.connect(OPENWEBUI_DB)) as db, db:
            row = db.execute("SELECT value FROM config WHERE key='tool_server.connections'").fetchone()
        if row:
            try:
                value = json.loads(row[0])
                configured = len(value) if isinstance(value, list) else len(value or {})
            except (TypeError, ValueError):
                configured = 0
    return {
        "openwebui_mcp_connections": configured,
        "status": "ready_for_configuration" if configured == 0 else "connections_configured",
        "note": "Connect external services inside Open WebUI. Hermes will use only connections you explicitly authorize.",
    }


initialize_governance()

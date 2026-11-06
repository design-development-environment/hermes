#!/usr/bin/env python3
"""Reliability, backup, and live-status endpoints for Hermes Alpha."""

from __future__ import annotations

import json
import shutil
import sqlite3
import mac_commands as subprocess
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter

from backup_manager import create_backup, create_encrypted_backup, encryption_status, list_backups
from model_runtime import public_status as model_runtime_status
from task_control import DATABASE as TASK_DATABASE, initialize_database


router = APIRouter(prefix="/maintenance", tags=["Hermes Alpha reliability"])


def endpoint_status(url: str) -> dict:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Hermes-Alpha"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return {"healthy": 200 <= response.status < 400, "status": response.status}
    except (OSError, urllib.error.URLError) as exc:
        return {"healthy": False, "error": type(exc).__name__}


def service_status(name: str, *, user=True):
    from mac_native import service_status
    return service_status(name)


@router.get("/status", operation_id="get_hermes_health_report")
def get_hermes_health_report():
    initialize_database()
    endpoints = {
        "action_bridge": endpoint_status("http://127.0.0.1:8765/health"),
        "documents": endpoint_status("http://127.0.0.1:8766/health"),
        "open_webui": endpoint_status("http://127.0.0.1:3000/"),
    }
    services = {
        "action_bridge": service_status("hermes-action-bridge.service"),
        "documents": service_status("hermes-documents.service"),
        "open_webui": service_status("open-webui.service"),
        "health_monitor": service_status("hermes-health-monitor.timer"),
        "backup_timer": service_status("hermes-backup.timer"),
    }
    tailscale_binary = shutil.which("tailscale")
    services["tailscale"] = service_status("tailscaled.service", user=False) if tailscale_binary else "not_installed"
    models = model_runtime_status()
    cloud_ready = bool(
        models.get("providers", {}).get("nvidia", {}).get("enabled")
        and models.get("providers", {}).get("nvidia", {}).get("api_key_configured")
    )
    with closing(sqlite3.connect(TASK_DATABASE)) as db, db:
        task_counts = dict(db.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
    disk = shutil.disk_usage(Path.home())
    backups = list_backups()
    if tailscale_binary:
        tailscale = subprocess.run([tailscale_binary, "serve", "status", "--json"], capture_output=True, text=True, timeout=10, check=False)
        try:
            tailscale_data = json.loads(tailscale.stdout) if tailscale.returncode == 0 else {}
        except json.JSONDecodeError:
            tailscale_data = {}
    else:
        tailscale_data = {}
    return {
        "version": "alpha",
        "healthy": (
            all(endpoints[name]["healthy"] for name in ("action_bridge", "documents", "open_webui"))
            and all(services[name] == "active" for name in ("action_bridge", "documents", "open_webui", "health_monitor", "backup_timer"))
            and cloud_ready
        ),
        "endpoints": endpoints,
        "services": services,
        "tasks": task_counts,
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "latest_backup": backups[0] if backups else None,
        "backup_encryption": encryption_status(),
        "models": models,
        "cloud_ready": cloud_ready,
        "tailscale_serve_configured": bool(tailscale_data),
        "remote_access_optional": True,
    }


@router.post("/backup", operation_id="create_hermes_backup")
def create_hermes_backup():
    return create_backup()


@router.get("/backups", operation_id="list_hermes_backups")
def list_hermes_backups():
    return {"backups": list_backups()}


@router.get("/backup-encryption", operation_id="get_backup_encryption_status")
def get_backup_encryption_status():
    return encryption_status()


@router.post("/backup-encrypted", operation_id="create_encrypted_hermes_backup")
def create_encrypted_hermes_backup():
    try:
        return create_encrypted_backup()
    except RuntimeError as exc:
        from fastapi import HTTPException
        raise HTTPException(409, str(exc))

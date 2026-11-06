#!/usr/bin/env python3
"""Atomic local backups for Hermes configuration and persistent data."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from platform_support import DATA_DIR, PROJECT_ROOT, openwebui_data_dir


HOME = Path.home()
PROJECT = PROJECT_ROOT
BACKUP_DIR = HOME / ".local/share/hermes/backups"
OPENWEBUI_DB = openwebui_data_dir() / "webui.db"
OPENWEBUI_VECTOR_DB = openwebui_data_dir() / "vector_db/chroma.sqlite3"
TASK_DB = DATA_DIR / "tasks.db"
MEMORY_DB = DATA_DIR / "memory.db"
PLAN_DB = DATA_DIR / "plans.db"
GOVERNANCE_DB = DATA_DIR / "governance.db"
AGENT_DB = DATA_DIR / "agent.db"
KEEP_BACKUPS = 14
GPG_RECIPIENT = os.environ.get("HERMES_BACKUP_GPG_RECIPIENT", "").strip()
CONFIG_FILES = sorted({
    *PROJECT.glob("*.py"),
    *PROJECT.glob("*.service"),
    *PROJECT.glob("*.timer"),
    *PROJECT.glob("*.md"),
    *PROJECT.glob("*.sh"),
    *PROJECT.glob("*.txt"),
    *PROJECT.glob("*.in"),
    *PROJECT.glob("*.lock"),
    *PROJECT.glob("*.example"),
    PROJECT / "open-webui.service.portable",
    HOME / ".config/systemd/user/open-webui.service",
    HOME / ".config/systemd/user/open-webui.service.d/network.conf",
})
PRIVATE_CONFIG_FILES = sorted({
    openwebui_data_dir().parent / "open-webui.env",
    HOME / ".config/hermes/models.json",
    HOME / ".config/hermes/tool-token",
    HOME / ".config/hermes/vision.env",
})


def sqlite_snapshot(source: Path, destination: Path):
    with closing(sqlite3.connect(source, timeout=30)) as source_db, closing(sqlite3.connect(destination)) as destination_db:
        source_db.backup(destination_db)
        destination_db.commit()


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        return (result.stdout or result.stderr).strip()[:20_000]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{type(exc).__name__}: {exc}"


def encryption_status() -> dict:
    """Encryption is opt-in: the private key never belongs in Hermes or Open WebUI."""
    return {
        "available": shutil.which("gpg") is not None,
        "configured": bool(GPG_RECIPIENT),
        "method": "GPG public-key encryption",
        "note": "Set HERMES_BACKUP_GPG_RECIPIENT in the backup service environment to enable encrypted copies.",
    }


def create_encrypted_backup() -> dict:
    status = encryption_status()
    if not status["available"]:
        raise RuntimeError("GPG is not installed")
    if not status["configured"]:
        raise RuntimeError("Encrypted backup is not configured; a GPG recipient is required")
    source = Path(create_backup()["path"])
    destination = source.with_suffix(source.suffix + ".gpg")
    result = subprocess.run(
        ["gpg", "--batch", "--yes", "--trust-model", "always", "--encrypt", "--recipient", GPG_RECIPIENT, "--output", str(destination), str(source)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode or not destination.is_file():
        destination.unlink(missing_ok=True)
        raise RuntimeError((result.stderr or result.stdout or "GPG encryption failed").strip())
    os.chmod(destination, 0o600)
    return {"success": True, "path": str(destination), "bytes": destination.stat().st_size, "source_backup": str(source)}


def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = BACKUP_DIR / f"hermes-{stamp}.zip"
    counter = 1
    while destination.exists():
        destination = BACKUP_DIR / f"hermes-{stamp}-{counter}.zip"
        counter += 1

    with tempfile.TemporaryDirectory(prefix="hermes-backup-") as temporary_name:
        temporary = Path(temporary_name)
        databases = []
        for source, name in (
            (OPENWEBUI_DB, "openwebui.db"),
            (OPENWEBUI_VECTOR_DB, "chroma.sqlite3"),
            (TASK_DB, "tasks.db"),
            (MEMORY_DB, "memory.db"),
            (PLAN_DB, "plans.db"),
            (GOVERNANCE_DB, "governance.db"),
            (AGENT_DB, "agent.db"),
        ):
            if source.is_file():
                snapshot = temporary / name
                sqlite_snapshot(source, snapshot)
                databases.append(snapshot)
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.6",
            "hostname": os.uname().nodename,
            "git_head": command_output(["git", "-C", str(PROJECT), "rev-parse", "HEAD"]),
            "user_services": command_output(["systemctl", "--user", "is-active", "hermes-action-bridge.service", "hermes-documents.service", "open-webui.service"]),
            "included_databases": [item.name for item in databases],
            "contains_sensitive_openwebui_data": OPENWEBUI_DB.is_file(),
            "contains_private_runtime_configuration": any(item.is_file() for item in PRIVATE_CONFIG_FILES),
            "protection": "owner-only file mode 0600; contains credentials and must remain private",
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        partial = destination.with_suffix(".zip.partial")
        try:
            with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.write(temporary / "manifest.json", "manifest.json")
                for database in databases:
                    archive.write(database, f"data/{database.name}")
                for source in CONFIG_FILES:
                    if source.is_file():
                        if source.is_relative_to(PROJECT):
                            relative = source.relative_to(PROJECT)
                            archive.write(source, f"project/{relative}")
                        else:
                            archive.write(source, f"systemd/{source.name}")
                for source in PRIVATE_CONFIG_FILES:
                    if source.is_file():
                        archive.write(source, f"private/{source.name}")
            os.chmod(partial, 0o600)
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)

    backups = sorted(BACKUP_DIR.glob("hermes-*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    for expired in backups[KEEP_BACKUPS:]:
        expired.unlink(missing_ok=True)
    return {"success": True, "path": str(destination), "bytes": destination.stat().st_size, "retained": min(len(backups), KEEP_BACKUPS)}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.is_dir():
        return []
    results = []
    for path in sorted(BACKUP_DIR.glob("hermes-*.zip"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        results.append({
            "filename": path.name,
            "path": str(path),
            "bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
    return results


if __name__ == "__main__":
    print(json.dumps(create_backup(), indent=2))

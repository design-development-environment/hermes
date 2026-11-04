#!/usr/bin/env python3
"""Persistent checkpointed background workflows for Hermes V5.3."""

from __future__ import annotations

import json
import os
import sqlite3
import platform_commands as subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from browser_control import DownloadRequest, WebPageRequest, download_web_file, read_web_page
from codebase_control import (
    BatchEditRequest,
    BatchWriteRequest,
    CodebaseRequest,
    ReadRangeRequest,
    SearchCodeRequest,
    edit_multiple_files,
    inspect_codebase,
    read_source_range,
    review_git_changes,
    search_code,
    write_multiple_files,
)
from computer_control import TerminalRequest, run_terminal


router = APIRouter(prefix="/tasks", tags=["Hermes V5.3 persistent tasks"])
DATA_DIR = __import__("platform_support").DATA_DIR
DATABASE = DATA_DIR / "tasks.db"
ALLOWED_STEP_TYPES = {
    "command",
    "write_files",
    "edit_files",
    "inspect_codebase",
    "search_code",
    "read_source",
    "git_review",
    "read_web_page",
    "download_web_file",
    "notification",
    "delay",
}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
worker_stop = threading.Event()
worker_thread: threading.Thread | None = None
worker_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    connection = sqlite3.connect(DATABASE, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(*, recover_running: bool = False):
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                current_step INTEGER NOT NULL DEFAULT 0,
                results_json TEXT NOT NULL DEFAULT '[]',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                notify INTEGER NOT NULL DEFAULT 1,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 1
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS task_queue_idx ON tasks(status, scheduled_for, created_at)")
        if recover_running:
            db.execute(
                "UPDATE tasks SET status='queued', error='Action Bridge restarted; resuming from checkpoint', updated_at=? WHERE status='running'",
                (utc_now(),),
            )
    os.chmod(DATABASE, 0o600)


class TaskStep(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    payload: dict = Field(default_factory=dict)
    label: str = Field(default="", max_length=200)


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    steps: list[TaskStep] = Field(min_length=1, max_length=30)
    scheduled_for: datetime | None = None
    notify: bool = True
    max_attempts: int = Field(default=1, ge=1, le=5)


class TaskControlRequest(BaseModel):
    task_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    action: str = Field(pattern=r"^(pause|resume|cancel|retry)$")


def validate_step(step: TaskStep):
    if step.type not in ALLOWED_STEP_TYPES:
        raise HTTPException(400, f"Unsupported background step: {step.type}")
    payload = step.payload
    required = {
        "command": {"program"},
        "write_files": {"root", "files"},
        "edit_files": {"root", "edits"},
        "inspect_codebase": {"root"},
        "search_code": {"root", "query"},
        "read_source": {"path"},
        "git_review": {"root"},
        "read_web_page": {"url"},
        "download_web_file": {"url", "filename"},
        "notification": {"title", "message"},
        "delay": {"seconds"},
    }[step.type]
    missing = required - payload.keys()
    if missing:
        raise HTTPException(400, f"Step {step.type} is missing: {', '.join(sorted(missing))}")
    encoded = json.dumps(payload)
    if len(encoded.encode("utf-8")) > 2_000_000:
        raise HTTPException(413, "A background step exceeds the 2 MB limit")
    try:
        if step.type == "command":
            TerminalRequest(**payload)
        elif step.type == "write_files":
            BatchWriteRequest(**payload)
        elif step.type == "edit_files":
            BatchEditRequest(**payload)
        elif step.type == "inspect_codebase":
            CodebaseRequest(root=payload["root"])
        elif step.type == "search_code":
            SearchCodeRequest(**payload)
        elif step.type == "read_source":
            ReadRangeRequest(**payload)
        elif step.type == "git_review":
            CodebaseRequest(**payload)
        elif step.type == "read_web_page":
            WebPageRequest(**payload)
        elif step.type == "download_web_file":
            DownloadRequest(**payload)
        elif step.type == "notification":
            if not 1 <= len(str(payload["title"])) <= 100 or not 1 <= len(str(payload["message"])) <= 500:
                raise ValueError("Notification title or message has an invalid length")
        elif step.type == "delay":
            if not 1 <= int(payload["seconds"]) <= 300:
                raise ValueError("Delay must be between 1 and 300 seconds")
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid {step.type} step: {exc}")


def row_to_task(row: sqlite3.Row, *, include_results=True):
    task = {
        "task_id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "current_step": row["current_step"],
        "step_count": len(json.loads(row["steps_json"])),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "scheduled_for": row["scheduled_for"],
        "attempts": row["attempts"],
        "max_attempts": row["max_attempts"],
        "notify": bool(row["notify"]),
    }
    if include_results:
        task["steps"] = json.loads(row["steps_json"])
        task["results"] = json.loads(row["results_json"])
    return task


def execute_step(step: dict):
    kind = step["type"]
    payload = step.get("payload", {})
    if kind == "command":
        return run_terminal(TerminalRequest(**payload))
    if kind == "write_files":
        return write_multiple_files(BatchWriteRequest(**payload))
    if kind == "edit_files":
        return edit_multiple_files(BatchEditRequest(**payload))
    if kind == "inspect_codebase":
        request = CodebaseRequest(root=payload["root"])
        return inspect_codebase(request, payload.get("max_files", 500), payload.get("max_depth", 5))
    if kind == "search_code":
        return search_code(SearchCodeRequest(**payload))
    if kind == "read_source":
        return read_source_range(ReadRangeRequest(**payload))
    if kind == "git_review":
        return review_git_changes(CodebaseRequest(**payload))
    if kind == "read_web_page":
        return read_web_page(WebPageRequest(**payload))
    if kind == "download_web_file":
        return download_web_file(DownloadRequest(**payload))
    if kind == "notification":
        subprocess.run(
            ["notify-send", str(payload["title"])[:100], str(payload["message"])[:500]],
            check=True,
            timeout=5,
        )
        return {"success": True}
    if kind == "delay":
        seconds = int(payload["seconds"])
        if not 1 <= seconds <= 300:
            raise ValueError("Delay must be between 1 and 300 seconds")
        time.sleep(seconds)
        return {"success": True, "waited_seconds": seconds}
    raise ValueError(f"Unsupported step: {kind}")


def notify_completion(name: str, status: str):
    try:
        subprocess.run(
            ["notify-send", "Hermes background task", f"{name}: {status}"],
            check=False,
            timeout=5,
        )
    except OSError:
        pass


def claim_task():
    now = utc_now()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM tasks WHERE status='queued' AND scheduled_for<=? ORDER BY scheduled_for, created_at LIMIT 1",
            (now,),
        ).fetchone()
        if not row:
            db.commit()
            return None
        db.execute("UPDATE tasks SET status='running', updated_at=? WHERE id=?", (now, row["id"]))
        db.commit()
        return dict(row)


def run_task(task: dict):
    task_id = task["id"]
    steps = json.loads(task["steps_json"])
    results = json.loads(task["results_json"])
    index = int(task["current_step"])
    while index < len(steps):
        with connect() as db:
            current = db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not current or current["status"] != "running":
            return
        step = steps[index]
        started = utc_now()
        try:
            output = execute_step(step)
            if isinstance(output, dict) and output.get("success") is False:
                raise RuntimeError(output.get("error") or output.get("stderr") or "Step reported failure")
            serialized = json.loads(json.dumps(output, default=str))
            rendered = json.dumps(serialized)
            if len(rendered) > 60_000:
                serialized = {"success": True, "output_truncated": True, "preview": rendered[:60_000]}
            results.append({"step": index + 1, "type": step["type"], "label": step.get("label", ""), "started_at": started, "finished_at": utc_now(), "result": serialized})
            index += 1
            with connect() as db:
                db.execute(
                    "UPDATE tasks SET current_step=?, results_json=?, error=NULL, updated_at=? WHERE id=?",
                    (index, json.dumps(results), utc_now(), task_id),
                )
        except Exception as exc:
            attempts = int(task["attempts"]) + 1
            message = f"{type(exc).__name__}: {exc}"[:4000]
            retry = attempts < int(task["max_attempts"])
            status = "queued" if retry else "failed"
            scheduled = (datetime.now(timezone.utc) + timedelta(seconds=min(60, attempts * 10))).isoformat() if retry else task["scheduled_for"]
            with connect() as db:
                db.execute(
                    "UPDATE tasks SET status=?, attempts=?, error=?, scheduled_for=?, updated_at=? WHERE id=?",
                    (status, attempts, message, scheduled, utc_now(), task_id),
                )
            if not retry and task["notify"]:
                notify_completion(task["name"], "failed")
            return
    with connect() as db:
        current = db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not current or current["status"] != "running":
            return
        db.execute("UPDATE tasks SET status='succeeded', error=NULL, updated_at=? WHERE id=?", (utc_now(), task_id))
    if task["notify"]:
        notify_completion(task["name"], "completed")


def worker_loop():
    while not worker_stop.wait(1):
        try:
            task = claim_task()
            if task:
                run_task(task)
        except Exception as exc:
            print(f"Hermes task worker error: {type(exc).__name__}: {exc}", flush=True)
            worker_stop.wait(2)


def start_task_worker():
    global worker_thread
    initialize_database(recover_running=True)
    with worker_lock:
        if worker_thread and worker_thread.is_alive():
            return
        worker_stop.clear()
        worker_thread = threading.Thread(target=worker_loop, name="hermes-task-worker", daemon=True)
        worker_thread.start()


def stop_task_worker():
    worker_stop.set()
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=5)


@router.post("/create", operation_id="create_background_workflow")
def create_background_workflow(request: CreateTaskRequest):
    initialize_database()
    for step in request.steps:
        validate_step(step)
    scheduled = request.scheduled_for or datetime.now(timezone.utc)
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=datetime.now().astimezone().tzinfo)
    task_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as db:
        db.execute(
            "INSERT INTO tasks(id,name,status,steps_json,current_step,results_json,error,created_at,updated_at,scheduled_for,notify,attempts,max_attempts) VALUES(?,?,?,?,0,'[]',NULL,?,?,?,?,0,?)",
            (task_id, request.name, "queued", json.dumps([step.model_dump() for step in request.steps]), now, now, scheduled.astimezone(timezone.utc).isoformat(), int(request.notify), request.max_attempts),
        )
    return {"success": True, "task_id": task_id, "status": "queued", "scheduled_for": scheduled.isoformat(), "steps": len(request.steps)}


@router.get("", operation_id="list_background_tasks")
def list_background_tasks(status: str = "", limit: int = 20):
    initialize_database()
    limit = max(1, min(limit, 100))
    with connect() as db:
        if status:
            if status not in {"queued", "running", "paused", "succeeded", "failed", "cancelled"}:
                raise HTTPException(400, "Invalid task status")
            rows = db.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"tasks": [row_to_task(row, include_results=False) for row in rows]}


@router.get("/{task_id}", operation_id="get_background_task")
def get_background_task(task_id: str):
    initialize_database()
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Background task was not found")
    return row_to_task(row)


@router.post("/control", operation_id="control_background_task")
def control_background_task(request: TaskControlRequest):
    initialize_database()
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (request.task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Background task was not found")
        status = row["status"]
        if request.action == "pause":
            if status not in {"queued", "running"}:
                raise HTTPException(409, f"Cannot pause a {status} task")
            new_status = "paused"
        elif request.action == "resume":
            if status != "paused":
                raise HTTPException(409, "Only a paused task can be resumed")
            new_status = "queued"
        elif request.action == "cancel":
            if status in TERMINAL_STATUSES:
                raise HTTPException(409, f"Cannot cancel a {status} task")
            new_status = "cancelled"
        else:
            if status not in {"failed", "cancelled"}:
                raise HTTPException(409, "Only a failed or cancelled task can be retried")
            new_status = "queued"
        db.execute(
            "UPDATE tasks SET status=?, error=NULL, scheduled_for=?, updated_at=? WHERE id=?",
            (new_status, utc_now(), utc_now(), request.task_id),
        )
    return {"success": True, "task_id": request.task_id, "status": new_status, "current_step": row["current_step"]}


initialize_database()

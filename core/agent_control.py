#!/usr/bin/env python3
"""Hermes V8 persistent personal-agent layer.

This module coordinates the existing planning, task, browser, memory, and
governance systems.  It stores only owner-controlled metadata locally and never
executes an approval merely because it was approved.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time as clock_time, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import browser_control
import planning_control
import task_control
from governance_control import safety_mode
from platform_support import DATA_DIR, platform_status, writable_roots


router = APIRouter(prefix="/agent", tags=["Hermes V8 personal agent"])
DATABASE = DATA_DIR / "agent.db"
SENSITIVE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|nvapi-[A-Za-z0-9_-]{12,}|Bearer\s+\S+|"
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----|password\s*[:=]|api[_ -]?key\s*[:=])",
    re.IGNORECASE,
)
worker_stop = threading.Event()
worker_thread: threading.Thread | None = None
worker_lock = threading.Lock()


SKILLS = {
    "missions": ("Personal missions", "Turn outcomes into persistent, specialist workstreams.", "core"),
    "memory": ("Personal memory", "Recall user-approved facts and working preferences.", "core"),
    "computer": ("Computer control", "Use files, applications, codebases, terminal, and the desktop.", "core"),
    "managed_browser": ("Managed browser", "Run visible browser workflows with confirmation gates.", "core"),
    "vision": ("Screen understanding", "Analyze a user-requested screenshot with the configured cloud model.", "core"),
    "routines": ("Background routines", "Run approved recurring workflows that survive restarts.", "core"),
    "proactive_briefing": ("Proactive briefing", "Surface deadlines, failures, approvals, and stale goals.", "optional"),
    "gmail": ("Gmail", "Search, summarize, draft, and send only through an authorized connection.", "integration"),
    "calendar": ("Google Calendar", "Read availability and manage events through an authorized connection.", "integration"),
    "drive": ("Google Drive", "Find and work with cloud documents through an authorized connection.", "integration"),
    "github": ("GitHub", "Work with repositories, issues, and pull requests through an authorized connection.", "integration"),
    "notion": ("Notion", "Use personal notes and project spaces through an authorized connection.", "integration"),
    "todoist": ("Todoist", "Manage tasks and recurring reminders through an authorized connection.", "integration"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reject_secrets(value: str):
    if SENSITIVE.search(value):
        raise HTTPException(400, "Hermes refused to store text that resembles a credential or private key")


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    db = sqlite3.connect(DATABASE, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize_agent():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                target_date TEXT,
                progress INTEGER NOT NULL DEFAULT 0,
                milestones_json TEXT NOT NULL DEFAULT '[]',
                linked_plan_id TEXT,
                linked_task_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS goals_status_idx ON goals(status, priority, target_date);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals(status, expires_at);
            CREATE TABLE IF NOT EXISTS routines (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                status TEXT NOT NULL,
                notify INTEGER NOT NULL DEFAULT 1,
                next_run TEXT,
                last_run TEXT,
                last_task_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS routines_due_idx ON routines(status, next_run);
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS skill_state (
                id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS context_snapshots (
                id TEXT PRIMARY KEY,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        timestamp = now()
        for skill_id, (_, _, kind) in SKILLS.items():
            db.execute(
                "INSERT OR IGNORE INTO skill_state(id,enabled,updated_at) VALUES(?,?,?)",
                (skill_id, int(kind == "core"), timestamp),
            )
    os.chmod(DATABASE, 0o600)


def record_event(event_type: str, entity_type: str, entity_id: str | None, summary: str, details: dict | None = None):
    initialize_agent()
    with connect() as db:
        db.execute(
            "INSERT INTO events(event_type,entity_type,entity_id,summary,details_json,created_at) VALUES(?,?,?,?,?,?)",
            (event_type, entity_type, entity_id, summary[:500], json.dumps(details or {}), now()),
        )


class Milestone(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False
    due_date: date | None = None


class CreateGoalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: date | None = None
    milestones: list[Milestone] = Field(default_factory=list, max_length=50)


class GoalIdRequest(BaseModel):
    goal_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


class UpdateGoalRequest(GoalIdRequest):
    progress: int | None = Field(default=None, ge=0, le=100)
    status: Literal["active", "paused", "completed"] | None = None
    target_date: date | None = None
    milestones: list[Milestone] | None = Field(default=None, max_length=50)
    note: str = Field(default="", max_length=1000)


class ArchiveGoalRequest(GoalIdRequest):
    confirmed: bool = False


class MissionWorkstream(BaseModel):
    specialist: Literal["planner", "researcher", "browser", "coder", "operator", "reviewer"]
    objective: str = Field(min_length=1, max_length=500)
    steps: list[planning_control.PlanStep] = Field(min_length=1, max_length=30)


class CreateMissionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    outcome: str = Field(min_length=1, max_length=4000)
    workstreams: list[MissionWorkstream] = Field(min_length=1, max_length=8)
    constraints: str = Field(default="", max_length=2000)
    priority: int = Field(default=4, ge=1, le=5)
    target_date: date | None = None


class ApproveMissionRequest(GoalIdRequest):
    confirmed: bool = False
    notify: bool = True
    max_attempts: int = Field(default=1, ge=1, le=5)


def row_to_goal(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["goal_id"] = result.pop("id")
    result["milestones"] = json.loads(result.pop("milestones_json"))
    return result


@router.post("/goals", operation_id="create_personal_goal")
def create_goal(request: CreateGoalRequest):
    initialize_agent()
    reject_secrets(request.title + " " + request.description)
    goal_id = str(uuid.uuid4())
    timestamp = now()
    with connect() as db:
        db.execute(
            "INSERT INTO goals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (goal_id, request.title.strip(), request.description.strip(), "active", request.priority,
             request.target_date.isoformat() if request.target_date else None, 0,
             json.dumps([item.model_dump(mode="json") for item in request.milestones]), None, None, timestamp, timestamp),
        )
    record_event("created", "goal", goal_id, f"Created goal: {request.title}")
    return {"success": True, "goal_id": goal_id, "status": "active", "message": "Goal created. Add a mission plan when you are ready to act."}


@router.get("/goals", operation_id="list_personal_goals")
def list_goals(status: str = "active", limit: int = 50):
    initialize_agent()
    limit = max(1, min(limit, 100))
    allowed = {"", "active", "paused", "completed", "archived"}
    if status not in allowed:
        raise HTTPException(400, "Invalid goal status")
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM goals WHERE status=? ORDER BY priority DESC,target_date,updated_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM goals ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return {"goals": [row_to_goal(row) for row in rows]}


@router.get("/goals/{goal_id}", operation_id="get_personal_goal")
def get_goal(goal_id: str):
    initialize_agent()
    with connect() as db:
        row = db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Goal was not found")
    result = row_to_goal(row)
    if row["linked_plan_id"]:
        try:
            result["plan"] = planning_control.get_execution_plan(row["linked_plan_id"])
        except HTTPException:
            result["plan"] = None
    return result


@router.post("/goals/update", operation_id="update_personal_goal")
def update_goal(request: UpdateGoalRequest):
    initialize_agent()
    if request.note:
        reject_secrets(request.note)
    with connect() as db:
        row = db.execute("SELECT * FROM goals WHERE id=? AND status!='archived'", (request.goal_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Active goal was not found")
        progress = row["progress"] if request.progress is None else request.progress
        status = request.status or row["status"]
        if status == "completed":
            progress = 100
        milestones = row["milestones_json"] if request.milestones is None else json.dumps([item.model_dump(mode="json") for item in request.milestones])
        target = row["target_date"] if request.target_date is None else request.target_date.isoformat()
        db.execute(
            "UPDATE goals SET status=?,progress=?,target_date=?,milestones_json=?,updated_at=? WHERE id=?",
            (status, progress, target, milestones, now(), request.goal_id),
        )
    record_event("updated", "goal", request.goal_id, request.note or f"Goal is {progress}% complete", {"status": status, "progress": progress})
    return {"success": True, "goal_id": request.goal_id, "status": status, "progress": progress}


@router.post("/goals/archive", operation_id="archive_personal_goal")
def archive_goal(request: ArchiveGoalRequest):
    if not request.confirmed:
        raise HTTPException(403, "Archiving a goal requires explicit confirmation")
    initialize_agent()
    with connect() as db:
        cursor = db.execute("UPDATE goals SET status='archived',updated_at=? WHERE id=? AND status!='archived'", (now(), request.goal_id))
    if cursor.rowcount != 1:
        raise HTTPException(404, "Goal was not found or is already archived")
    record_event("archived", "goal", request.goal_id, "Goal archived")
    return {"success": True, "goal_id": request.goal_id, "status": "archived"}


@router.post("/missions", operation_id="draft_personal_mission")
def create_mission(request: CreateMissionRequest):
    reject_secrets(request.title + " " + request.outcome + " " + request.constraints)
    goal = create_goal(CreateGoalRequest(
        title=request.title,
        description=request.outcome,
        priority=request.priority,
        target_date=request.target_date,
        milestones=[Milestone(title=stream.objective) for stream in request.workstreams],
    ))
    steps: list[planning_control.PlanStep] = []
    specialists = []
    for stream in request.workstreams:
        specialists.append(stream.specialist)
        for step in stream.steps:
            data = step.model_dump()
            data["label"] = f"{stream.specialist}: {step.label or stream.objective}"[:200]
            steps.append(planning_control.PlanStep(**data))
    if len(steps) > 30:
        archive_goal(ArchiveGoalRequest(goal_id=goal["goal_id"], confirmed=True))
        raise HTTPException(400, "A mission may contain at most 30 executable steps")
    try:
        plan = planning_control.draft_execution_plan(planning_control.DraftPlanRequest(
            goal=request.outcome,
            constraints=request.constraints,
            steps=steps,
        ))
    except Exception:
        archive_goal(ArchiveGoalRequest(goal_id=goal["goal_id"], confirmed=True))
        raise
    with connect() as db:
        db.execute("UPDATE goals SET linked_plan_id=?,updated_at=? WHERE id=?", (plan["plan_id"], now(), goal["goal_id"]))
    record_event("mission_drafted", "goal", goal["goal_id"], f"Drafted mission with {len(steps)} steps", {"plan_id": plan["plan_id"], "specialists": specialists})
    return {"success": True, "goal_id": goal["goal_id"], "plan_id": plan["plan_id"], "status": "draft", "specialists": specialists, "risk": plan["risk"], "message": "Review and explicitly approve this mission before it runs."}


@router.post("/missions/approve", operation_id="approve_personal_mission")
def approve_mission(request: ApproveMissionRequest):
    if not request.confirmed:
        raise HTTPException(403, "Running a personal mission requires explicit confirmation")
    goal = get_goal(request.goal_id)
    if not goal.get("linked_plan_id"):
        raise HTTPException(409, "Goal has no mission plan")
    result = planning_control.approve_execution_plan(planning_control.ApprovePlanRequest(
        plan_id=goal["linked_plan_id"], confirmed=True, notify=request.notify, max_attempts=request.max_attempts,
    ))
    with connect() as db:
        db.execute("UPDATE goals SET linked_task_id=?,updated_at=? WHERE id=?", (result["task_id"], now(), request.goal_id))
    record_event("mission_started", "goal", request.goal_id, "Mission queued", {"task_id": result["task_id"]})
    return {"success": True, "goal_id": request.goal_id, "plan_id": result["plan_id"], "task_id": result["task_id"], "status": "queued"}


class ApprovalCreateRequest(BaseModel):
    category: Literal["browser", "communication", "files", "command", "account", "purchase", "general"] = "general"
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1000)
    details: dict = Field(default_factory=dict)
    expires_minutes: int = Field(default=60, ge=1, le=10080)


class ApprovalResolveRequest(BaseModel):
    approval_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    decision: Literal["approved", "rejected"]
    confirmed: bool = False


def expire_approvals(db: sqlite3.Connection):
    db.execute("UPDATE approvals SET status='expired',resolved_at=? WHERE status='pending' AND expires_at<=?", (now(), now()))


@router.post("/approvals", operation_id="request_owner_approval")
def request_approval(request: ApprovalCreateRequest):
    initialize_agent()
    encoded = request.title + " " + request.summary + " " + json.dumps(request.details)
    reject_secrets(encoded)
    approval_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc)
    expires = created + timedelta(minutes=request.expires_minutes)
    with connect() as db:
        db.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,'pending',?,?,NULL)",
            (approval_id, request.category, request.title, request.summary, json.dumps(request.details), expires.isoformat(), created.isoformat()),
        )
    record_event("requested", "approval", approval_id, request.title, {"category": request.category})
    return {"success": True, "approval_id": approval_id, "status": "pending", "expires_at": expires.isoformat(), "note": "Approval records the owner's decision; the requested action must still be performed and verified separately."}


@router.get("/approvals", operation_id="list_owner_approvals")
def list_approvals(status: str = "pending", limit: int = 50):
    initialize_agent()
    if status not in {"", "pending", "approved", "rejected", "expired"}:
        raise HTTPException(400, "Invalid approval status")
    with connect() as db:
        expire_approvals(db)
        if status:
            rows = db.execute("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, max(1, min(limit, 100)))).fetchall()
        else:
            rows = db.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["approval_id"] = item.pop("id")
        item["details"] = json.loads(item.pop("details_json"))
        results.append(item)
    return {"approvals": results}


@router.post("/approvals/resolve", operation_id="resolve_owner_approval")
def resolve_approval(request: ApprovalResolveRequest):
    if not request.confirmed:
        raise HTTPException(403, "Recording an approval decision requires explicit confirmation")
    initialize_agent()
    with connect() as db:
        expire_approvals(db)
        row = db.execute("SELECT * FROM approvals WHERE id=?", (request.approval_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Approval request was not found")
        if row["status"] != "pending":
            raise HTTPException(409, f"Approval request is already {row['status']}")
        db.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=?", (request.decision, now(), request.approval_id))
    record_event("resolved", "approval", request.approval_id, f"Approval {request.decision}", {"decision": request.decision})
    return {"success": True, "approval_id": request.approval_id, "status": request.decision, "execute_automatically": False}


class RoutineCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    schedule_type: Literal["on_demand", "interval", "daily", "weekly"] = "on_demand"
    schedule: dict = Field(default_factory=dict)
    steps: list[task_control.TaskStep] = Field(min_length=1, max_length=30)
    notify: bool = True


class RoutineControlRequest(BaseModel):
    routine_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    action: Literal["enable", "pause", "archive", "run_now"]
    confirmed: bool = False


def validate_schedule(kind: str, schedule: dict):
    if kind == "on_demand":
        return
    if kind == "interval":
        minutes = int(schedule.get("minutes", 0))
        if not 5 <= minutes <= 10080:
            raise HTTPException(422, "Interval routines require 5 to 10080 minutes")
        return
    raw_time = str(schedule.get("time", ""))
    try:
        clock_time.fromisoformat(raw_time)
    except ValueError as exc:
        raise HTTPException(422, "Daily and weekly routines require time as HH:MM") from exc
    if kind == "weekly" and int(schedule.get("weekday", -1)) not in range(7):
        raise HTTPException(422, "Weekly routines require weekday 0 (Monday) through 6 (Sunday)")


def next_run_for(kind: str, schedule: dict, reference: datetime | None = None) -> str | None:
    if kind == "on_demand":
        return None
    reference = (reference or datetime.now().astimezone()).astimezone()
    if kind == "interval":
        return (reference + timedelta(minutes=int(schedule["minutes"]))).astimezone(timezone.utc).isoformat()
    at = clock_time.fromisoformat(str(schedule["time"]))
    candidate = reference.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if kind == "daily":
        if candidate <= reference:
            candidate += timedelta(days=1)
    else:
        days = (int(schedule["weekday"]) - reference.weekday()) % 7
        candidate += timedelta(days=days)
        if candidate <= reference:
            candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc).isoformat()


@router.post("/routines", operation_id="create_agent_routine")
def create_routine(request: RoutineCreateRequest):
    initialize_agent()
    reject_secrets(request.name + " " + request.description + " " + json.dumps(request.schedule))
    validate_schedule(request.schedule_type, request.schedule)
    for step in request.steps:
        task_control.validate_step(step)
    routine_id = str(uuid.uuid4())
    timestamp = now()
    with connect() as db:
        db.execute(
            "INSERT INTO routines VALUES(?,?,?,?,?,?,'draft',?,NULL,NULL,NULL,?,?)",
            (routine_id, request.name, request.description, request.schedule_type, json.dumps(request.schedule),
             json.dumps([step.model_dump() for step in request.steps]), int(request.notify), timestamp, timestamp),
        )
    record_event("created", "routine", routine_id, f"Created routine draft: {request.name}")
    return {"success": True, "routine_id": routine_id, "status": "draft", "message": "Review and explicitly enable the routine before it can run."}


@router.get("/routines", operation_id="list_agent_routines")
def list_routines(status: str = "", limit: int = 50):
    initialize_agent()
    if status not in {"", "draft", "enabled", "paused", "archived"}:
        raise HTTPException(400, "Invalid routine status")
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM routines WHERE status=? ORDER BY updated_at DESC LIMIT ?", (status, max(1, min(limit, 100)))).fetchall()
        else:
            rows = db.execute("SELECT * FROM routines ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["routine_id"] = item.pop("id")
        item["schedule"] = json.loads(item.pop("schedule_json"))
        item["steps"] = json.loads(item.pop("steps_json"))
        item["notify"] = bool(item["notify"])
        results.append(item)
    return {"routines": results}


def queue_routine(row: sqlite3.Row) -> dict:
    steps = [task_control.TaskStep(**item) for item in json.loads(row["steps_json"])]
    task = task_control.create_background_workflow(task_control.CreateTaskRequest(
        name=f"Routine: {row['name']}", steps=steps, notify=bool(row["notify"]), max_attempts=2,
    ))
    schedule = json.loads(row["schedule_json"])
    next_run = next_run_for(row["schedule_type"], schedule)
    with connect() as db:
        db.execute(
            "UPDATE routines SET last_run=?,last_task_id=?,next_run=?,updated_at=? WHERE id=?",
            (now(), task["task_id"], next_run, now(), row["id"]),
        )
    record_event("queued", "routine", row["id"], f"Queued routine: {row['name']}", {"task_id": task["task_id"]})
    return task


@router.post("/routines/control", operation_id="control_agent_routine")
def control_routine(request: RoutineControlRequest):
    if not request.confirmed:
        raise HTTPException(403, "Changing or running a routine requires explicit confirmation")
    initialize_agent()
    with connect() as db:
        row = db.execute("SELECT * FROM routines WHERE id=?", (request.routine_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Routine was not found")
    if request.action == "run_now":
        if row["status"] == "archived":
            raise HTTPException(409, "Archived routines cannot run")
        task = queue_routine(row)
        return {"success": True, "routine_id": request.routine_id, "status": row["status"], "task_id": task["task_id"]}
    status = {"enable": "enabled", "pause": "paused", "archive": "archived"}[request.action]
    next_run = next_run_for(row["schedule_type"], json.loads(row["schedule_json"])) if status == "enabled" else None
    with connect() as db:
        db.execute("UPDATE routines SET status=?,next_run=?,updated_at=? WHERE id=?", (status, next_run, now(), request.routine_id))
    record_event("status_changed", "routine", request.routine_id, f"Routine is {status}")
    return {"success": True, "routine_id": request.routine_id, "status": status, "next_run": next_run}


class ProfileRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    value: str = Field(min_length=1, max_length=2000)
    category: Literal["communication", "work", "coding", "schedule", "notification", "general"] = "general"


class ProfileDeleteRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    confirmed: bool = False


@router.post("/manual", operation_id="save_operator_preference")
def save_preference(request: ProfileRequest):
    initialize_agent()
    reject_secrets(request.key + " " + request.value)
    with connect() as db:
        db.execute(
            "INSERT INTO profile(key,value,category,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,category=excluded.category,updated_at=excluded.updated_at",
            (request.key, request.value.strip(), request.category, now()),
        )
    record_event("updated", "profile", request.key, f"Updated operating preference: {request.key}")
    return {"success": True, "key": request.key, "category": request.category}


@router.get("/manual", operation_id="get_operator_manual")
def get_operator_manual(category: str = ""):
    initialize_agent()
    with connect() as db:
        if category:
            rows = db.execute("SELECT * FROM profile WHERE category=? ORDER BY key", (category,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM profile ORDER BY category,key").fetchall()
    return {"preferences": [dict(row) for row in rows], "note": "This contains only preferences the owner explicitly asked Hermes to save."}


@router.post("/manual/delete", operation_id="delete_operator_preference")
def delete_preference(request: ProfileDeleteRequest):
    if not request.confirmed:
        raise HTTPException(403, "Deleting an operating preference requires explicit confirmation")
    initialize_agent()
    with connect() as db:
        cursor = db.execute("DELETE FROM profile WHERE key=?", (request.key,))
    if cursor.rowcount != 1:
        raise HTTPException(404, "Operating preference was not found")
    record_event("deleted", "profile", request.key, f"Deleted operating preference: {request.key}")
    return {"success": True, "key": request.key, "deleted": True}


class SkillControlRequest(BaseModel):
    skill_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    enabled: bool
    confirmed: bool = False


@router.get("/skills", operation_id="list_agent_skills")
def list_skills():
    initialize_agent()
    with connect() as db:
        state = {row["id"]: bool(row["enabled"]) for row in db.execute("SELECT id,enabled FROM skill_state").fetchall()}
    results = []
    for skill_id, (name, description, kind) in SKILLS.items():
        results.append({"skill_id": skill_id, "name": name, "description": description, "kind": kind, "enabled": state.get(skill_id, kind == "core"), "requires_connection": kind == "integration", "mutable": kind != "core"})
    return {"skills": results}


@router.post("/skills", operation_id="set_agent_skill_enabled")
def set_skill(request: SkillControlRequest):
    if not request.confirmed:
        raise HTTPException(403, "Changing an agent skill requires explicit confirmation")
    if request.skill_id not in SKILLS:
        raise HTTPException(404, "Agent skill was not found")
    if SKILLS[request.skill_id][2] == "core":
        raise HTTPException(409, "Core safety and computer skills cannot be disabled from chat")
    initialize_agent()
    with connect() as db:
        db.execute("UPDATE skill_state SET enabled=?,updated_at=? WHERE id=?", (int(request.enabled), now(), request.skill_id))
    record_event("skill_changed", "skill", request.skill_id, f"Skill {'enabled' if request.enabled else 'disabled'}")
    return {"success": True, "skill_id": request.skill_id, "enabled": request.enabled, "note": "Integration skills still require an authorized Open WebUI connection."}


def recent_files(limit: int = 12) -> list[dict]:
    candidates: list[tuple[float, Path, int]] = []
    visited = 0
    for root in writable_roots():
        if not root.is_dir():
            continue
        for directory, names, files in os.walk(root):
            names[:] = [name for name in names if not name.startswith(".")][:100]
            for filename in files[:200]:
                visited += 1
                if visited > 5000:
                    break
                path = Path(directory) / filename
                try:
                    stat = path.stat()
                except OSError:
                    continue
                candidates.append((stat.st_mtime, path, stat.st_size))
            if visited > 5000:
                break
        if visited > 5000:
            break
    return [
        {"path": str(path), "name": path.name, "modified_at": datetime.fromtimestamp(modified, timezone.utc).isoformat(), "bytes": size}
        for modified, path, size in sorted(candidates, reverse=True)[:limit]
    ]


@router.get("/context", operation_id="get_current_workspace_context")
def current_context(include_recent_files: bool = True, save_snapshot: bool = False):
    context = {"captured_at": now(), "platform": platform_status(), "windows": [], "managed_browser_pages": [], "recent_files": []}
    try:
        import desktop
        context["windows"] = desktop.get_windows()[:100]
    except (SystemExit, Exception) as exc:
        context["windows_unavailable"] = str(exc)[:300]
    try:
        context["managed_browser_pages"] = browser_control.public_pages()[:50]
    except Exception as exc:
        context["managed_browser_unavailable"] = str(exc)[:300]
    if include_recent_files:
        context["recent_files"] = recent_files()
    if save_snapshot:
        initialize_agent()
        snapshot_id = str(uuid.uuid4())
        with connect() as db:
            db.execute("INSERT INTO context_snapshots VALUES(?,?,?)", (snapshot_id, json.dumps(context), now()))
        context["snapshot_id"] = snapshot_id
        record_event("captured", "context", snapshot_id, "Saved an explicit workspace-context snapshot")
    context["privacy"] = "No screen image or file content was captured. Snapshot storage occurs only when save_snapshot is true."
    return context


def proactive_suggestions() -> list[dict]:
    initialize_agent()
    suggestions: list[dict] = []
    today = date.today()
    with connect() as db:
        expire_approvals(db)
        pending = db.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0]
        goals = db.execute("SELECT * FROM goals WHERE status='active' ORDER BY priority DESC,target_date").fetchall()
    if pending:
        suggestions.append({"kind": "approval", "priority": 5, "message": f"{pending} decision{'s' if pending != 1 else ''} waiting for review."})
    for goal in goals:
        if goal["target_date"]:
            due = date.fromisoformat(goal["target_date"])
            days = (due - today).days
            if days < 0:
                suggestions.append({"kind": "overdue_goal", "priority": 5, "goal_id": goal["id"], "message": f"{goal['title']} is overdue by {-days} day(s)."})
            elif days <= 2:
                suggestions.append({"kind": "goal_deadline", "priority": 4, "goal_id": goal["id"], "message": f"{goal['title']} is due in {days} day(s)."})
        updated = parse_datetime(goal["updated_at"])
        if updated and datetime.now(timezone.utc) - updated > timedelta(days=7) and goal["progress"] < 100:
            suggestions.append({"kind": "stale_goal", "priority": 3, "goal_id": goal["id"], "message": f"{goal['title']} has not moved for more than a week."})
    try:
        failed = task_control.list_background_tasks("failed", 5)["tasks"]
        for item in failed:
            suggestions.append({"kind": "failed_task", "priority": 5, "task_id": item["task_id"], "message": f"Review failed task: {item['name']}"})
    except Exception:
        pass
    if not goals:
        suggestions.append({"kind": "start_goal", "priority": 2, "message": "Create one concrete goal so Hermes can track progress instead of waiting for isolated prompts."})
    return sorted(suggestions, key=lambda item: item["priority"], reverse=True)[:20]


@router.get("/briefing", operation_id="get_proactive_briefing")
def get_briefing():
    return {"generated_at": now(), "suggestions": proactive_suggestions(), "automatic_actions_taken": 0, "note": "Hermes surfaces suggestions but never acts on a suggestion without the relevant approval."}


@router.get("/timeline", operation_id="get_personal_timeline")
def get_timeline(limit: int = 50):
    initialize_agent()
    with connect() as db:
        rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json"))
        events.append(item)
    return {"events": events}


@router.get("/command-center", operation_id="get_personal_command_center")
def command_center():
    initialize_agent()
    goals = list_goals("active", 10)["goals"]
    tasks = task_control.list_background_tasks("", 10)["tasks"]
    approvals = list_approvals("pending", 20)["approvals"]
    routines = list_routines("enabled", 20)["routines"]
    manual = get_operator_manual()["preferences"]
    with connect() as db:
        active_goal_count = db.execute("SELECT COUNT(*) FROM goals WHERE status='active'").fetchone()[0]
        pending_approval_count = db.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0]
        enabled_routine_count = db.execute("SELECT COUNT(*) FROM routines WHERE status='enabled'").fetchone()[0]
        preference_count = db.execute("SELECT COUNT(*) FROM profile").fetchone()[0]
    task_control.initialize_database()
    with task_control.connect() as db:
        active_task_count = db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('queued','running','paused')").fetchone()[0]
    return {
        "generated_at": now(),
        "safety_mode": safety_mode(),
        "summary": {
            "active_goals": active_goal_count,
            "active_tasks": active_task_count,
            "pending_approvals": pending_approval_count,
            "enabled_routines": enabled_routine_count,
            "saved_preferences": preference_count,
        },
        "goals": goals,
        "tasks": tasks,
        "approvals": approvals,
        "routines": routines,
        "suggestions": proactive_suggestions(),
        "emergency_stop": "Use emergency_stop_hermes with explicit confirmation to stop queued and running work.",
    }


def process_due_routines():
    initialize_agent()
    if safety_mode() != "normal":
        return
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM routines WHERE status='enabled' AND next_run IS NOT NULL AND next_run<=? ORDER BY next_run LIMIT 5",
            (now(),),
        ).fetchall()
    for row in rows:
        try:
            queue_routine(row)
        except Exception as exc:
            record_event("failed", "routine", row["id"], f"Routine could not be queued: {type(exc).__name__}")
            with connect() as db:
                db.execute("UPDATE routines SET next_run=?,updated_at=? WHERE id=?", (next_run_for(row["schedule_type"], json.loads(row["schedule_json"])), now(), row["id"]))


def agent_worker_loop():
    while not worker_stop.wait(15):
        process_due_routines()


def start_agent_worker():
    global worker_thread
    initialize_agent()
    with worker_lock:
        if worker_thread and worker_thread.is_alive():
            return
        worker_stop.clear()
        process_due_routines()
        worker_thread = threading.Thread(target=agent_worker_loop, name="hermes-agent-worker", daemon=True)
        worker_thread.start()


def stop_agent_worker():
    worker_stop.set()
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=5)


initialize_agent()

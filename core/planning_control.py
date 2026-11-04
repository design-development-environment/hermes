#!/usr/bin/env python3
"""Approval-first planning layer backed by Hermes V5.3 task execution."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from task_control import DATABASE as TASK_DATABASE, CreateTaskRequest, TaskStep, create_background_workflow, validate_step


router = APIRouter(prefix="/plans", tags=["Hermes planning"])
DATA_DIR = __import__("platform_support").DATA_DIR
DATABASE = DATA_DIR / "plans.db"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    db = sqlite3.connect(DATABASE, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def initialize_plans():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                constraints TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                risk_json TEXT NOT NULL,
                status TEXT NOT NULL,
                task_id TEXT,
                parent_plan_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(plans)").fetchall()}
        if "parent_plan_id" not in columns:
            db.execute("ALTER TABLE plans ADD COLUMN parent_plan_id TEXT")
    os.chmod(DATABASE, 0o600)


class PlanStep(TaskStep):
    depends_on: list[int] = Field(default_factory=list, max_length=30)
    estimated_seconds: int = Field(default=30, ge=1, le=1800)


class DraftPlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    steps: list[PlanStep] = Field(min_length=1, max_length=30)
    constraints: str = Field(default="", max_length=2000)


class PlanIdRequest(BaseModel):
    plan_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


class ApprovePlanRequest(PlanIdRequest):
    confirmed: bool = False
    notify: bool = True
    max_attempts: int = Field(default=1, ge=1, le=5)


class RevisePlanRequest(PlanIdRequest):
    steps: list[PlanStep] = Field(min_length=1, max_length=30)
    constraints: str = Field(default="", max_length=2000)


def risk_for(steps: list[PlanStep]) -> dict:
    categories = []
    for step in steps:
        if step.type in {"write_files", "edit_files"}:
            categories.append("filesystem_write")
        elif step.type == "command":
            categories.append("development_command")
        elif step.type == "download_web_file":
            categories.append("download")
        else:
            categories.append("read_only")
    unique = sorted(set(categories))
    return {
        "categories": unique,
        "requires_approval": any(category != "read_only" for category in unique),
        "step_count": len(steps),
        "estimated_seconds": sum(step.estimated_seconds for step in steps),
        "sequential_dependencies": sum(len(step.depends_on) for step in steps),
    }


def row_to_plan(row: sqlite3.Row):
    plan = {
        "plan_id": row["id"],
        "goal": row["goal"],
        "constraints": row["constraints"],
        "steps": json.loads(row["steps_json"]),
        "risk": json.loads(row["risk_json"]),
        "status": row["status"],
        "task_id": row["task_id"],
        "parent_plan_id": row["parent_plan_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["task_id"]:
        with sqlite3.connect(TASK_DATABASE) as db:
            task = db.execute("SELECT status,current_step,error FROM tasks WHERE id=?", (row["task_id"],)).fetchone()
        plan["task"] = dict(zip(("status", "current_step", "error"), task)) if task else None
    return plan


@router.post("/draft", operation_id="draft_execution_plan")
def draft_execution_plan(request: DraftPlanRequest):
    initialize_plans()
    for index, step in enumerate(request.steps, 1):
        validate_step(TaskStep(type=step.type, payload=step.payload, label=step.label))
        if any(dependency < 1 or dependency >= index for dependency in step.depends_on):
            raise HTTPException(400, f"Step {index} has an invalid dependency")
    plan_id = str(uuid.uuid4())
    risk = risk_for(request.steps)
    created = timestamp()
    with connect() as db:
        db.execute(
            "INSERT INTO plans(id,goal,constraints,steps_json,risk_json,status,task_id,parent_plan_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (plan_id, request.goal, request.constraints, json.dumps([step.model_dump() for step in request.steps]), json.dumps(risk), "draft", None, None, created, created),
        )
    return {"success": True, "plan_id": plan_id, "status": "draft", "goal": request.goal, "risk": risk, "message": "Review this plan and approve it before execution."}


@router.get("/{plan_id}", operation_id="get_execution_plan")
def get_execution_plan(plan_id: str):
    initialize_plans()
    with connect() as db:
        row = db.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Execution plan was not found")
    return row_to_plan(row)


@router.get("", operation_id="list_execution_plans")
def list_execution_plans(limit: int = 20):
    initialize_plans()
    limit = max(1, min(limit, 100))
    with connect() as db:
        rows = db.execute("SELECT * FROM plans ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"plans": [row_to_plan(row) for row in rows]}


@router.post("/revise", operation_id="revise_execution_plan")
def revise_execution_plan(request: RevisePlanRequest):
    """Create a new draft from an earlier plan after a failure or changed requirement."""
    initialize_plans()
    with connect() as db:
        original = db.execute("SELECT * FROM plans WHERE id=?", (request.plan_id,)).fetchone()
    if not original:
        raise HTTPException(404, "Original execution plan was not found")
    for index, step in enumerate(request.steps, 1):
        validate_step(TaskStep(type=step.type, payload=step.payload, label=step.label))
        if any(dependency < 1 or dependency >= index for dependency in step.depends_on):
            raise HTTPException(400, f"Step {index} has an invalid dependency")
    plan_id = str(uuid.uuid4())
    created = timestamp()
    risk = risk_for(request.steps)
    constraints = request.constraints or original["constraints"]
    with connect() as db:
        db.execute(
            "INSERT INTO plans(id,goal,constraints,steps_json,risk_json,status,task_id,parent_plan_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (plan_id, original["goal"], constraints, json.dumps([step.model_dump() for step in request.steps]), json.dumps(risk), "draft", None, request.plan_id, created, created),
        )
    return {"success": True, "plan_id": plan_id, "parent_plan_id": request.plan_id, "status": "draft", "risk": risk, "message": "Revised plan is a draft and requires approval before execution."}


@router.post("/approve", operation_id="approve_execution_plan")
def approve_execution_plan(request: ApprovePlanRequest):
    if not request.confirmed:
        raise HTTPException(403, "Executing a plan requires explicit confirmation")
    initialize_plans()
    with connect() as db:
        row = db.execute("SELECT * FROM plans WHERE id=?", (request.plan_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Execution plan was not found")
    if row["status"] != "draft":
        raise HTTPException(409, f"Plan is already {row['status']}")
    stored_steps = json.loads(row["steps_json"])
    task_steps = [TaskStep(type=step["type"], payload=step["payload"], label=step.get("label", "")) for step in stored_steps]
    task = create_background_workflow(CreateTaskRequest(name=row["goal"], steps=task_steps, notify=request.notify, max_attempts=request.max_attempts))
    with connect() as db:
        db.execute("UPDATE plans SET status='queued', task_id=?, updated_at=? WHERE id=?", (task["task_id"], timestamp(), request.plan_id))
    return {"success": True, "plan_id": request.plan_id, "task_id": task["task_id"], "status": "queued", "risk": json.loads(row["risk_json"])}


initialize_plans()

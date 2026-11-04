#!/usr/bin/env python3
"""Private, user-controlled long-term memory for Hermes V6."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/memory", tags=["Hermes memory"])
DATA_DIR = __import__("platform_support").DATA_DIR
DATABASE = DATA_DIR / "memory.db"
SENSITIVE = re.compile(r"(?:sk-[A-Za-z0-9]{20,}|Bearer\s+\S+|-----BEGIN [A-Z ]+PRIVATE KEY-----|password\s*[:=])", re.IGNORECASE)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    db = sqlite3.connect(DATABASE, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize_memory():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                source TEXT NOT NULL,
                importance INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_recalled_at TEXT,
                archived INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS memory_category_idx ON memories(category, archived, updated_at)")
    os.chmod(DATABASE, 0o600)


class RememberRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    category: str = Field(default="general", min_length=1, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="user", min_length=1, max_length=80)
    importance: int = Field(default=3, ge=1, le=5)


class RecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class MemoryIdRequest(BaseModel):
    memory_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    confirmed: bool = False


def clean_tags(tags: list[str]) -> list[str]:
    result = []
    for tag in tags:
        cleaned = " ".join(tag.split())[:80]
        if cleaned and cleaned.casefold() not in {item.casefold() for item in result}:
            result.append(cleaned)
    return result


def normalise(content: str) -> str:
    return " ".join(content.casefold().split())


def row_to_memory(row: sqlite3.Row) -> dict:
    return {
        "memory_id": row["id"],
        "content": row["content"],
        "category": row["category"],
        "tags": json.loads(row["tags_json"]),
        "source": row["source"],
        "importance": row["importance"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_recalled_at": row["last_recalled_at"],
        "archived": bool(row["archived"]),
    }


@router.post("/remember", operation_id="remember_fact")
def remember_fact(request: RememberRequest):
    initialize_memory()
    if SENSITIVE.search(request.content):
        raise HTTPException(400, "Memory rejected because it resembles a password, API key, bearer token, or private key")
    content = request.content.strip()
    category = " ".join(request.category.split())
    normalised = normalise(content)
    timestamp = now()
    tags = clean_tags(request.tags)
    with connect() as db:
        duplicate = db.execute(
            "SELECT id FROM memories WHERE archived=0 AND lower(content)=? AND category=? LIMIT 1",
            (normalised, category),
        ).fetchone()
        if duplicate:
            return {"success": True, "memory_id": duplicate["id"], "category": category, "tags": tags, "duplicate": True}
        memory_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,0)",
            (memory_id, content, category, json.dumps(tags), request.source.strip(), request.importance, timestamp, timestamp, None),
        )
    return {"success": True, "memory_id": memory_id, "category": category, "tags": tags, "duplicate": False}


@router.post("/recall", operation_id="recall_memories")
def recall_memories(request: RecallRequest):
    initialize_memory()
    words = [word for word in re.findall(r"[\w-]{2,}", request.query.casefold())[:12]]
    with connect() as db:
        if words:
            clauses = " OR ".join("(lower(content) LIKE ? OR lower(category) LIKE ? OR lower(tags_json) LIKE ?)" for _ in words)
            params = [value for word in words for value in (f"%{word}%", f"%{word}%", f"%{word}%")]
            rows = db.execute(
                f"SELECT * FROM memories WHERE archived=0 AND ({clauses}) ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (*params, request.limit),
            ).fetchall()
        else:
            rows = []
        timestamp = now()
        for row in rows:
            db.execute("UPDATE memories SET last_recalled_at=? WHERE id=?", (timestamp, row["id"]))
    return {"query": request.query, "memories": [row_to_memory(row) for row in rows]}


@router.get("", operation_id="list_memories")
def list_memories(category: str = "", include_archived: bool = False, limit: int = 50):
    initialize_memory()
    limit = max(1, min(limit, 100))
    with connect() as db:
        clauses = []
        params: list[str | int] = []
        if category:
            clauses.append("category=?")
            params.append(category)
        if not include_archived:
            clauses.append("archived=0")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = db.execute(f"SELECT * FROM memories{where} ORDER BY importance DESC, updated_at DESC LIMIT ?", (*params, limit)).fetchall()
    return {"memories": [row_to_memory(row) for row in rows]}


@router.post("/briefing", operation_id="get_memory_briefing")
def get_memory_briefing(request: RecallRequest):
    """Compact relevant context for a new task; no hidden automatic prompt injection."""
    recalled = recall_memories(request)["memories"]
    return {
        "query": request.query,
        "memory_count": len(recalled),
        "briefing": [
            {"memory_id": item["memory_id"], "content": item["content"], "category": item["category"], "importance": item["importance"]}
            for item in recalled
        ],
    }


@router.get("/duplicates", operation_id="find_duplicate_memories")
def find_duplicate_memories(limit: int = 50):
    """Find exact normalized duplicates for review; this endpoint never changes memory."""
    initialize_memory()
    with connect() as db:
        rows = db.execute("SELECT * FROM memories WHERE archived=0 ORDER BY created_at DESC").fetchall()
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        item = row_to_memory(row)
        grouped.setdefault((item["category"], normalise(item["content"])), []).append(item)
    duplicates = [items for items in grouped.values() if len(items) > 1]
    return {"duplicate_groups": duplicates[:max(1, min(limit, 100))], "group_count": len(duplicates)}


@router.post("/forget", operation_id="forget_memory")
def forget_memory(request: MemoryIdRequest):
    if not request.confirmed:
        raise HTTPException(403, "Forgetting a memory requires explicit confirmation")
    initialize_memory()
    with connect() as db:
        cursor = db.execute("UPDATE memories SET archived=1, updated_at=? WHERE id=? AND archived=0", (now(), request.memory_id))
    if cursor.rowcount != 1:
        raise HTTPException(404, "Memory was not found or is already archived")
    return {"success": True, "memory_id": request.memory_id, "archived": True}


initialize_memory()

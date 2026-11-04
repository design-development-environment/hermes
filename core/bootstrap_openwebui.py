#!/usr/bin/env python3
"""Complete Hermes Workspace setup after the Open WebUI owner signs up."""

from __future__ import annotations

import argparse
import json
import sqlite3

from platform_support import openwebui_data_dir


def readiness() -> dict:
    database = openwebui_data_dir() / "webui.db"
    result = {"database": str(database), "database_exists": database.is_file(), "owner_exists": False}
    if not database.is_file():
        return result
    try:
        with sqlite3.connect(database, timeout=5) as db:
            result["owner_exists"] = db.execute("SELECT 1 FROM user LIMIT 1").fetchone() is not None
    except sqlite3.Error as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Only report readiness")
    args = parser.parse_args()
    state = readiness()
    if args.check:
        print(json.dumps(state, indent=2))
        return 0 if state["owner_exists"] else 1
    if not state["owner_exists"]:
        print(json.dumps({**state, "success": False, "next": "Open http://127.0.0.1:3000, create the owner account, then run this command again."}, indent=2))
        return 2
    from sync_openwebui_tool import main as sync
    sync()
    print(json.dumps({"success": True, "profiles": ["Hermes Alpha", "Hermes Beta", "Hermes Gamma"], "next": "Add the NVIDIA, Deepgram, and ElevenLabs keys in Open WebUI settings, then rerun this command once to connect NVIDIA document embeddings."}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Standard-library regression tests for Hermes V5.3."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import backup_manager
import computer_control
import task_control
from browser_control import PageParser, RISKY_BUTTON_WORDS, valid_url
from codebase_control import BatchEditRequest, edit_multiple_files


class BrowserSafetyTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertEqual(valid_url("https://example.com/path"), "https://example.com/path")
        for unsafe in ("file:///etc/passwd", "javascript:alert(1)", "not-a-url"):
            with self.assertRaises(HTTPException):
                valid_url(unsafe)

    def test_risky_action_detection(self):
        for text in ("Send message", "Buy now", "Delete account", "Sign in"):
            self.assertIsNotNone(RISKY_BUTTON_WORDS.search(text))
        self.assertIsNone(RISKY_BUTTON_WORDS.search("Read more"))

    def test_page_parser_removes_scripts_and_resolves_links(self):
        parser = PageParser("https://example.com/start")
        parser.feed("<title>Test</title><script>bad()</script><p>Hello</p><a href='/next'>Next</a>")
        self.assertEqual(" ".join(parser.title), "Test")
        self.assertIn("Hello", parser.text)
        self.assertNotIn("bad()", parser.text)
        self.assertEqual(parser.links, ["https://example.com/next"])


class AtomicEditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hermes-v53-edit-")
        self.root = Path(self.temporary.name).resolve()
        self.old_roots = computer_control.WRITE_ROOTS
        computer_control.WRITE_ROOTS = (self.root,)
        (self.root / "one.txt").write_text("alpha\n", encoding="utf-8")
        (self.root / "two.txt").write_text("beta\n", encoding="utf-8")

    def tearDown(self):
        computer_control.WRITE_ROOTS = self.old_roots
        self.temporary.cleanup()

    def test_failed_batch_changes_no_files(self):
        request = BatchEditRequest(root=str(self.root), edits=[
            {"path": "one.txt", "old_text": "alpha", "new_text": "changed", "expected_occurrences": 1},
            {"path": "two.txt", "old_text": "missing", "new_text": "changed", "expected_occurrences": 1},
        ])
        with self.assertRaises(HTTPException):
            edit_multiple_files(request)
        self.assertEqual((self.root / "one.txt").read_text(), "alpha\n")
        self.assertEqual((self.root / "two.txt").read_text(), "beta\n")


class PersistentTaskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hermes-v53-task-")
        self.old_data = task_control.DATA_DIR
        self.old_db = task_control.DATABASE
        task_control.DATA_DIR = Path(self.temporary.name)
        task_control.DATABASE = task_control.DATA_DIR / "tasks.db"
        task_control.initialize_database()

    def tearDown(self):
        task_control.DATA_DIR = self.old_data
        task_control.DATABASE = self.old_db
        self.temporary.cleanup()

    def test_checkpointed_task_completes(self):
        request = task_control.CreateTaskRequest(
            name="unit workflow",
            notify=False,
            steps=[
                {"type": "notification", "payload": {"title": "one", "message": "one"}},
                {"type": "notification", "payload": {"title": "two", "message": "two"}},
            ],
        )
        created = task_control.create_background_workflow(request)
        claimed = task_control.claim_task()
        self.assertEqual(claimed["id"], created["task_id"])
        with patch.object(task_control, "execute_step", return_value={"success": True}):
            task_control.run_task(claimed)
        with task_control.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (created["task_id"],)).fetchone()
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(row["current_step"], 2)
        self.assertEqual(len(json.loads(row["results_json"])), 2)

    def test_restart_recovers_running_task(self):
        now = datetime.now(timezone.utc).isoformat()
        with task_control.connect() as db:
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("00000000-0000-0000-0000-000000000001", "restart", "running", "[]", 0, "[]", None, now, now, now, 0, 0, 1),
            )
        task_control.initialize_database(recover_running=True)
        with task_control.connect() as db:
            status = db.execute("SELECT status FROM tasks").fetchone()[0]
        self.assertEqual(status, "queued")

    def test_pause_resume_cancel_and_retry(self):
        request = task_control.CreateTaskRequest(
            name="control workflow",
            notify=False,
            scheduled_for=datetime(2099, 1, 1, tzinfo=timezone.utc),
            steps=[{"type": "delay", "payload": {"seconds": 1}}],
        )
        task_id = task_control.create_background_workflow(request)["task_id"]
        paused = task_control.control_background_task(task_control.TaskControlRequest(task_id=task_id, action="pause"))
        self.assertEqual(paused["status"], "paused")
        resumed = task_control.control_background_task(task_control.TaskControlRequest(task_id=task_id, action="resume"))
        self.assertEqual(resumed["status"], "queued")
        cancelled = task_control.control_background_task(task_control.TaskControlRequest(task_id=task_id, action="cancel"))
        self.assertEqual(cancelled["status"], "cancelled")
        retried = task_control.control_background_task(task_control.TaskControlRequest(task_id=task_id, action="retry"))
        self.assertEqual(retried["status"], "queued")


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hermes-v53-backup-")
        root = Path(self.temporary.name)
        self.originals = {
            "BACKUP_DIR": backup_manager.BACKUP_DIR,
            "OPENWEBUI_DB": backup_manager.OPENWEBUI_DB,
            "OPENWEBUI_VECTOR_DB": backup_manager.OPENWEBUI_VECTOR_DB,
            "TASK_DB": backup_manager.TASK_DB,
            "MEMORY_DB": backup_manager.MEMORY_DB,
            "PLAN_DB": backup_manager.PLAN_DB,
            "GOVERNANCE_DB": backup_manager.GOVERNANCE_DB,
            "AGENT_DB": backup_manager.AGENT_DB,
            "CONFIG_FILES": backup_manager.CONFIG_FILES,
            "PRIVATE_CONFIG_FILES": backup_manager.PRIVATE_CONFIG_FILES,
        }
        backup_manager.BACKUP_DIR = root / "backups"
        backup_manager.OPENWEBUI_DB = root / "webui.db"
        backup_manager.OPENWEBUI_VECTOR_DB = root / "chroma.sqlite3"
        backup_manager.TASK_DB = root / "tasks.db"
        backup_manager.MEMORY_DB = root / "memory.db"
        backup_manager.PLAN_DB = root / "plans.db"
        backup_manager.GOVERNANCE_DB = root / "governance.db"
        backup_manager.AGENT_DB = root / "agent.db"
        config = root / "config.txt"
        config.write_text("safe config", encoding="utf-8")
        backup_manager.CONFIG_FILES = [config]
        private_config = root / "private.env"
        private_config.write_text("SECRET=test", encoding="utf-8")
        backup_manager.PRIVATE_CONFIG_FILES = [private_config]
        for database in (backup_manager.OPENWEBUI_DB, backup_manager.OPENWEBUI_VECTOR_DB, backup_manager.TASK_DB, backup_manager.MEMORY_DB, backup_manager.PLAN_DB, backup_manager.GOVERNANCE_DB, backup_manager.AGENT_DB):
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE sample(value TEXT)")
                db.execute("INSERT INTO sample VALUES('ok')")

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(backup_manager, name, value)
        self.temporary.cleanup()

    def test_backup_is_valid_owner_only_zip(self):
        result = backup_manager.create_backup()
        path = Path(result["path"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with zipfile.ZipFile(path) as archive:
            self.assertIn("manifest.json", archive.namelist())
            self.assertIn("data/openwebui.db", archive.namelist())
            self.assertIn("data/chroma.sqlite3", archive.namelist())
            self.assertIn("private/private.env", archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["version"], "8.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)

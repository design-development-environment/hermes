#!/usr/bin/env python3
"""Focused V6 regression tests using only the standard library."""

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import memory_control
import planning_control
from task_control import TaskStep


class V6MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        memory_control.DATA_DIR = Path(self.tmp.name)
        memory_control.DATABASE = memory_control.DATA_DIR / "memory.db"
        memory_control.initialize_memory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_remember_recall_and_confirmed_archive(self):
        saved = memory_control.remember_fact(memory_control.RememberRequest(
            content="I prefer concise replies", category="preference", tags=["style"]
        ))
        result = memory_control.recall_memories(memory_control.RecallRequest(query="concise replies"))
        self.assertEqual(result["memories"][0]["memory_id"], saved["memory_id"])
        with self.assertRaises(HTTPException) as blocked:
            memory_control.forget_memory(memory_control.MemoryIdRequest(memory_id=saved["memory_id"]))
        self.assertEqual(blocked.exception.status_code, 403)
        archived = memory_control.forget_memory(memory_control.MemoryIdRequest(memory_id=saved["memory_id"], confirmed=True))
        self.assertTrue(archived["archived"])
        self.assertEqual(memory_control.recall_memories(memory_control.RecallRequest(query="concise"))["memories"], [])

    def test_memory_rejects_secret_like_content(self):
        with self.assertRaises(HTTPException) as blocked:
            memory_control.remember_fact(memory_control.RememberRequest(content="api key sk-abcdefghijklmnopqrstuvwxyz123456"))
        self.assertEqual(blocked.exception.status_code, 400)


class V6PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        planning_control.DATA_DIR = Path(self.tmp.name)
        planning_control.DATABASE = planning_control.DATA_DIR / "plans.db"
        planning_control.initialize_plans()

    def tearDown(self):
        self.tmp.cleanup()

    def test_draft_classifies_risk_and_requires_approval(self):
        request = planning_control.DraftPlanRequest(
            goal="inspect a page",
            steps=[planning_control.PlanStep(type="read_web_page", payload={"url": "https://example.com"})],
        )
        drafted = planning_control.draft_execution_plan(request)
        self.assertFalse(drafted["risk"]["requires_approval"])
        with self.assertRaises(HTTPException) as blocked:
            planning_control.approve_execution_plan(planning_control.ApprovePlanRequest(plan_id=drafted["plan_id"]))
        self.assertEqual(blocked.exception.status_code, 403)

    def test_invalid_dependency_is_rejected(self):
        request = planning_control.DraftPlanRequest(
            goal="bad plan",
            steps=[planning_control.PlanStep(type="read_web_page", payload={}, depends_on=[1])],
        )
        with self.assertRaises(HTTPException) as blocked:
            planning_control.draft_execution_plan(request)
        self.assertEqual(blocked.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Focused regression tests for Hermes V6.1 safeguards."""

import tempfile
import unittest
from pathlib import Path

import governance_control
import memory_control
import planning_control


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        governance_control.DATA_DIR = Path(self.tmp.name)
        governance_control.DATABASE = governance_control.DATA_DIR / "governance.db"
        governance_control.initialize_governance()

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_only_blocks_writes_but_allows_inspection_and_plan_drafts(self):
        governance_control.set_safety_mode(governance_control.SafetyModeRequest(mode="read_only", confirmed=True))
        self.assertTrue(governance_control.action_permitted("GET", "/files/read")[0])
        self.assertTrue(governance_control.action_permitted("POST", "/plans/draft")[0])
        self.assertFalse(governance_control.action_permitted("POST", "/code/write")[0])

    def test_stopped_mode_allows_only_the_safety_controls_for_post_requests(self):
        with governance_control.connect() as db:
            db.execute("UPDATE settings SET value='stopped' WHERE key='safety_mode'")
        self.assertTrue(governance_control.action_permitted("POST", "/governance/safety-mode")[0])
        self.assertFalse(governance_control.action_permitted("POST", "/tasks/create")[0])


class MemoryHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        memory_control.DATA_DIR = Path(self.tmp.name)
        memory_control.DATABASE = memory_control.DATA_DIR / "memory.db"
        memory_control.initialize_memory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_duplicate_is_reused_not_inserted_twice(self):
        first = memory_control.remember_fact(memory_control.RememberRequest(content="Prefer concise replies", category="preference"))
        second = memory_control.remember_fact(memory_control.RememberRequest(content="  prefer   concise replies ", category="preference"))
        self.assertEqual(first["memory_id"], second["memory_id"])
        self.assertTrue(second["duplicate"])


class PlanRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        planning_control.DATA_DIR = Path(self.tmp.name)
        planning_control.DATABASE = planning_control.DATA_DIR / "plans.db"
        planning_control.initialize_plans()

    def tearDown(self):
        self.tmp.cleanup()

    def test_revision_is_a_new_unapproved_draft(self):
        original = planning_control.draft_execution_plan(planning_control.DraftPlanRequest(
            goal="Read an example page",
            steps=[planning_control.PlanStep(type="read_web_page", payload={"url": "https://example.com"})],
        ))
        revised = planning_control.revise_execution_plan(planning_control.RevisePlanRequest(
            plan_id=original["plan_id"],
            steps=[planning_control.PlanStep(type="read_web_page", payload={"url": "https://example.org"})],
        ))
        self.assertEqual(revised["status"], "draft")
        self.assertEqual(revised["parent_plan_id"], original["plan_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

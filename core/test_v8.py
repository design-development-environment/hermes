#!/usr/bin/env python3
"""Regression tests for Hermes V8 persistent personal-agent behavior."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import agent_control
import planning_control
import task_control


class PersonalAgentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hermes-v8-")
        self.root = Path(self.temporary.name)
        self.originals = {
            "agent_data": agent_control.DATA_DIR,
            "agent_db": agent_control.DATABASE,
            "task_data": task_control.DATA_DIR,
            "task_db": task_control.DATABASE,
            "plan_data": planning_control.DATA_DIR,
            "plan_db": planning_control.DATABASE,
        }
        agent_control.DATA_DIR = self.root
        agent_control.DATABASE = self.root / "agent.db"
        task_control.DATA_DIR = self.root
        task_control.DATABASE = self.root / "tasks.db"
        planning_control.DATA_DIR = self.root
        planning_control.DATABASE = self.root / "plans.db"
        agent_control.initialize_agent()
        task_control.initialize_database()
        planning_control.initialize_plans()

    def tearDown(self):
        agent_control.DATA_DIR = self.originals["agent_data"]
        agent_control.DATABASE = self.originals["agent_db"]
        task_control.DATA_DIR = self.originals["task_data"]
        task_control.DATABASE = self.originals["task_db"]
        planning_control.DATA_DIR = self.originals["plan_data"]
        planning_control.DATABASE = self.originals["plan_db"]
        self.temporary.cleanup()

    def test_goal_lifecycle_requires_confirmation_to_archive(self):
        created = agent_control.create_goal(agent_control.CreateGoalRequest(
            title="Ship the prototype", description="Finish the verified Linux release",
            target_date=date.today() + timedelta(days=7),
            milestones=[agent_control.Milestone(title="Pass tests")],
        ))
        updated = agent_control.update_goal(agent_control.UpdateGoalRequest(
            goal_id=created["goal_id"], progress=40, note="Core tests pass",
        ))
        self.assertEqual(updated["progress"], 40)
        with self.assertRaises(HTTPException) as blocked:
            agent_control.archive_goal(agent_control.ArchiveGoalRequest(goal_id=created["goal_id"]))
        self.assertEqual(blocked.exception.status_code, 403)
        result = agent_control.archive_goal(agent_control.ArchiveGoalRequest(
            goal_id=created["goal_id"], confirmed=True,
        ))
        self.assertEqual(result["status"], "archived")

    def test_mission_is_drafted_then_explicitly_queued(self):
        drafted = agent_control.create_mission(agent_control.CreateMissionRequest(
            title="Review repository",
            outcome="Review the repository safely",
            workstreams=[agent_control.MissionWorkstream(
                specialist="reviewer", objective="Inspect source",
                steps=[planning_control.PlanStep(type="inspect_codebase", payload={"root": str(self.root)})],
            )],
        ))
        self.assertEqual(drafted["status"], "draft")
        with self.assertRaises(HTTPException):
            agent_control.approve_mission(agent_control.ApproveMissionRequest(goal_id=drafted["goal_id"]))
        queued = agent_control.approve_mission(agent_control.ApproveMissionRequest(
            goal_id=drafted["goal_id"], confirmed=True,
        ))
        self.assertEqual(queued["status"], "queued")
        self.assertTrue(queued["task_id"])

    def test_approval_records_decision_without_execution(self):
        requested = agent_control.request_approval(agent_control.ApprovalCreateRequest(
            category="communication", title="Send draft", summary="Send the prepared email",
        ))
        resolved = agent_control.resolve_approval(agent_control.ApprovalResolveRequest(
            approval_id=requested["approval_id"], decision="approved", confirmed=True,
        ))
        self.assertFalse(resolved["execute_automatically"])
        self.assertEqual(task_control.list_background_tasks("", 10)["tasks"], [])

    def test_routine_is_draft_until_enabled_and_can_run_now(self):
        routine = agent_control.create_routine(agent_control.RoutineCreateRequest(
            name="Daily status", schedule_type="daily", schedule={"time": "09:00"},
            steps=[task_control.TaskStep(type="notification", payload={"title": "Hermes", "message": "Status ready"})],
        ))
        self.assertEqual(routine["status"], "draft")
        enabled = agent_control.control_routine(agent_control.RoutineControlRequest(
            routine_id=routine["routine_id"], action="enable", confirmed=True,
        ))
        self.assertEqual(enabled["status"], "enabled")
        self.assertIsNotNone(enabled["next_run"])
        run = agent_control.control_routine(agent_control.RoutineControlRequest(
            routine_id=routine["routine_id"], action="run_now", confirmed=True,
        ))
        self.assertTrue(run["task_id"])

    def test_due_routines_respect_global_safety_mode(self):
        routine = agent_control.create_routine(agent_control.RoutineCreateRequest(
            name="Safe recurring check", schedule_type="interval", schedule={"minutes": 5},
            steps=[task_control.TaskStep(type="notification", payload={"title": "Hermes", "message": "Ready"})],
        ))
        agent_control.control_routine(agent_control.RoutineControlRequest(
            routine_id=routine["routine_id"], action="enable", confirmed=True,
        ))
        with agent_control.connect() as db:
            db.execute("UPDATE routines SET next_run='2000-01-01T00:00:00+00:00' WHERE id=?", (routine["routine_id"],))
        with patch.object(agent_control, "safety_mode", return_value="stopped"):
            agent_control.process_due_routines()
        self.assertEqual(task_control.list_background_tasks("", 10)["tasks"], [])
        with patch.object(agent_control, "safety_mode", return_value="normal"):
            agent_control.process_due_routines()
        self.assertEqual(len(task_control.list_background_tasks("", 10)["tasks"]), 1)

    def test_secret_preferences_are_rejected_and_core_skills_are_immutable(self):
        with self.assertRaises(HTTPException) as blocked:
            agent_control.save_preference(agent_control.ProfileRequest(
                key="cloud.token", value="password=not-a-real-test-secret",
            ))
        self.assertEqual(blocked.exception.status_code, 400)
        with self.assertRaises(HTTPException) as blocked:
            agent_control.set_skill(agent_control.SkillControlRequest(
                skill_id="computer", enabled=False, confirmed=True,
            ))
        self.assertEqual(blocked.exception.status_code, 409)

    def test_context_is_ephemeral_unless_explicitly_saved(self):
        with patch.object(agent_control, "recent_files", return_value=[]), \
             patch.object(agent_control.browser_control, "public_pages", return_value=[]):
            context = agent_control.current_context(include_recent_files=True, save_snapshot=False)
        self.assertNotIn("snapshot_id", context)
        with agent_control.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0], 0)

    def test_command_center_aggregates_without_taking_action(self):
        agent_control.create_goal(agent_control.CreateGoalRequest(title="One goal"))
        with patch.object(agent_control, "safety_mode", return_value="normal"):
            center = agent_control.command_center()
        self.assertEqual(center["summary"]["active_goals"], 1)
        self.assertIn("suggestions", center)


if __name__ == "__main__":
    unittest.main(verbosity=2)

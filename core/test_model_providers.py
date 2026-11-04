"""Regression tests for replaceable vision providers and Workspace presets."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_runtime
import workspace_preset


class ModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.old_dir = model_runtime.CONFIG_DIR
        self.old_path = model_runtime.CONFIG_PATH
        model_runtime.CONFIG_DIR = Path(self.temporary.name)
        model_runtime.CONFIG_PATH = model_runtime.CONFIG_DIR / "models.json"

    def tearDown(self):
        model_runtime.CONFIG_DIR = self.old_dir
        model_runtime.CONFIG_PATH = self.old_path
        self.temporary.cleanup()

    def test_default_is_cloud_super_vision_and_owner_only(self):
        config = model_runtime.load_config()
        self.assertEqual(config["vision"], {"provider": "nvidia", "model": "nvidia/nemotron-3.5-super-vl-120b-a12b"})
        self.assertEqual(model_runtime.CONFIG_PATH.stat().st_mode & 0o777, 0o600)

    def test_cloud_vision_requires_enablement_and_key(self):
        with self.assertRaises(RuntimeError):
            model_runtime.resolve_vision("openai_compatible", "vision-model")
        config = model_runtime.load_config()
        config["providers"]["openai_compatible"]["enabled"] = True
        model_runtime.save_config(config)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                model_runtime.resolve_vision("openai_compatible", "vision-model")

    def test_nvidia_reuses_matching_openwebui_connection(self):
        database = Path(self.temporary.name) / "webui.db"
        old_database = model_runtime.OPENWEBUI_DB
        model_runtime.OPENWEBUI_DB = database
        try:
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE config(key TEXT PRIMARY KEY,value JSON)")
                db.execute("INSERT INTO config VALUES(?,?)", ("openai.api_base_urls", json.dumps(["https://integrate.api.nvidia.com/v1"])))
                db.execute("INSERT INTO config VALUES(?,?)", ("openai.api_keys", json.dumps(["secret-test-key"])))
            selected = model_runtime.resolve_vision("nvidia", "vision-model")
            self.assertEqual(model_runtime.provider_api_key(selected), "secret-test-key")
        finally:
            model_runtime.OPENWEBUI_DB = old_database

    def test_configuration_change_requires_confirmation(self):
        with self.assertRaises(PermissionError):
            model_runtime.configure_vision("nvidia", "nvidia/nemotron-3.5-super-vl-120b-a12b")


class WorkspacePresetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.old_database = workspace_preset.DATABASE
        workspace_preset.DATABASE = Path(self.temporary.name) / "webui.db"
        with sqlite3.connect(workspace_preset.DATABASE) as db:
            db.execute("CREATE TABLE model(id TEXT PRIMARY KEY,user_id TEXT,base_model_id TEXT,name TEXT,params TEXT,meta TEXT,updated_at INTEGER,created_at INTEGER,is_active BOOLEAN,version_id TEXT)")
            db.execute(
                "INSERT INTO model VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                (
                    "hermes-v4",
                    "owner",
                    "lfm2.5:8b",
                    "Hermes Alpha",
                    json.dumps({"system": "Hermes"}),
                    json.dumps({"capabilities": {}, "toolIds": ["hermes_v4"]}),
                    1,
                    1,
                    True,
                ),
            )

    def tearDown(self):
        workspace_preset.DATABASE = self.old_database
        self.temporary.cleanup()

    def test_preset_inherits_tools_search_and_vision_selection(self):
        result = workspace_preset.create_preset(
            "hermes-api",
            "Hermes API",
            "cloud-model",
            "openai_compatible",
            "vision-model",
            "Cloud preset",
        )
        self.assertTrue(result["created"])
        with sqlite3.connect(workspace_preset.DATABASE) as db:
            base_model, meta_json = db.execute("SELECT base_model_id,meta FROM model WHERE id='hermes-api'").fetchone()
        meta = json.loads(meta_json)
        self.assertEqual(base_model, "cloud-model")
        self.assertEqual(meta["toolIds"], ["hermes_v4"])
        self.assertEqual(meta["hermesVision"]["model"], "vision-model")
        self.assertIn("web_search", meta["defaultFeatureIds"])

    def test_provider_style_model_ids_are_allowed(self):
        result = workspace_preset.create_preset(
            "hermes-cloud",
            "Hermes Cloud",
            "nvidia/model-name",
            "nvidia",
            "nvidia/vision-model",
            "Cloud preset",
        )
        self.assertEqual(result["base_model"], "nvidia/model-name")


if __name__ == "__main__":
    unittest.main(verbosity=2)

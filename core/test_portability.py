"""Regression tests for amd64/arm64 and desktop/headless portability."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import platform_support
import sync_openwebui_tool
import persistent_workflow
import managed_browser_launcher


class PlatformTests(unittest.TestCase):
    def test_architecture_aliases(self):
        self.assertEqual(platform_support.normalized_arch("x86_64"), "amd64")
        self.assertEqual(platform_support.normalized_arch("aarch64"), "arm64")

    def test_debian_ubuntu_and_raspberry_pi_families(self):
        self.assertTrue(platform_support.supported_debian_family({"ID": "ubuntu", "ID_LIKE": "debian"}))
        self.assertTrue(platform_support.supported_debian_family({"ID": "raspbian", "ID_LIKE": "debian"}))
        self.assertTrue(platform_support.supported_debian_family({"ID": "linuxmint", "ID_LIKE": "ubuntu debian"}))
        self.assertFalse(platform_support.supported_debian_family({"ID": "arch", "ID_LIKE": ""}))

    def test_session_detection(self):
        self.assertEqual(platform_support.session_type({"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}), "x11")
        self.assertEqual(platform_support.session_type({"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"}), "wayland")
        with patch.object(platform_support, "_desktop_environment_from_processes", return_value={}):
            self.assertEqual(platform_support.session_type({}), "headless")

    def test_browser_selection_is_cross_architecture(self):
        available = {"/usr/bin/chromium", "/usr/bin/firefox"}
        with patch("platform_support.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if f"/usr/bin/{name}" in available else None):
            self.assertEqual(platform_support.find_browser(), "/usr/bin/chromium")
            self.assertEqual(platform_support.find_browser("firefox"), "/usr/bin/firefox")

    def test_headless_managed_browser_uses_chromium_headless(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(managed_browser_launcher, "DATA_DIR", Path(temporary)), \
             patch.object(managed_browser_launcher, "find_browser", return_value="/usr/bin/chromium"), \
             patch.object(managed_browser_launcher, "graphical_environment", return_value={"XDG_SESSION_TYPE": "headless"}), \
             patch.object(managed_browser_launcher, "platform_status", return_value={"memory_bytes": 2_048_000_000}):
            command, _environment = managed_browser_launcher.command()
            self.assertIn("--headless=new", command)
            self.assertIn("--remote-debugging-address=127.0.0.1", command)
            self.assertIn("--renderer-process-limit=2", command)

    def test_appliance_mode_refuses_headless_browser(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(managed_browser_launcher, "DATA_DIR", Path(temporary)), \
             patch.object(managed_browser_launcher, "find_browser", return_value="/usr/bin/chromium"), \
             patch.object(managed_browser_launcher, "graphical_environment", return_value={"XDG_SESSION_TYPE": "headless"}), \
             patch.dict(os.environ, {"HERMES_REQUIRE_GRAPHICAL": "1"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Headless browser fallback is disabled"):
                managed_browser_launcher.command()

    def test_wayland_refuses_global_x11_input_cleanly(self):
        with patch.object(platform_support, "graphical_environment", return_value={"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}):
            with self.assertRaisesRegex(RuntimeError, "requires an X11 session"):
                platform_support.require_x11_automation()

    def test_service_templates_have_no_personal_home_path(self):
        root = Path(__file__).resolve().parent
        for service in root.glob("*.service"):
            self.assertNotIn("/home/anshul", service.read_text(encoding="utf-8"), service.name)
        self.assertNotIn("/home/anshul", (root / "install.sh").read_text(encoding="utf-8"))

    def test_installer_uses_locked_transactional_cpu_only_environments(self):
        root = Path(__file__).resolve().parent
        installer = (root / "install.sh").read_text(encoding="utf-8")
        lock = (root / "requirements-hermes.lock").read_text(encoding="utf-8")
        amd64_lock = (root / "requirements-openwebui-amd64.lock").read_text(encoding="utf-8")
        arm64_lock = (root / "requirements-openwebui-arm64.lock").read_text(encoding="utf-8")
        self.assertIn("requirements-hermes.lock", installer)
        self.assertIn('requirements-openwebui-${HERMES_ARCH}.lock', installer)
        self.assertIn("open-webui-venv.next", installer)
        self.assertIn("venv --relocatable", installer)
        self.assertIn("appliance.env.example", installer)
        self.assertIn("fastapi==", lock)
        self.assertIn("uvicorn==", lock)
        manifest = (root / "appliance-packages-amd64.txt").read_text(encoding="utf-8")
        installer_lower = installer.casefold()
        self.assertNotIn("intel-microcode\n", manifest)
        self.assertNotIn("i965-va-driver\n", manifest)
        self.assertNotIn("nvidia-driver", manifest)
        self.assertNotIn("intel-microcode", installer_lower)
        self.assertNotIn("i965-va-driver", installer_lower)
        self.assertNotIn("nvidia-driver", installer_lower)
        for webui_lock in (amd64_lock, arm64_lock):
            self.assertIn("download.pytorch.org/whl/cpu", webui_lock)
            self.assertIn("open-webui==0.12.5", webui_lock)
            self.assertIn("torch==2.15.0+cpu", webui_lock)
            self.assertNotIn("nvidia-cuda", webui_lock)

    def test_document_creation_is_headless_atomic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            old_workspace = persistent_workflow.WORKSPACE
            persistent_workflow.WORKSPACE = Path(temporary)
            try:
                first = persistent_workflow.persistent_document_workflow("portable.txt", "hello")
                second = persistent_workflow.persistent_document_workflow("portable.txt", "changed")
                self.assertTrue(first["success"])
                self.assertFalse(second["success"])
                self.assertEqual((Path(temporary) / "portable.txt").read_text(), "hello")
                self.assertFalse(first["desktop_required"])
            finally:
                persistent_workflow.WORKSPACE = old_workspace


class FreshOpenWebUIBootstrapTests(unittest.TestCase):
    def test_fresh_database_gets_tool_and_three_profiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "webui.db"
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE user(id TEXT PRIMARY KEY, role TEXT, created_at INTEGER)")
                db.execute("INSERT INTO user VALUES('owner','admin',1)")
                db.execute("CREATE TABLE tool(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,content TEXT,specs TEXT,meta TEXT,valves TEXT,updated_at INTEGER,created_at INTEGER,version_id TEXT)")
                db.execute("CREATE TABLE model(id TEXT PRIMARY KEY,user_id TEXT,base_model_id TEXT,name TEXT,params TEXT,meta TEXT,updated_at INTEGER,created_at INTEGER,is_active BOOLEAN,version_id TEXT)")
                db.execute("CREATE TABLE config(key TEXT PRIMARY KEY,value TEXT,updated_at INTEGER)")
            old_database = sync_openwebui_tool.DB
            sync_openwebui_tool.DB = database
            try:
                sync_openwebui_tool.main()
            finally:
                sync_openwebui_tool.DB = old_database
            with sqlite3.connect(database) as db:
                specs = json.loads(db.execute("SELECT specs FROM tool WHERE id='hermes_v4'").fetchone()[0])
                profiles = db.execute("SELECT name,base_model_id FROM model ORDER BY name").fetchall()
                config = dict(db.execute("SELECT key,value FROM config").fetchall())
            self.assertGreaterEqual(len(specs), 100)
            self.assertIn("get_platform_compatibility", {item["name"] for item in specs})
            self.assertEqual([name for name, _ in profiles], ["Hermes Alpha", "Hermes Beta", "Hermes Gamma"])
            self.assertEqual(json.loads(config["rag.embedding_model"]), "nvidia/nemotron-3-embed-1b")
            self.assertEqual(json.loads(config["audio.stt.engine"]), "deepgram")
            self.assertEqual(json.loads(config["audio.tts.engine"]), "elevenlabs")
            self.assertEqual(json.loads(config["ui.default_models"]), "hermes-v4")
            self.assertFalse(json.loads(config["ui.default_interface_settings"])["chatBubble"])
            self.assertEqual(len(json.loads(config["ui.prompt_suggestions"])), 4)
            with sqlite3.connect(database) as db:
                profile_meta = json.loads(db.execute("SELECT meta FROM model WHERE id='hermes-v4'").fetchone()[0])
            self.assertEqual(len(profile_meta["suggestion_prompts"]), 4)
            self.assertNotIn("rag.openai.api_key", config)


if __name__ == "__main__":
    unittest.main(verbosity=2)

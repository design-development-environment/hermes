"""Safety and command-routing tests for Cinnamon graphical integration."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import graphical_control as graphical
import app as bridge


class GraphicalControlTests(unittest.TestCase):
    def test_clipboard_read_requires_confirmation(self):
        with self.assertRaises(HTTPException) as error:
            graphical.read_clipboard(graphical.ClipboardReadRequest(confirmed=False))
        self.assertEqual(error.exception.status_code, 403)

    def test_clipboard_read_is_bounded(self):
        result = subprocess.CompletedProcess(["xclip"], 0, stdout="hello", stderr="")
        with patch.object(graphical, "_x11", return_value={}), \
             patch.object(graphical, "_which", return_value="/usr/bin/xclip"), \
             patch.object(graphical, "_run", return_value=result):
            response = graphical.read_clipboard(graphical.ClipboardReadRequest(confirmed=True))
        self.assertEqual(response["text"], "hello")
        self.assertFalse(response["truncated"])

    def test_audio_volume_is_validated_and_uses_default_sink(self):
        with patch.object(graphical, "_which", return_value="/usr/bin/pactl"), \
             patch.object(graphical, "_run") as run:
            response = graphical.set_audio_volume(graphical.VolumeRequest(percent=72))
        run.assert_called_once_with(["/usr/bin/pactl", "set-sink-volume", "@DEFAULT_SINK@", "72%"])
        self.assertEqual(response["percent"], 72)

    def test_media_player_list_allows_no_active_player(self):
        completed = subprocess.CompletedProcess(["playerctl"], 1, stdout="", stderr="No players found")
        with patch.object(graphical, "_which", return_value="/usr/bin/playerctl"), \
             patch.object(graphical, "graphical_environment", return_value={}), \
             patch("graphical_control.subprocess.run", return_value=completed):
            self.assertEqual(graphical.media_players()["players"], [])

    def test_workspace_listing_parses_active_workspace(self):
        output = "0  * DG: 1920x1080 VP: 0,0 WA: 0,0 1920x1040 Main\n1  - DG: 1920x1080 VP: N/A WA: 0,0 1920x1040 Work\n"
        completed = subprocess.CompletedProcess(["wmctrl"], 0, stdout=output, stderr="")
        with patch.object(graphical, "_x11", return_value={}), \
             patch.object(graphical, "_which", return_value="/usr/bin/wmctrl"), \
             patch("graphical_control.subprocess.run", return_value=completed):
            response = graphical.list_workspaces()
        self.assertEqual([item["index"] for item in response["workspaces"]], [0, 1])
        self.assertTrue(response["workspaces"][0]["active"])

    def test_window_move_checks_exact_window_first(self):
        windows = subprocess.CompletedProcess(["wmctrl"], 0, stdout="0x01200001  0 host App.Class Title\n", stderr="")
        moved = subprocess.CompletedProcess(["wmctrl"], 0, stdout="", stderr="")
        with patch.object(graphical, "_x11", return_value={}), \
             patch.object(graphical, "_which", return_value="/usr/bin/wmctrl"), \
             patch("graphical_control.subprocess.run", side_effect=[windows, moved]) as run:
            response = graphical.move_window_to_workspace(
                graphical.WindowWorkspaceRequest(window_id="0x01200001", workspace=2)
            )
        self.assertTrue(response["success"])
        self.assertEqual(run.call_count, 2)

    def test_desktop_lock_requires_confirmation(self):
        with self.assertRaises(HTTPException) as error:
            graphical.lock_desktop(graphical.ConfirmedRequest(confirmed=False))
        self.assertEqual(error.exception.status_code, 403)

    def test_keep_awake_requires_confirmation(self):
        with self.assertRaises(HTTPException) as error:
            graphical.enable_keep_awake(graphical.ConfirmedRequest(confirmed=False))
        self.assertEqual(error.exception.status_code, 403)

    def test_network_status_does_not_request_credentials(self):
        responses = [
            subprocess.CompletedProcess(["nmcli"], 0, stdout="connected:full\n", stderr=""),
            subprocess.CompletedProcess(["nmcli"], 0, stdout="enp3s0:ethernet:connected:Wired connection 1\n", stderr=""),
        ]
        with patch.object(graphical, "_which", return_value="/usr/bin/nmcli"), \
             patch.object(graphical, "_run", side_effect=responses) as run:
            response = graphical.network_status()
        self.assertEqual(response["general"], "connected:full")
        self.assertEqual(len(response["devices"]), 1)
        for call in run.call_args_list:
            self.assertNotIn("password", " ".join(call.args[0]).casefold())

    def test_readiness_accepts_generic_xfce_amd64_without_intel_assumptions(self):
        status = {
            "architecture": "amd64",
            "distribution": {"id": "linuxmint", "debian_family": True},
            "desktop": "XFCE",
            "session": "x11",
            "memory_bytes": 2_000_000_000,
        }
        with patch.object(graphical, "platform_status", return_value=status), \
             patch.object(graphical.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"), \
             patch.object(graphical.Path, "exists", return_value=True):
            report = graphical.graphical_readiness()
        self.assertTrue(report["ready"])
        self.assertTrue(report["checks"]["supported_desktop"])
        self.assertNotIn("i3_3220", report["checks"])

    def test_audit_log_rotates_and_stays_owner_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            audit = Path(temporary) / "actions.jsonl"
            with patch.object(bridge, "AUDIT_LOG", audit), \
                 patch.object(bridge, "AUDIT_MAX_BYTES", 1), \
                 patch.object(bridge, "AUDIT_RETAIN", 2):
                bridge.write_audit("GET", "/first", 200, "one", 2)
                bridge.write_audit("POST", "/second", 200, "two", 3)
            self.assertTrue(audit.is_file())
            self.assertTrue(audit.with_name("actions.jsonl.1").is_file())
            self.assertEqual(audit.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("secret", audit.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

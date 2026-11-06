import json
import os
import tempfile
import unittest
from pathlib import Path

import hermes_client


class HermesClientTests(unittest.TestCase):
    def test_accepts_tailscale_names_and_ips(self):
        self.assertEqual(hermes_client.normalise_host("my-host.tail123.ts.net"), "https://my-host.tail123.ts.net")
        self.assertEqual(hermes_client.normalise_host("https://100.100.100.100"), "https://100.100.100.100")

    def test_rejects_public_and_credentialed_urls(self):
        for value in ("https://example.com", "http://host.tail.ts.net", "https://name:secret@host.tail.ts.net", "https://host.tail.ts.net/admin"):
            with self.assertRaises(ValueError):
                hermes_client.normalise_host(value)

    def test_saved_host_is_private_owner_only(self):
        with tempfile.TemporaryDirectory() as folder:
            previous_dir, previous_file = hermes_client.CONFIG_DIR, hermes_client.CONFIG_FILE
            hermes_client.CONFIG_DIR = Path(folder) / "config"
            hermes_client.CONFIG_FILE = hermes_client.CONFIG_DIR / "connection.json"
            try:
                hermes_client.save_host("https://host.tail.ts.net")
                self.assertEqual(hermes_client.load_host(), "https://host.tail.ts.net")
                self.assertEqual(json.loads(hermes_client.CONFIG_FILE.read_text())["host"], "https://host.tail.ts.net")
                if os.name != "nt":
                    self.assertEqual(hermes_client.CONFIG_FILE.stat().st_mode & 0o777, 0o600)
            finally:
                hermes_client.CONFIG_DIR, hermes_client.CONFIG_FILE = previous_dir, previous_file

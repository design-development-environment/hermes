"""Regression checks for the two Debian package manifests."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class DebianPackageLayoutTests(unittest.TestCase):
    def test_host_and_user_use_distinct_desktop_icon_paths(self):
        host = (ROOT / "packaging" / "build_deb.py").read_text(encoding="utf-8")
        user = (ROOT / "packaging" / "build_user_deb.py").read_text(encoding="utf-8")
        desktop = (ROOT / "client" / "hermes-user.desktop").read_text(encoding="utf-8")
        self.assertIn('apps/hermes.png', host)
        self.assertIn('apps/hermes-user.png', user)
        self.assertIn('Icon=hermes-user', desktop)

    def test_host_setup_reports_the_user_install_result(self):
        setup = (ROOT / "packaging" / "hermes_setup.py").read_text(encoding="utf-8")
        self.assertIn("def install_user(self):", setup)
        self.assertIn("self.command([str(launcher)], self.open_user)", setup)
        self.assertIn("self.after(400, self.install_user)", setup)


if __name__ == "__main__":
    unittest.main()

"""Regression checks for Hermes Alpha smart operator behavior."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class SmartOperatorPromptTests(unittest.TestCase):
    def setUp(self):
        self.instructions = (ROOT / "model_instructions.txt").read_text(encoding="utf-8")

    def test_screen_questions_route_to_vision(self):
        self.assertIn("what am I watching/looking at?", self.instructions)
        self.assertIn("analyze_desktop_screen", self.instructions)

    def test_prompt_requires_verified_tool_results(self):
        self.assertIn("Tool results are facts", self.instructions)
        self.assertIn("Never claim success until a tool returned success", self.instructions)

    def test_prompt_keeps_consequential_action_confirmation(self):
        self.assertIn("Ask before signing in, submitting forms", self.instructions)
        self.assertIn("Approval is required before a plan performs writes", self.instructions)


if __name__ == "__main__":
    unittest.main(verbosity=2)

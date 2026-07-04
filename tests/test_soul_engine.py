"""
Tests for SOUL.md Personality Engine
====================================
"""

import json
import tempfile
import unittest
from pathlib import Path

from hermes.agent.soul_engine import SoulEngine, SoulProfile

class TestSoulEngine(unittest.TestCase):
    def setUp(self):
        # Create temp folder for souls
        self.temp_dir = tempfile.TemporaryDirectory()
        self.souls_path = Path(self.temp_dir.name)
        self.engine = SoulEngine(souls_dir=self.souls_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builtins_creation(self):
        # Engine initialization should create builtins automatically
        profiles = self.engine.list_profiles()
        self.assertIn("default", profiles)
        self.assertIn("coding-mentor", profiles)
        self.assertIn("devops-operator", profiles)
        self.assertIn("research-analyst", profiles)
        self.assertIn("security-auditor", profiles)

    def test_load_and_switch_profile(self):
        # Load coding-mentor
        profile = self.engine.load_profile("coding-mentor")
        self.assertEqual(profile.name, "coding-mentor")
        self.assertEqual(self.engine.active_profile_name, "coding-mentor")
        self.assertIn("Patient", profile.role)

        # Non-existent falls back to default
        fallback = self.engine.load_profile("non-existent-persona")
        self.assertEqual(fallback.name, "default")
        self.assertEqual(self.engine.active_profile_name, "default")

    def test_save_custom_profile(self):
        custom = SoulProfile(
            name="custom-expert",
            role="Quantum Physics Expert",
            tone="Highly formal",
            communication_style="Mathematical and precise",
            guardrails=["Only discuss verified quantum phenomena"],
            expertise_areas=["quantum mechanics", "particle physics"]
        )
        self.engine.save_custom_profile(custom)
        
        # Verify it lists
        profiles = self.engine.list_profiles()
        self.assertIn("custom-expert", profiles)

        # Load it
        loaded = self.engine.load_profile("custom-expert")
        self.assertEqual(loaded.role, "Quantum Physics Expert")
        self.assertEqual(loaded.expertise_areas, ["quantum mechanics", "particle physics"])

    def test_render_soul_prompt(self):
        prompt = self.engine.render_soul_prompt("devops-operator")
        self.assertIn("DEVOPS-OPERATOR", prompt)
        self.assertIn("DevOps & Infrastructure Operator", prompt)
        self.assertIn("Terse", prompt)
        self.assertIn("Always warn the user before destructive commands", prompt)

if __name__ == "__main__":
    unittest.main()

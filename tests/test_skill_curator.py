"""
Tests for Skill Curator Lifecycle Manager
=========================================
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from hermes.skills.curator import SkillCurator
from hermes.skills.curator_metrics import SkillMetricsStore

class TestSkillCurator(unittest.TestCase):
    def setUp(self):
        # Create temp environment
        self.temp_dir = tempfile.TemporaryDirectory()
        self.skills_path = Path(self.temp_dir.name) / "skills"
        self.skills_path.mkdir(parents=True, exist_ok=True)
        
        # Temp metrics database
        self.db_path = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics_store = SkillMetricsStore(db_path=self.db_path)
        self.curator = SkillCurator(skills_dir=self.skills_path, metrics_store=self.metrics_store)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_dummy_skill(self, name: str, markdown_content: str, last_modified_days_ago: int = 0) -> Path:
        skill_dir = self.skills_path / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(markdown_content, encoding="utf-8")
        
        # Adjust mtime
        if last_modified_days_ago > 0:
            past_time = datetime.now().timestamp() - (last_modified_days_ago * 86400)
            os.utime(str(skill_md), (past_time, past_time))
            
        return skill_dir

    def test_metrics_store(self):
        # Check defaults
        metrics = self.metrics_store.get_metrics("non_existent")
        self.assertEqual(metrics["use_count"], 0)
        self.assertFalse(metrics["pinned"])

        # Track actions
        self.metrics_store.record_view("my_skill")
        self.metrics_store.record_use("my_skill")
        self.metrics_store.record_use("my_skill")
        self.metrics_store.record_patch("my_skill")
        self.metrics_store.set_pinned("my_skill", True)

        metrics = self.metrics_store.get_metrics("my_skill")
        self.assertEqual(metrics["view_count"], 1)
        self.assertEqual(metrics["use_count"], 2)
        self.assertEqual(metrics["patch_count"], 1)
        self.assertTrue(metrics["pinned"])
        self.assertIsNotNone(metrics["last_used_at"])

    def test_evaluate_and_archive(self):
        # Create active skill
        self._create_dummy_skill("active_skill", "# Active Skill\nThis handles active tasks.", last_modified_days_ago=0)
        self.metrics_store.record_use("active_skill")

        # Create stale skill (modified 45 days ago)
        self._create_dummy_skill("stale_skill", "# Stale Skill\nThis handles stale tasks.", last_modified_days_ago=45)

        # Create archivable skill (modified 100 days ago)
        self._create_dummy_skill("old_skill", "# Old Skill\nThis handles historical tasks.", last_modified_days_ago=100)

        # Evaluate skills
        eval_active = self.curator.evaluate_skill(self.skills_path / "active_skill")
        self.assertEqual(eval_active["status"], "Active")

        eval_stale = self.curator.evaluate_skill(self.skills_path / "stale_skill")
        self.assertEqual(eval_stale["status"], "Stale")

        eval_old = self.curator.evaluate_skill(self.skills_path / "old_skill")
        self.assertEqual(eval_old["status"], "Archive")

        # Run curator pass
        res = self.curator.run_curator_pass()
        self.assertEqual(res["archived_count"], 1)
        
        # Check that old_skill was moved to .archive
        self.assertFalse((self.skills_path / "old_skill").exists())
        self.assertTrue((self.skills_path / ".archive" / "old_skill").exists())
        self.assertTrue((self.skills_path / ".archive" / "old_skill" / "SKILL.md").exists())

        # Check REPORT.md was created
        report_file = self.skills_path / "REPORT.md"
        self.assertTrue(report_file.exists())
        report_content = report_file.read_text(encoding="utf-8")
        self.assertIn("stale_skill", report_content)
        self.assertIn("active_skill", report_content)

        # Restore the skill
        success = self.curator.restore_skill("old_skill")
        self.assertTrue(success)
        self.assertTrue((self.skills_path / "old_skill").exists())
        self.assertFalse((self.skills_path / ".archive" / "old_skill").exists())

    def test_duplicate_detection(self):
        # Create two very similar skills
        content_a = "# Git Deploy Skill\nRun git commit and push changes to remote origin production main branches."
        content_b = "# Git Deploy Skill\nRun git commit and push changes to remote origin production main repository."
        content_c = "# Weather API Skill\nFetches current forecast temperature rain metrics from open source api."

        self._create_dummy_skill("git_deploy_a", content_a)
        self._create_dummy_skill("git_deploy_b", content_b)
        self._create_dummy_skill("weather_api", content_c)

        duplicates = self.curator.find_duplicate_skills()
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0][0], "git_deploy_a")
        self.assertEqual(duplicates[0][1], "git_deploy_b")
        self.assertGreaterEqual(duplicates[0][2], 0.65)

if __name__ == "__main__":
    unittest.main()

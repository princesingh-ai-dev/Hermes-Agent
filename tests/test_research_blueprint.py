"""
Tests for Research Blueprint System
===================================
"""

import os
import json
import tempfile
import asyncio
import unittest
from pathlib import Path

from hermes.scheduler.research_blueprint import (
    ResearchBlueprint, ResearchItem, BlueprintRegistry, BlueprintRunner
)

class MockScraper:
    def __init__(self, source_name, items):
        self.source_name = source_name
        self.items = items

    def scrape(self, keywords, max_items):
        return self.items


class TestResearchBlueprint(unittest.TestCase):
    def setUp(self):
        # Temp database file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_blueprints.db")
        self.registry = BlueprintRegistry(db_path=self.db_path)
        self.runner = BlueprintRunner(registry=self.registry)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_registry_crud(self):
        # Registry built-ins registration
        self.registry.register_builtins()
        all_bps = self.registry.list_all()
        self.assertGreaterEqual(len(all_bps), 4)
        
        # Get one builtin
        bp = self.registry.get("ai-news-digest")
        self.assertIsNotNone(bp)
        self.assertEqual(bp.name, "ai-news-digest")

        # Save custom blueprint
        custom = ResearchBlueprint(
            name="custom-research",
            description="Scrape custom topics",
            sources=["arxiv"],
            keywords=["deep learning"],
            schedule="0 12 * * *"
        )
        self.registry.save(custom)

        # Get and verify
        loaded = self.registry.get("custom-research")
        self.assertEqual(loaded.description, "Scrape custom topics")
        self.assertEqual(loaded.keywords, ["deep learning"])

        # Delete
        success = self.registry.delete("custom-research")
        self.assertTrue(success)
        self.assertIsNone(self.registry.get("custom-research"))

    def test_record_runs(self):
        self.registry.register_builtins()
        run_id = self.registry.record_run(
            blueprint_name="ai-news-digest",
            items_found=5,
            status="completed",
            report_path="/tmp/report.md"
        )
        self.assertGreater(run_id, 0)

        history = self.registry.get_run_history("ai-news-digest")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["items_found"], 5)
        self.assertEqual(history[0]["status"], "completed")
        self.assertEqual(history[0]["report_path"], "/tmp/report.md")

    def test_runner_execution(self):
        bp = ResearchBlueprint(
            name="test-run",
            description="Testing execution pipeline",
            sources=["arxiv", "github"],
            keywords=["transformer", "attention"],
            output_format="json"
        )
        self.registry.save(bp)

        # Inject mock scrapers
        arxiv_items = [
            ResearchItem("Attention Is All You Need", "http://arxiv.org/abs/1706.03762", "Transformers study.", 0.9, "arxiv"),
            ResearchItem("BERT: Pre-training of Deep Bidirectional Transformers", "http://arxiv.org/abs/1810.04805", "BERT paper.", 0.85, "arxiv")
        ]
        github_items = [
            ResearchItem("huggingface/transformers", "https://github.com/huggingface/transformers", "Transformers library.", 0.95, "github")
        ]

        self.runner._scrapers = {
            "arxiv": MockScraper("arxiv", arxiv_items),
            "github": MockScraper("github", github_items)
        }

        # Run execute sync
        res = self.runner.execute_sync(bp)
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["items_found"], 3)
        self.assertTrue(Path(res["report_path"]).exists())

        # Verify output file content is valid JSON
        with open(res["report_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["metadata"]["blueprint_name"], "test-run")
            self.assertEqual(len(data["items"]), 3)

        # Clean up output file
        if os.path.exists(res["report_path"]):
            os.remove(res["report_path"])

if __name__ == "__main__":
    unittest.main()

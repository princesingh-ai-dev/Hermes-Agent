"""
Tests for Hybrid Cognitive Memory Store
=======================================
"""

import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from hermes.memory.hybrid_store import HybridMemoryManager

class TestHybridMemoryStore(unittest.TestCase):
    def setUp(self):
        # Create temp folder for DB
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_hybrid.db")
        self.manager = HybridMemoryManager(db_path=self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_knowledge_graph(self):
        # Add nodes and relationships
        self.manager.add_relation("jarvis", "system", "is_a")
        self.manager.add_relation("prince", "jarvis", "created")

        # Query connections
        edges = self.manager.query_neighborhood("jarvis")
        self.assertEqual(len(edges), 2)
        
        # Verify edge structures
        edge_data = {(src, rel, tgt) for src, rel, tgt in edges}
        self.assertIn(("jarvis", "is_a", "system"), edge_data)
        self.assertIn(("prince", "created", "jarvis"), edge_data)

    def test_temporal_decay(self):
        # Record immediate memory access
        self.manager.record_memory_access("m1", "High importance context payload.")
        
        # Verify it is active (0 days inactive -> score = 1.0)
        active = self.manager.retrieve_active_memories()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["key"], "m1")
        self.assertGreaterEqual(active[0]["score"], 0.99)

        # Force a stale record manually inside database to mock time delay
        now = datetime.now(timezone.utc)
        past_time = (now - timedelta(days=100)).isoformat()
        
        import sqlite3 as sqlite
        with sqlite.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE temporal_memories SET last_accessed_at = ? WHERE memory_key = 'm1'",
                (past_time,)
            )
            conn.commit()

        # Score on 100 days decay should drop below 0.1 and prune it automatically
        active_pruned = self.manager.retrieve_active_memories(decay_threshold=0.1)
        self.assertEqual(len(active_pruned), 0)

        # Verify it was deleted from db
        with sqlite.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM temporal_memories WHERE memory_key = 'm1'").fetchone()
            self.assertEqual(row[0], 0)

if __name__ == "__main__":
    unittest.main()

"""
Skill Curator Metrics Database
==============================
Tracks usage metrics for skills (views, invocations, edits) to enable
intelligent pruning and archiving by the Skill Curator.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger("hermes.skills.curator_metrics")

class SkillMetricsStore:
    """
    SQLite-based persistent store for tracking skill usage metrics.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            hermes_home = Path.home() / ".hermes"
            hermes_home.mkdir(parents=True, exist_ok=True)
            db_path = str(hermes_home / "skill_metrics.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_metrics (
                    skill_name TEXT PRIMARY KEY,
                    view_count INTEGER DEFAULT 0,
                    use_count INTEGER DEFAULT 0,
                    patch_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT,
                    pinned INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def record_view(self, skill_name: str):
        """Record that a skill's instructions were viewed by the agent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO skill_metrics (skill_name, view_count)
                VALUES (?, 1)
                ON CONFLICT(skill_name) DO UPDATE SET
                    view_count = view_count + 1
            """, (skill_name,))
            conn.commit()

    def record_use(self, skill_name: str):
        """Record that a skill was executed/invoked."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO skill_metrics (skill_name, use_count, last_used_at)
                VALUES (?, 1, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    use_count = use_count + 1,
                    last_used_at = ?
            """, (skill_name, now, now))
            conn.commit()

    def record_patch(self, skill_name: str):
        """Record that a skill was edited or evolved (e.g. by DSPy)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO skill_metrics (skill_name, patch_count)
                VALUES (?, 1)
                ON CONFLICT(skill_name) DO UPDATE SET
                    patch_count = patch_count + 1
            """, (skill_name,))
            conn.commit()

    def set_pinned(self, skill_name: str, pinned: bool = True):
        """Pin a skill to protect it from auto-pruning."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO skill_metrics (skill_name, pinned)
                VALUES (?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    pinned = ?
            """, (skill_name, 1 if pinned else 0, 1 if pinned else 0))
            conn.commit()

    def get_metrics(self, skill_name: str) -> Dict:
        """Retrieve metrics for a single skill."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT view_count, use_count, patch_count, created_at, last_used_at, pinned
                FROM skill_metrics WHERE skill_name = ?
            """, (skill_name,)).fetchone()
        
        if row:
            return {
                "skill_name": skill_name,
                "view_count": row[0],
                "use_count": row[1],
                "patch_count": row[2],
                "created_at": row[3],
                "last_used_at": row[4],
                "pinned": bool(row[5])
            }
        return {
            "skill_name": skill_name,
            "view_count": 0,
            "use_count": 0,
            "patch_count": 0,
            "created_at": None,
            "last_used_at": None,
            "pinned": False
        }

    def list_all_metrics(self) -> List[Dict]:
        """List metrics for all recorded skills."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT skill_name, view_count, use_count, patch_count, created_at, last_used_at, pinned
                FROM skill_metrics
            """).fetchall()
        return [
            {
                "skill_name": r[0],
                "view_count": r[1],
                "use_count": r[2],
                "patch_count": r[3],
                "created_at": r[4],
                "last_used_at": r[5],
                "pinned": bool(r[6])
            }
            for r in rows
        ]

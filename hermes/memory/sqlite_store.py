import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

class LearningLoop:
    """
    After each task:
    1. Analyze what worked and what didn't
    2. Extract reusable skill (if complex enough)
    3. Store in SQLite with FTS5 indexing
    4. Compare against existing skills
    5. If better approach found: update skill
    6. Periodically: GEPA self-evolution pass
    """
    def __init__(self, db_path: str = "hermes_learning.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite with FTS5 virtual tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                platform TEXT,
                user_id TEXT,
                query TEXT,
                response TEXT,
                tools_used TEXT, -- JSON array
                success BOOLEAN,
                duration_seconds REAL
            )
        """)
        # FTS5 for full-text search across ALL sessions
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS session_fts USING fts5(
                query, response, tools_used,
                content='sessions',
                content_rowid='id'
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                instructions TEXT, -- Markdown skill document
                examples TEXT, -- JSON array of example inputs/outputs
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_tool_calls REAL,
                created_at TEXT,
                updated_at TEXT,
                version INTEGER DEFAULT 1
            )
        """)
        # FTS5 for skill search
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(
                name, description, instructions,
                content='skills',
                content_rowid='id'
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_model (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT, -- preference, goal, style, fact
                confidence REAL DEFAULT 1.0,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def process_task_result(self, query: str, response: str, tools_used: List[str],
                            success: bool, duration: float, user_id: str = "default"):
        """Called after every task completion."""
        # 1. Store session
        session_id = self._store_session(query, response, tools_used, success, duration, user_id)
        
        # 2. If successful and complex (>3 tools), auto-extract skill
        if success and len(tools_used) > 3:
            self._maybe_create_skill(query, response, tools_used)
            
        # 3. If failed, search for similar past failures and create troubleshooting skill
        if not success:
            self._handle_failure(query, tools_used)
            
        # 4. Update user model
        self._update_user_model(query, response, user_id)

    def _store_session(self, query, response, tools_used, success, duration, user_id) -> int:
        """Store session with FTS5 indexing for cross-session search."""
        cursor = self.conn.execute(
            """INSERT INTO sessions (timestamp, platform, user_id, query, response, tools_used, success, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.utcnow().isoformat(), "cli", user_id, query, response,
             json.dumps(tools_used), success, duration)
        )
        session_id = cursor.lastrowid
        self.conn.execute(
            """INSERT INTO session_fts(rowid, query, response, tools_used) VALUES (?, ?, ?, ?)""",
            (session_id, query, response, json.dumps(tools_used))
        )
        self.conn.commit()
        return session_id

    def search_memory(self, query: str, limit: int = 5) -> List[Dict]:
        """
        FTS5 search across ALL past sessions.
        This is how the agent "remembers" things from weeks ago.
        """
        results = self.conn.execute(
            """SELECT sessions.* FROM sessions 
               JOIN session_fts ON sessions.id = session_fts.rowid 
               WHERE session_fts MATCH ? 
               ORDER BY rank 
               LIMIT ?""",
            (query, limit)
        ).fetchall()
        return [dict(zip([col[0] for col in self.conn.execute("SELECT * FROM sessions LIMIT 0").description], r)) for r in results]

    def _update_user_model(self, query, response, user_id):
        pass # Placeholder for user modeling

    def _handle_failure(self, query, tools_used):
        pass # Placeholder for failure handler
        
    def _maybe_create_skill(self, query: str, response: str, tools_used: List[str]):
        """
        Auto-generate a skill from a successful complex task.
        """
        existing = self._search_similar_skills(query)
        if existing:
            if self._is_better_approach(existing, tools_used):
                self._update_skill(existing["id"], query, response, tools_used)
        else:
            skill_name = self._generate_skill_name(query)
            instructions = self._generate_skill_instructions(query, response, tools_used)
            self._create_skill(skill_name, instructions, tools_used)
            
    def _search_similar_skills(self, query: str):
        return None # Placeholder
        
    def _is_better_approach(self, existing, tools_used):
        return False
        
    def _update_skill(self, skill_id, query, response, tools_used):
        pass
        
    def _generate_skill_name(self, query):
        return "skill_" + str(int(datetime.utcnow().timestamp()))
        
    def _generate_skill_instructions(self, query, response, tools_used):
        return f"To handle {query}, use tools: {tools_used}"
        
    def _create_skill(self, name, instructions, tools_used):
        cursor = self.conn.execute(
            """INSERT INTO skills (name, description, instructions, examples, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, "Auto-generated skill", instructions, json.dumps([]), datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        skill_id = cursor.lastrowid
        self.conn.execute(
            """INSERT INTO skill_fts(rowid, name, description, instructions) VALUES (?, ?, ?, ?)""",
            (skill_id, name, "Auto-generated skill", instructions)
        )
        self.conn.commit()

    def get_relevant_skills(self, query: str) -> List[Dict]:
        """Dynamically load only relevant skills for the current task."""
        sanitized = "".join([c for c in query if c.isalnum() or c.isspace()])
        if not sanitized.strip():
            return []
        match_query = " OR ".join(sanitized.split())
        try:
            results = self.conn.execute(
                """SELECT skills.* FROM skills 
                   JOIN skill_fts ON skills.id = skill_fts.rowid 
                   WHERE skill_fts MATCH ? 
                   ORDER BY rank 
                   LIMIT 5""",
                (match_query,)
            ).fetchall()
            return [dict(zip([col[0] for col in self.conn.execute("SELECT * FROM skills LIMIT 0").description], r)) for r in results]
        except sqlite3.OperationalError:
            return []

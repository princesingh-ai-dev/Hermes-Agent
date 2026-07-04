"""
Hybrid Cognitive Memory Manager
================================
Implements the multi-tier cognitive memory architecture from the JARVIS evolution blueprint.

Includes:
1. Temporal Cache (SQLite table) with exponential decay factor scoring.
2. Knowledge Graph (SQLite tables) tracking nodes and relation triples.
"""

import sqlite3
import math
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger("hermes.memory.hybrid_store")

class HybridMemoryManager:
    """
    Manages the Knowledge Graph and Temporal Cache SQLite databases,
    applying exponential decay calculations for memory pruning.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            hermes_home = Path.home() / ".hermes"
            hermes_home.mkdir(parents=True, exist_ok=True)
            db_path = str(hermes_home / "hybrid_cognitive_memory.db")
        self.db_path = db_path
        self._init_databases()

    def _init_databases(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            
            # 1. Temporal Cache Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS temporal_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT UNIQUE,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    decay_factor REAL DEFAULT 0.05
                )
            """)
            
            # 2. Knowledge Graph Nodes Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    entity_name TEXT PRIMARY KEY,
                    entity_type TEXT DEFAULT 'generic',
                    created_at TEXT NOT NULL
                )
            """)
            
            # 3. Knowledge Graph Triples Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_node TEXT NOT NULL,
                    target_node TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY(source_node) REFERENCES graph_nodes(entity_name) ON DELETE CASCADE,
                    FOREIGN KEY(target_node) REFERENCES graph_nodes(entity_name) ON DELETE CASCADE,
                    UNIQUE(source_node, target_node, relation)
                )
            """)
            conn.commit()

    # --- Knowledge Graph API ---
    def add_entity(self, name: str, entity_type: str = "generic"):
        name_clean = name.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO graph_nodes (entity_name, entity_type, created_at) VALUES (?, ?, ?)",
                (name_clean, entity_type, now)
            )
            conn.commit()

    def add_relation(self, source: str, target: str, relation: str, weight: float = 1.0):
        source_clean = source.strip().lower()
        target_clean = target.strip().lower()
        relation_clean = relation.strip().lower()
        
        self.add_entity(source_clean)
        self.add_entity(target_clean)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO graph_triples (source_node, target_node, relation, weight)
                VALUES (?, ?, ?, ?)
            """, (source_clean, target_clean, relation_clean, weight))
            conn.commit()

    def query_neighborhood(self, entity: str) -> List[Tuple[str, str, str]]:
        entity_clean = entity.strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT source_node, relation, target_node FROM graph_triples
                WHERE source_node = ? OR target_node = ?
            """, (entity_clean, entity_clean)).fetchall()
        return rows

    # --- Temporal Access & Decay API ---
    def record_memory_access(self, key: str, content: str):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO temporal_memories (memory_key, content, created_at, last_accessed_at, access_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(memory_key) DO UPDATE SET
                    content = ?,
                    last_accessed_at = ?,
                    access_count = access_count + 1
            """, (key, content, now, now, content, now))
            conn.commit()

    def retrieve_active_memories(self, decay_threshold: float = 0.1) -> List[Dict]:
        """
        Retrieves memories with a relevance score computed dynamically
        via: score = access_count * e^(-decay_factor * days_inactive)
        """
        now = datetime.now(timezone.utc)
        active_memories = []
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT memory_key, content, last_accessed_at, access_count, decay_factor
                FROM temporal_memories
            """).fetchall()
            
        for key, content, last_accessed_str, access_count, decay_factor in rows:
            last_accessed = datetime.fromisoformat(last_accessed_str)
            days_inactive = (now - last_accessed).days + ((now - last_accessed).seconds / 86400.0)
            
            # Exponential decay formula
            score = access_count * math.exp(-decay_factor * days_inactive)
            
            if score >= decay_threshold:
                active_memories.append({
                    "key": key,
                    "content": content,
                    "score": round(score, 3),
                    "days_inactive": round(days_inactive, 2)
                })
            else:
                # Cleanup stale entry autonomously
                self._prune_memory(key)
                
        active_memories.sort(key=lambda x: x["score"], reverse=True)
        return active_memories

    def _prune_memory(self, key: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM temporal_memories WHERE memory_key = ?", (key,))
            conn.commit()

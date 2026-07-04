import sys
import os
import shutil
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.agent.evolution import GEPAEvolution

def setup_test_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            instructions TEXT,
            success_count INTEGER,
            fail_count INTEGER,
            version INTEGER,
            updated_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS skill_fts (
            rowid INTEGER PRIMARY KEY,
            instructions TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            response TEXT,
            tools_used TEXT,
            success INTEGER,
            timestamp TEXT
        )
    ''')
    
    # Insert a dummy failing skill
    conn.execute('''
        INSERT INTO skills (name, instructions, success_count, fail_count, version, updated_at)
        VALUES ('WebSearch', 'Use Google Search to find relevant web links.', 1, 9, 1, '2026-07-03T12:00:00')
    ''')
    conn.execute("INSERT INTO skill_fts (rowid, instructions) VALUES (1, 'Use Google Search to find relevant web links.')")
    
    # Insert dummy failure traces containing keywords like "brave-free", "json", "failure"
    conn.execute('''
        INSERT INTO sessions (query, response, tools_used, success, timestamp)
        VALUES ('find data science jobs', 'Error reading brave-free JSON data', 'web-search', 0, '2026-07-03T12:05:00')
    ''')
    conn.commit()
    conn.close()

def test_evolution_mutation():
    temp_dir = tempfile.mkdtemp(prefix="test_evo_")
    db_file = os.path.join(temp_dir, "test_learning.db")
    setup_test_db(db_file)
    
    try:
        evo = GEPAEvolution(db_path=db_file)
        
        # Get the initial skill row
        skill_row = evo.loop.conn.execute("SELECT * FROM skills WHERE id = 1").fetchone()
        skill = dict(zip([col[0] for col in evo.loop.conn.execute("SELECT * FROM skills LIMIT 0").description], skill_row))
        
        # 1. Test evaluation directly on identical instructions
        score_ident = evo._evaluate_instructions(skill, skill["instructions"])
        assert score_ident == 0.0
        print("test_evaluation_mutation: Direct identical check scored 0.0 successfully.")
        
        # 2. Test evaluation directly on empty instructions
        score_empty = evo._evaluate_instructions(skill, "   ")
        assert score_empty == 0.0
        print("test_evaluation_mutation: Direct empty check scored 0.0 successfully.")
        
        # 3. Test _evolve_skill when optimizer returns no change
        mock_result_ident = MagicMock()
        mock_result_ident.improved_skill = skill["instructions"]
        with patch("dspy.Predict") as mock_predict:
            mock_predict.return_value = MagicMock(return_value=mock_result_ident)
            res_ident = evo._evolve_skill(skill)
        assert not res_ident
        print("test_evolution_mutation: Rejected identical instructions successfully.")
        
        # 4. Test _evolve_skill when optimizer returns highly relevant instructions (contains keyword 'brave-free' from failure logs)
        mock_result_rel = MagicMock()
        mock_result_rel.improved_skill = "Use Google Search or brave-free engine and parse JSON results carefully to find links."
        with patch("dspy.Predict") as mock_predict:
            mock_predict.return_value = MagicMock(return_value=mock_result_rel)
            res_rel = evo._evolve_skill(skill)
        assert res_rel
        print("test_evolution_mutation: Promoted relevant instructions successfully!")
        
        # Verify db update
        updated_instructions = evo.loop.conn.execute("SELECT instructions FROM skills WHERE id = 1").fetchone()[0]
        assert "brave-free" in updated_instructions
        
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

def main():
    print("--- Running DSPy Skill Evolution Mutation Tests ---")
    test_evolution_mutation()
    print("All evolution tests passed successfully! 🎉")

if __name__ == "__main__":
    main()

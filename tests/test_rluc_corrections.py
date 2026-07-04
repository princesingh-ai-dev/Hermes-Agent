import sys
import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes_state import SessionDB
from hermes.agent.evolution import GEPAEvolution

def test_db_corrections_insertion_retrieval():
    print("test_db_corrections_insertion_retrieval: Running...")
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "state.db"
    try:
        db = SessionDB(db_path=db_path)
        
        # Insert a session
        db.create_session("session_1", "cli")
        
        # Record a user correction
        db.record_user_correction(
            session_id="session_1",
            correction_text="Don't use python to run simple git status",
            previous_tool_name="execute_python_safe",
            previous_tool_args='{"code": "import subprocess; subprocess.run([\\"git\\", \\"status\\"])"}',
            corrected_action="git_status"
        )
        
        # Retrieve corrections
        corrs = db.get_user_corrections()
        assert len(corrs) == 1
        assert corrs[0]["session_id"] == "session_1"
        assert corrs[0]["previous_tool_name"] == "execute_python_safe"
        assert "git status" in corrs[0]["correction_text"]
        print("test_db_corrections_insertion_retrieval: PASSED")
    finally:
        try:
            db.close()
        except Exception:
            pass
        shutil.rmtree(temp_dir)

def test_extract_last_tool_call():
    print("test_extract_last_tool_call: Running...")
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "state.db"
    try:
        db = SessionDB(db_path=db_path)
        db.create_session("session_2", "cli")
        
        # Insert messages: user message, assistant action, tool response
        db._conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?)",
            ("session_2", "user", "run git status please", None, 100.0)
        )
        db._conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?)",
            ("session_2", "assistant", None, '[{"function": {"name": "execute_python_safe", "arguments": {"code": "print(1)"}}}]', 101.0)
        )
        db._conn.commit()
        
        # Simulate /correct extraction logic
        messages = db.get_messages("session_2")
        prev_tool_name = None
        prev_tool_args = None
        
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_call = msg["tool_calls"][0]
                prev_tool_name = tool_call.get("function", {}).get("name")
                import json
                prev_tool_args = json.dumps(tool_call.get("function", {}).get("arguments"))
                break
                
        assert prev_tool_name == "execute_python_safe"
        assert "print(1)" in prev_tool_args
        print("test_extract_last_tool_call: PASSED")
    finally:
        try:
            db.close()
        except Exception:
            pass
        shutil.rmtree(temp_dir)

def test_evolution_corrections_injection():
    print("test_evolution_corrections_injection: Running...")
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "state.db"
    try:
        # Patch SessionDB globally to return our test corrections
        db = SessionDB(db_path=db_path)
        db.create_session("session_3", "cli")
        db.record_user_correction(
            session_id="session_3",
            correction_text="Use Brave search API for search",
            previous_tool_name="web_search",
            previous_tool_args='{"query": "hello"}'
        )
        
        # Create a mock GEPAEvolution
        loop_mock = MagicMock()
        loop_mock.conn = db._conn
        
        evolution = GEPAEvolution()
        evolution.loop = loop_mock
        
        skill = {
            "id": 1,
            "name": "WebSearch",
            "instructions": "Use web_search tool to fetch answers",
            "version": 1
        }
        
        # Verify that _evolve_skill query includes the correction
        # We mock _evaluate_instructions and _get_failure_traces
        with patch.object(evolution, "_get_failure_traces", return_value=[]), \
             patch.object(evolution, "_evaluate_instructions", return_value=0.0), \
             patch.object(SessionDB, "get_user_corrections", return_value=db.get_user_corrections()):
                 
            # We mock the DSPy predict call to assert it receives the user corrections feedback
            with patch("dspy.Predict") as mock_predict:
                mock_predict_instance = MagicMock()
                mock_predict.return_value = mock_predict_instance
                mock_predict_instance.return_value = MagicMock(improved_skill="improved instructions")
                
                evolution._evolve_skill(skill)
                
                # Check what failure_traces arguments was passed to Predict
                args, kwargs = mock_predict_instance.call_args
                passed_failures = kwargs.get("failure_traces") or args[1]
                assert "User Correction: Tool 'web_search' failed" in passed_failures
                assert "Use Brave search API for search" in passed_failures
                
        print("test_evolution_corrections_injection: PASSED")
    finally:
        try:
            db.close()
        except Exception:
            pass
        shutil.rmtree(temp_dir)

def main():
    print("--- Running RLUC User Corrections Feedback Tests ---")
    test_db_corrections_insertion_retrieval()
    test_extract_last_tool_call()
    test_evolution_corrections_injection()
    print("All RLUC corrections tests passed successfully! 🎉")

if __name__ == "__main__":
    main()

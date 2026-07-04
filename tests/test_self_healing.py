import sys
import os
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.tools.code_exec import _get_ast_diagnostics, execute_with_healing

def test_ast_diagnostics():
    bad_code = """
def hello():
    print "hello world"
"""
    diag = _get_ast_diagnostics(bad_code)
    print(f"AST Diagnostic output:\n{diag}")
    assert "AST SyntaxError" in diag
    assert "line 3" in diag
    print("test_ast_diagnostics: PASSED")

def test_self_healing_simulated():
    bad_code = """
def hello():
    print "hello world"

hello()
"""
    # Force mock API key to be absent to trigger heuristic fallback
    with patch.dict(os.environ, {}, clear=False):
        res = execute_with_healing.invoke({
            "prompt": "Print hello world inside a hello function",
            "initial_code": bad_code
        })
        
    print(f"Self-Healing Result:\n{res}")
    assert res.get("status") == "success"
    assert "print(" in res.get("final_code")
    print("test_self_healing_simulated: PASSED")

def main():
    print("--- Running AST Self-Healing Tests ---")
    test_ast_diagnostics()
    test_self_healing_simulated()
    print("All healing tests passed successfully! 🎉")

if __name__ == "__main__":
    main()

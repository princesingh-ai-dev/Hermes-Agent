import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.tools.code_exec import execute_python_safe, _is_docker_available

def test_docker_availability_run():
    # Just run it to see if it executes without crashing
    avail = _is_docker_available()
    print(f"Docker available on host: {avail}")

def test_fallback_scrubbing():
    # Set a sensitive env var
    os.environ["SECRET_API_KEY_TEST"] = "super-secret-key-12345"
    
    # Python code to print env var
    code = """
import os
print(os.environ.get("SECRET_API_KEY_TEST", "NOT_FOUND"))
"""
    # Force fallback by mocking _is_docker_available to False
    with patch("hermes.tools.code_exec._is_docker_available", return_value=False):
        res = execute_python_safe.invoke({"code": code})
        
    assert res.get("sandbox") == "local_fallback"
    # Ensure it did not leak the key
    output = res.get("stdout", "").strip()
    assert "super-secret-key-12345" not in output
    assert output == "NOT_FOUND"
    print("test_fallback_scrubbing: PASSED")

def test_docker_execution_if_available():
    if not _is_docker_available():
        print("test_docker_execution_if_available: SKIPPED (Docker not running on host)")
        return
        
    # Code that attempts a socket connection to google.com (should fail because --network none)
    code = """
import socket
try:
    socket.create_connection(("8.8.8.8", 53), timeout=2)
    print("CONNECTED")
except Exception as e:
    print(f"FAILED: {e}")
"""
    res = execute_python_safe.invoke({"code": code})
    assert res.get("sandbox") == "docker"
    output = res.get("stdout", "").strip()
    assert "FAILED" in output
    assert "CONNECTED" not in output
    print("test_docker_execution_if_available: PASSED (Network isolated!)")

def main():
    print("--- Running Code Execution Sandbox Tests ---")
    test_docker_availability_run()
    test_fallback_scrubbing()
    test_docker_execution_if_available()
    print("All tests passed successfully! 🎉")

if __name__ == "__main__":
    main()

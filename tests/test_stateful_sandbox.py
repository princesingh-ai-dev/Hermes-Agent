import sys
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.tools.code_exec import DockerSandboxManager, execute_python_safe

def test_availability_run():
    mgr = DockerSandboxManager.get_instance()
    avail = mgr.is_available()
    print(f"Docker SDK connection active: {avail}")

def test_fallback_when_docker_down():
    # Force mock client to be None to simulate Docker being down
    with patch.object(DockerSandboxManager, "is_available", return_value=False):
        res = execute_python_safe.invoke({
            "code": "print('local fallback run')",
            "session_id": "test_fallback"
        })
    assert res.get("sandbox") == "local_fallback"
    assert "local fallback run" in res.get("stdout").strip()
    print("test_fallback_when_docker_down: PASSED")

def test_stateful_execution():
    mgr = DockerSandboxManager.get_instance()
    if not mgr.is_available():
        print("test_stateful_execution: SKIPPED (Docker daemon not running on host)")
        return
        
    session_id = "test_stateful_session"
    
    # Clean up any leftover container first
    mgr.cleanup_container(session_id)
    
    try:
        # Step 1: Write a state file inside the sandbox
        code1 = """
with open("state.txt", "w") as f:
    f.write("stateful-data-1234")
print("STEP_1_DONE")
"""
        res1 = execute_python_safe.invoke({
            "code": code1,
            "session_id": session_id
        })
        assert res1.get("sandbox") == "docker_stateful"
        assert "STEP_1_DONE" in res1.get("stdout").strip()
        
        # Step 2: Read the state file inside the sandbox in a separate tool invocation
        code2 = """
try:
    with open("state.txt", "r") as f:
        print("CONTENT:" + f.read())
except Exception as e:
    print("ERROR:" + str(e))
"""
        res2 = execute_python_safe.invoke({
            "code": code2,
            "session_id": session_id
        })
        assert res2.get("sandbox") == "docker_stateful"
        stdout = res2.get("stdout").strip()
        print(f"Step 2 Read Output: {stdout}")
        assert "CONTENT:stateful-data-1234" in stdout
        print("test_stateful_execution: PASSED")
    finally:
        mgr.cleanup_container(session_id)

def main():
    print("--- Running Persistent Stateful Sandbox Tests ---")
    DockerSandboxManager._instance = None
    DockerSandboxManager._proxy_server = None
    test_availability_run()
    test_fallback_when_docker_down()
    test_stateful_execution()
    print("All sandbox tests passed successfully! 🎉")

if __name__ == "__main__":
    main()

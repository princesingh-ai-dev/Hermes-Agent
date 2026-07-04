import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.subagents.spawner import SubagentSpawner, SubagentTask

async def test_validate_and_sanitize_dag_acyclic():
    spawner = SubagentSpawner()
    task_dict = {
        "t1": SubagentTask("t1", "Task 1", "Researcher", [], ["web"]),
        "t2": SubagentTask("t2", "Task 2", "Developer", ["t1"], ["file"]),
        "t3": SubagentTask("t3", "Task 3", "Writer", ["t2"], ["terminal"])
    }
    
    # Run sanitization
    spawner._validate_and_sanitize_dag(task_dict)
    
    # Assert no change (already acyclic)
    assert task_dict["t1"].dependencies == []
    assert task_dict["t2"].dependencies == ["t1"]
    assert task_dict["t3"].dependencies == ["t2"]
    print("test_validate_and_sanitize_dag_acyclic: PASSED")

async def test_validate_and_sanitize_dag_cyclic():
    spawner = SubagentSpawner()
    # Cycle: t1 -> t2 -> t3 -> t1
    task_dict = {
        "t1": SubagentTask("t1", "Task 1", "Role 1", ["t3"], []),
        "t2": SubagentTask("t2", "Task 2", "Role 2", ["t1"], []),
        "t3": SubagentTask("t3", "Task 3", "Role 3", ["t2"], [])
    }
    
    spawner._validate_and_sanitize_dag(task_dict)
    
    # Verify cycle was broken by linearizing the tasks
    has_empty = any(len(t.dependencies) == 0 for t in task_dict.values())
    assert has_empty, "Cyclic DAG did not resolve to have at least one root node"
    print("test_validate_and_sanitize_dag_cyclic: PASSED")

async def test_decompose_task_fallback():
    spawner = SubagentSpawner()
    # Force LLM decomposition failure
    with patch("hermes.core.model_router.ModelRouter.get_client", side_effect=Exception("API Key not found")):
        tasks = await spawner._decompose_task("Test prompt")
        
    assert len(tasks) == 3
    assert tasks[0].id == "t1"
    assert tasks[1].dependencies == ["t1"]
    assert tasks[2].dependencies == ["t2"]
    print("test_decompose_task_fallback: PASSED")

async def test_execute_task_containment():
    spawner = SubagentSpawner()
    task = SubagentTask("t1", "Do something", "Analyst", [], [])
    task_dict = {"t1": task}
    
    # Mock AIAgent to raise an exception
    with patch("hermes.subagents.spawner.AIAgent") as MockAgentClass:
        mock_agent = MockAgentClass.return_value
        mock_agent.run_conversation.side_effect = Exception("Inference failed")
        
        await spawner._execute_task(task, task_dict)
        
    assert task.status == "failed"
    assert "Error: Inference failed" in task.result
    print("test_execute_task_containment: PASSED")

async def main():
    print("--- Running SubagentSpawner DAG Tests ---")
    await test_validate_and_sanitize_dag_acyclic()
    await test_validate_and_sanitize_dag_cyclic()
    await test_decompose_task_fallback()
    await test_execute_task_containment()
    print("All tests passed successfully! 🎉")

if __name__ == "__main__":
    asyncio.run(main())

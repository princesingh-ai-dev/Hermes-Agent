import sys
import os
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from run_agent import AIAgent
from hermes.core.model_router import ModelRouter

@dataclass
class SubagentTask:
    id: str
    task_description: str
    role: str
    dependencies: List[str]
    tools: List[str]
    status: str = "pending"  # pending | running | completed | failed
    result: str = ""

class SubagentSpawner:
    """
    Production-ready Dynamic Swarm Orchestrator (Legion Protocol):
    - Decomposes a complex task into a Directed Acyclic Graph (DAG) of subtasks using LLM.
    - Executes independent subtasks in parallel concurrently using asyncio.to_thread.
    - Cascades outputs from parent dependencies to downstream subtasks.
    - Synthesizes a structured final execution report.
    """
    def __init__(self):
        self.logger = logging.getLogger("hermes.subagents.spawner")

    async def spawn_parallel(self, tasks: List[str]) -> List[str]:
        """Backward compatible parallel execution of independent tasks."""
        self.logger.info(f"Spawning {len(tasks)} parallel subtasks.")
        subagent_tasks = []
        for i, t in enumerate(tasks):
            subagent_tasks.append(SubagentTask(
                id=f"p{i}",
                task_description=t,
                role="Specialist",
                dependencies=[],
                tools=["web", "terminal", "file"]
            ))
        
        task_dict = {t.id: t for t in subagent_tasks}
        await asyncio.gather(*[self._execute_task(t, task_dict) for t in subagent_tasks])
        return [t.result for t in subagent_tasks]

    async def spawn_dag(self, prompt: str, parent_session_id: str = None) -> str:
        """Decompose a master task into a DAG and execute topologically."""
        self.logger.info(f"Decomposing master task: {prompt}")
        tasks = await self._decompose_task(prompt)
        
        # Build dependency graph
        task_dict = {t.id: t for t in tasks}
        
        # Validate dependencies and remove cycles
        self._validate_and_sanitize_dag(task_dict)
        
        self.logger.info(f"DAG structured with {len(task_dict)} tasks. Commencing execution loop.")
        
        # Event-driven topological run loop
        while True:
            ready_tasks = []
            all_done = True
            
            for t_id, task in task_dict.items():
                if task.status == "pending":
                    all_done = False
                    deps_ok = True
                    for dep_id in task.dependencies:
                        dep_task = task_dict.get(dep_id)
                        if not dep_task or dep_task.status != "completed":
                            deps_ok = False
                            break
                    if deps_ok:
                        ready_tasks.append(task)
                elif task.status == "running":
                    all_done = False

            if all_done:
                break
                
            if not ready_tasks:
                # Cycle or deadlock detected in runtime
                self.logger.warning("Unresolved dependency cycle or deadlock. Terminating remaining tasks.")
                for t in task_dict.values():
                    if t.status == "pending":
                        t.status = "failed"
                        t.result = "Deadlock/unresolved dependency cycle"
                break
                
            # Run all ready tasks in parallel
            self.logger.info(f"Executing batch: {[t.id for t in ready_tasks]}")
            await asyncio.gather(*[
                self._execute_task(t, task_dict, parent_session_id) for t in ready_tasks
            ])
            
        final_report = self._generate_final_report(task_dict, prompt)
        return final_report

    async def _decompose_task(self, prompt: str) -> List[SubagentTask]:
        """Decompose a high-level task into subtasks via LLM."""
        try:
            client = ModelRouter.get_client("planning")
            route = ModelRouter.get_route("planning")
            
            system_prompt = (
                "You are a highly advanced task decomposition engine.\n"
                "Your task is to break down a complex, high-level task into a Directed Acyclic Graph (DAG) of smaller, focused, and independent subtasks that can be executed by specialized subagents.\n\n"
                "Each subtask must contain:\n"
                "1. `id`: A unique, short identifier (e.g. \"t1\", \"t2\", \"t3\").\n"
                "2. `task_description`: A clear, detailed description of the task this subagent must solve, including the expected outputs.\n"
                "3. `role`: The specialized role name/persona for the subagent (e.g. \"Researcher\", \"Python Developer\", \"Security Auditor\", \"Writer\").\n"
                "4. `dependencies`: A list of task IDs that MUST complete before this task can start. For independent tasks, this is an empty list `[]`.\n"
                "5. `tools`: A list of toolsets allowed for this task. Available toolset names: [\"web\", \"terminal\", \"file\", \"browser\", \"memory\", \"skills\"].\n\n"
                "You must return strictly valid JSON inside a JSON object with a key \"tasks\" mapping to an array of tasks.\n"
                "Respond with ONLY the JSON object. Do not wrap in ```json markdown blocks, just return raw JSON."
            )
            
            user_prompt = f"Decompose this task: {prompt}"
            
            response = await client.chat.completions.create(
                model=route["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean markdown code block wraps if present
            if content.startswith("```"):
                content = re.sub(r"^```[a-zA-Z0-9-]*\n", "", content)
                content = re.sub(r"\n```$", "", content)
                content = content.strip()
                
            data = json.loads(content)
            tasks = []
            for t_data in data.get("tasks", []):
                tasks.append(SubagentTask(
                    id=str(t_data.get("id")),
                    task_description=str(t_data.get("task_description")),
                    role=str(t_data.get("role")),
                    dependencies=list(t_data.get("dependencies", [])),
                    tools=list(t_data.get("tools", []))
                ))
            if tasks:
                return tasks
        except Exception as e:
            self.logger.error(f"Failed to decompose task via LLM: {e}. Falling back to default linear DAG.")
            
        # Fallback static linear DAG
        return [
            SubagentTask(
                id="t1",
                task_description=f"Research and gather necessary context/specifications for: {prompt}",
                role="Researcher",
                dependencies=[],
                tools=["web"]
            ),
            SubagentTask(
                id="t2",
                task_description=f"Implement, write code, or execute the core logic for: {prompt}",
                role="Developer",
                dependencies=["t1"],
                tools=["file", "terminal"]
            ),
            SubagentTask(
                id="t3",
                task_description=f"Review, test, verify, and write a summary report for: {prompt}",
                role="Technical Writer",
                dependencies=["t2"],
                tools=["terminal"]
            )
        ]

    async def _execute_task(self, task: SubagentTask, task_dict: Dict[str, SubagentTask], parent_session_id: str = None):
        """Execute a single subtask by running a real AIAgent instance in a worker thread."""
        task.status = "running"
        self.logger.info(f"Executing subtask {task.id} (Role: {task.role})")
        
        # Assemble context from dependency task outputs
        dep_context = ""
        if task.dependencies:
            dep_context += "Context from previous completed subtasks:\n\n"
            for dep_id in task.dependencies:
                dep_task = task_dict.get(dep_id)
                if dep_task:
                    dep_context += f"--- Result from Task {dep_task.id} (Role: {dep_task.role}) ---\n"
                    dep_context += f"{dep_task.result}\n\n"
                    
        # Construct isolated instructions for the subagent
        user_msg = f"{dep_context}Your instructions: {task.task_description}"
        system_msg = f"You are a specialized subagent acting as a {task.role}. Solve your assigned subtask. Focus ONLY on your subtask and return your results."
        
        try:
            # Route model (default to coding or planning models)
            route = ModelRouter.get_route("coding")
            
            # Instantiate real AIAgent
            agent = AIAgent(
                base_url=route.get("base_url"),
                api_key=route.get("api_key"),
                provider=route.get("provider"),
                model=route.get("model"),
                max_iterations=15,  # Subagents have lower limits
                enabled_toolsets=task.tools,
                parent_session_id=parent_session_id,
                quiet_mode=True,
                skip_memory=True
            )
            
            # Execute synchronously in thread pool
            res_dict = await asyncio.to_thread(
                agent.run_conversation,
                user_message=user_msg,
                system_message=system_msg
            )
            
            task.result = res_dict.get("final_response") or "No output returned by subagent."
            task.status = "completed"
            self.logger.info(f"Subtask {task.id} completed.")
            
        except Exception as e:
            self.logger.error(f"Error executing subtask {task.id}: {e}", exc_info=True)
            task.status = "failed"
            task.result = f"Error: {e}"

    def _validate_and_sanitize_dag(self, task_dict: Dict[str, SubagentTask]):
        """Sanitize dependencies and break circular references by linearizing."""
        for t_id, task in task_dict.items():
            task.dependencies = [d for d in task.dependencies if d in task_dict and d != t_id]
            
        # Detect cycles using topological sorting simulation (Kahn's algorithm)
        in_degree = {t_id: 0 for t_id in task_dict}
        adj = {t_id: [] for t_id in task_dict}
        
        for t_id, task in task_dict.items():
            for dep in task.dependencies:
                adj[dep].append(t_id)
                in_degree[t_id] += 1
                
        queue = [t_id for t_id, deg in in_degree.items() if deg == 0]
        visited = []
        
        while queue:
            node = queue.pop(0)
            visited.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        # If there's a cycle, visited will be incomplete. Break cycle by linearizing.
        if len(visited) < len(task_dict):
            self.logger.warning("Dependency cycle detected! Linearizing tasks to resolve.")
            keys = list(task_dict.keys())
            for i, key in enumerate(keys):
                if i == 0:
                    task_dict[key].dependencies = []
                else:
                    task_dict[key].dependencies = [keys[i-1]]

    def _generate_final_report(self, task_dict: Dict[str, SubagentTask], original_prompt: str) -> str:
        """Synthesize results of all executed tasks into a markdown summary."""
        report = f"### Legion Swarm Execution Report 🛡️\n\n"
        report += f"**Original Task:** {original_prompt}\n\n"
        report += "| Task ID | Role | Status | Result Summary |\n"
        report += "| --- | --- | --- | --- |\n"
        
        for t_id, task in task_dict.items():
            status_emoji = "✅" if task.status == "completed" else "❌" if task.status == "failed" else "⏳"
            summary = task.result[:120].replace("\n", " ") + ("..." if len(task.result) > 120 else "")
            report += f"| {t_id} | {task.role} | {status_emoji} {task.status} | {summary} |\n"
            
        report += "\n---\n\n"
        for t_id, task in task_dict.items():
            report += f"#### Task {t_id} [{task.role}]\n"
            report += f"**Description:** {task.task_description}\n\n"
            report += f"**Output:**\n{task.result}\n\n"
            report += "---\n\n"
            
        return report

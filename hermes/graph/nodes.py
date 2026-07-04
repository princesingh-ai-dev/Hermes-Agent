# hermes/graph/nodes.py
from typing import TypedDict, Annotated
import operator
from hermes.core.model_router import ModelRouter
from hermes.memory.chroma_store import HermesMemory
from hermes.tools.registry import load_all_tools

class HermesState(TypedDict):
    messages: Annotated[list, operator.add]
    task_type: str
    tool_results: list
    memory_context: str
    iteration: int
    final_answer: str

memory_store = HermesMemory()
tools = load_all_tools()

async def classify_task_node(state: HermesState):
    # For now, just set a default task type or simple logic
    # In a full implementation, this would use the LLM to classify.
    last_msg = state["messages"][-1] if state["messages"] else {"role": "user", "content": ""}
    # Simplified classification
    return {"task_type": "reasoning"}

async def recall_memory_node(state: HermesState):
    last_msg = state["messages"][-1] if state["messages"] else {"role": "user", "content": ""}
    # Example logic
    context = memory_store.recall(last_msg["content"]) if isinstance(last_msg, dict) and "content" in last_msg else ""
    return {"memory_context": context}

async def _spawn_subagent(client, route, role, messages):
    """Option A: Legion Protocol Sub-Agent."""
    system_msg = {"role": "system", "content": f"You are a specialized sub-agent. Your role is: {role}"}
    try:
        response = await client.chat.completions.create(
            model=route["model"],
            messages=[system_msg] + messages
        )
        return f"[{role} Agent]: {response.choices[0].message.content}"
    except Exception as e:
        return f"[{role} Agent] Error: {e}"

async def plan_node(state: HermesState):
    client = ModelRouter.get_client(state.get("task_type", "default"))
    route = ModelRouter.get_route(state.get("task_type", "default"))
    
    # Check if the user is asking for a massive task (Trigger Legion Protocol)
    last_user_msg = state["messages"][-1].get("content", "").lower() if isinstance(state["messages"][-1], dict) else ""
    
    if "build a full stack" in last_user_msg or "legion protocol" in last_user_msg:
        from hermes.subagents.spawner import SubagentSpawner
        spawner = SubagentSpawner()
        combined_response = await spawner.spawn_dag(last_user_msg)
        return {"messages": [{"role": "assistant", "content": combined_response}]}

    # Normal single-agent execution
    response = await client.chat.completions.create(
        model=route["model"],
        messages=state["messages"]
    )
    
    new_msg = response.choices[0].message
    return {"messages": [{"role": "assistant", "content": new_msg.content}]}

async def tool_execution_node(state: HermesState):
    # Dummy tool execution for now
    return {"tool_results": ["executed"]}

async def synthesis_node(state: HermesState):
    # Final answer synthesis
    last_msg = state["messages"][-1]
    return {"final_answer": last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)}

async def store_memory_node(state: HermesState):
    # Store important insights
    if state.get("final_answer"):
        memory_store.store(state["final_answer"])
    return {}

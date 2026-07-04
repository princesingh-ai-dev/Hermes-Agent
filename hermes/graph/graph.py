# hermes/graph/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from hermes.graph.nodes import (
    HermesState, classify_task_node, recall_memory_node, plan_node,
    tool_execution_node, synthesis_node, store_memory_node
)

def should_continue(state: HermesState) -> str:
    # Condition: if tool_results exists, we could route back to plan, else synthesize
    return "done"

def build_hermes_graph():
    graph = StateGraph(HermesState)
    
    # Nodes
    graph.add_node("classify_task", classify_task_node)
    graph.add_node("recall_memory", recall_memory_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute_tools", tool_execution_node)
    graph.add_node("synthesize", synthesis_node)
    graph.add_node("store_memory", store_memory_node)
    
    # Edges
    graph.set_entry_point("classify_task")
    graph.add_edge("classify_task", "recall_memory")
    graph.add_edge("recall_memory", "plan")
    graph.add_edge("plan", "execute_tools")
    
    graph.add_conditional_edges("execute_tools", should_continue, {
        "continue": "plan",
        "done": "synthesize"
    })
    
    graph.add_edge("synthesize", "store_memory")
    graph.add_edge("store_memory", END)
    
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)

# Export an instance
hermes_graph = build_hermes_graph()

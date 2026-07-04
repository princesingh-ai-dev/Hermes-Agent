from langchain_core.tools import tool
from hermes.tools.registry import register_tool
from hermes.memory.graph_store import GraphStore
import json

graph_store = GraphStore()

@register_tool
@tool("memorize_graph_fact")
def memorize_graph_fact(triples_json: str) -> str:
    """
    Memorize facts into the Deep Knowledge Graph.
    Input must be a JSON array of arrays, where each inner array is exactly 3 strings: [subject, predicate, object].
    Example: '[["Prince", "created", "Hermes"], ["Hermes", "is_a", "AI Assistant"]]'
    """
    try:
        triples = json.loads(triples_json)
        if not isinstance(triples, list):
            return "Error: Input must be a JSON array of triples."
            
        count = 0
        for t in triples:
            if isinstance(t, list) and len(t) == 3:
                graph_store.add_triple(str(t[0]), str(t[1]), str(t[2]))
                count += 1
        
        return f"Successfully etched {count} relationships into the Deep Graph Memory."
    except Exception as e:
        return f"Failed to parse or store triples. Ensure strictly valid JSON. Error: {e}"

@register_tool
@tool("query_graph_memory")
def query_graph_memory(entity: str) -> str:
    """
    Query the Deep Knowledge Graph to recall complex facts, relationships, and context about an entity.
    Provide the exact name of the entity you want to look up (e.g. 'Prince').
    Returns all connected relationships up to 2 degrees of separation.
    """
    try:
        results = graph_store.query_neighborhood(entity, depth=2)
        if not results:
            return f"No memories found connected to '{entity}'."
            
        out = f"--- GraphRAG Memories for [{entity}] ---\n"
        out += "\n".join(results)
        return out
    except Exception as e:
        return f"Failed to traverse graph. Error: {e}"

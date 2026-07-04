# hermes/tools/registry.py
# All tools as LangChain @tool decorated functions
import logging

TOOL_REGISTRY = []

def register_tool(func):
    """Decorator to register a LangChain @tool into the central registry."""
    TOOL_REGISTRY.append(func)
    return func

# Note: We will import specific tools here after they are implemented
# to ensure they are registered when this module is loaded.
def load_all_tools():
    import hermes.tools.obsidian
    import hermes.tools.search
    import hermes.tools.code_exec
    import hermes.tools.computer_use
    import hermes.tools.graph_memory
    import hermes.tools.smart_home
    
    return TOOL_REGISTRY

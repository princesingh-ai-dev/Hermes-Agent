import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path to prevent import shadowing from tests/run_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.memory.graph_store import GraphStore

async def test_semantic_resolution():
    # Setup graph store (using a test SQLite file and temporary Chroma collection)
    db_file = "test_graph_memory.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
            
    store = GraphStore(db_path=db_file)
    
    # Store a fact
    store.add_triple("Jarvis", "is", "Operational")
    store.add_triple("Prince", "created", "Jarvis")
    
    # Verify exact match
    exact_res = store.query_neighborhood("Jarvis")
    print(f"Exact match results: {exact_res}")
    assert any("[jarvis] --is--> [operational]" in r for r in exact_res)
    
    # Verify semantic match (using slightly different query "Jarvis System")
    semantic_res = store.query_neighborhood("Jarvis System")
    print(f"Semantic match results (Query 'Jarvis System'): {semantic_res}")
    assert any("[jarvis] --is--> [operational]" in r for r in semantic_res)
    
    # Clean up test DB
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
    print("test_semantic_resolution: PASSED")

async def main():
    print("--- Running Multi-Modal Cognitive Memory Tests ---")
    await test_semantic_resolution()
    print("All memory tests passed successfully! 🎉")

if __name__ == "__main__":
    asyncio.run(main())

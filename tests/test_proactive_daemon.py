import sys
import os
import shutil
import tempfile
import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from hermes.core.idle_loop import IdleManager
from hermes.memory.chroma_store import HermesMemory

async def test_proactive_context_harvesting():
    print("test_proactive_context_harvesting: Running...")
    temp_dir = tempfile.mkdtemp()
    
    # We patch os.getcwd to return our temp workspace dir
    with patch("os.getcwd", return_value=temp_dir), \
         patch("hermes.core.idle_loop.HermesMemory") as mock_memory_class:
         
        mock_memory_instance = MagicMock()
        mock_memory_class.return_value = mock_memory_instance
        
        idle_mgr = IdleManager(interval_seconds=1)
        assert idle_mgr.memory == mock_memory_instance
        
        # 1. Create a dummy python file that imports dspy
        test_file_path = os.path.join(temp_dir, "my_script.py")
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write("import dspy\nimport os\nprint('Hello world!')\n")
            
        # We manually set last_harvest_time to past to ensure it scans this new file
        idle_mgr.last_harvest_time = datetime_from_timestamp(time.time() - 3600)
        
        # Run workspace harvesting
        await idle_mgr._harvest_workspace_context()
        
        # Assert that ChromaDB store was called with the proactive context card
        assert mock_memory_instance.store.call_count >= 1
        
        # Verify call arguments
        store_calls = mock_memory_instance.store.call_args_list
        found_proactive_card = False
        
        for call in store_calls:
            args, kwargs = call
            text = args[0]
            metadata = args[1] if len(args) > 1 else kwargs.get("metadata", {})
            if metadata.get("type") == "proactive_context":
                found_proactive_card = True
                assert "my_script.py" in text
                assert "DSPy guidance:" in text
                assert "dspy" in metadata.get("file_path", "") or "my_script.py" in metadata.get("file_path", "")
                
        assert found_proactive_card is True
        print("test_proactive_context_harvesting: PASSED")
        
    shutil.rmtree(temp_dir)

def datetime_from_timestamp(ts):
    from datetime import datetime
    return datetime.fromtimestamp(ts)

async def test_thread_startup_integration():
    print("test_thread_startup_integration: Running...")
    # Verify we can start/stop the manager cleanly without locking or thread leaks
    with patch("hermes.core.idle_loop.HermesMemory") as mock_memory:
        idle_mgr = IdleManager(interval_seconds=1)
        idle_mgr.memory = MagicMock()
        
        idle_mgr.start()
        assert idle_mgr.is_running is True
        assert idle_mgr._task is not None
        
        await asyncio.sleep(0.5)
        idle_mgr.stop()
        assert idle_mgr.is_running is False
        print("test_thread_startup_integration: PASSED")

async def main():
    print("--- Running Proactive OS Daemon Phase 4 Tests ---")
    await test_proactive_context_harvesting()
    await test_thread_startup_integration()
    print("All proactive daemon phase 4 tests passed successfully! 🎉")

if __name__ == "__main__":
    asyncio.run(main())

"""
Tests for Phase 2: SQLite WAL Temporal Memory Integration
==========================================================
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from agent.turn_context import build_turn_context
from agent.system_prompt import build_system_prompt_parts
from hermes.memory.hybrid_store import HybridMemoryManager


class MockAgent:
    def __init__(self):
        self.session_id = "test_session_123"
        self.platform = "cli"
        self.provider = "openai"
        self.model = "gpt-4"
        self.base_url = "https://api.openai.com/v1"
        self.api_key = "test_key"
        self.api_mode = "chat_completions"
        self.load_soul_identity = False
        self.skip_context_files = True
        self.valid_tool_names = []
        self.active_soul = "default"
        self._memory_write_origin = "assistant_tool"
        self._memory_nudge_interval = 0
        self._turns_since_memory = 0
        self._compression_turn_count = 0
        self._budget_grace_call = False
        self._compression_force_threshold = 10
        self.context_compressor = None
        self._memory_store = None
        self._memory_enabled = False
        self._user_profile_enabled = False
        self._memory_manager = None
        self._session_db = None
        self._session_db_created = False
        self._parent_session_id = None
        self._session_init_model_config = None
        self._tool_use_enforcement = "off"
        self._kanban_worker_guidance = None
        self.pass_session_id = False
        self._tool_guardrails = MagicMock()
        self._compression_warning = False
        self.max_iterations = 90
        self._user_turn_count = 0
        self._persist_user_message_idx = 0
        self.quiet_mode = False
        self._cached_system_prompt = "Identity"
        self.compression_enabled = False
        self.tools = []
        self._user_id = None
        self._turn_failed_file_mutations = {}
        self._turn_file_mutation_paths = set()
        self._verification_stop_nudges = 0
        self._execution_thread_id = None
        self._interrupt_requested = False
        self._interrupt_thread_signal_pending = False
        self._interrupt_message = None

    def _restore_primary_runtime(self):
        pass

    def _cleanup_dead_connections(self):
        return False

    def _emit_status(self, msg):
        pass

    def _replay_compression_warning(self):
        pass

    def _safe_print(self, msg):
        pass

    def _ensure_db_session(self):
        pass

    def _persist_session(self, messages, history):
        pass


class TestPhase2MemoryIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_cognitive.db")
        
        # Patch the HybridMemoryManager db_path globally to point to our test database
        self.patcher_db = patch("hermes.memory.hybrid_store.Path.home", return_value=Path(self.temp_dir.name))
        self.patcher_db.start()
        
        # Clear out any existing data
        self.manager = HybridMemoryManager()

    def tearDown(self):
        self.patcher_db.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_turn_context_prompt_recording(self):
        """Verify that user_message is recorded in temporal memory during context initialization."""
        agent = MockAgent()
        agent.session_id = "test_s1"

        # Mock standard turn dependencies
        mock_ra = MagicMock()
        mock_ra.load_soul_md.return_value = "Identity"
        mock_ra.build_nous_subscription_prompt.return_value = ""

        # Call build_turn_context
        build_turn_context(
            agent,
            user_message="Hello, retrieve my active temporal memory context.",
            system_message=None,
            conversation_history=None,
            task_id="t1",
            stream_callback=None,
            persist_user_message=None,
            restore_or_build_system_prompt=MagicMock(),
            install_safe_stdio=MagicMock(),
            sanitize_surrogates=MagicMock(),
            summarize_user_message_for_log=MagicMock(),
            set_session_context=MagicMock(),
            set_current_write_origin=MagicMock(),
            ra=mock_ra
        )

        # Retrieve active memories from our HybridMemoryManager
        active = self.manager.retrieve_active_memories(decay_threshold=0.1)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["content"], "Hello, retrieve my active temporal memory context.")

    def test_system_prompt_cognitive_memories_injection(self):
        """Verify that active temporal memories are dynamically injected into volatile system prompt parts."""
        # Seeding a memory directly in the store
        self.manager.record_memory_access("m_override", "Custom dynamic temporal details.")

        agent = MockAgent()
        agent.session_id = "test_s2"

        # Assemble prompt parts
        parts = build_system_prompt_parts(agent)
        volatile = parts.get("volatile", "")

        self.assertIn("=== ACTIVE COGNITIVE TEMPORAL MEMORIES ===", volatile)
        self.assertIn("- Custom dynamic temporal details.", volatile)

if __name__ == "__main__":
    unittest.main()

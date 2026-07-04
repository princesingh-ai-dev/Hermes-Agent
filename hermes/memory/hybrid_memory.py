"""
hermes/memory/hybrid_memory.py
================================
Forwarding shim: re-exports HybridMemoryManager from the canonical module
hermes.memory.hybrid_store under the legacy name hermes.memory.hybrid_memory.

Any code using:
    from hermes.memory.hybrid_memory import HybridMemoryManager
will now resolve correctly without a ModuleNotFoundError.
"""
from hermes.memory.hybrid_store import HybridMemoryManager  # noqa: F401

__all__ = ["HybridMemoryManager"]

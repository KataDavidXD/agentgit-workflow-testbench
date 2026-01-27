"""
State adapters - Anti-corruption layer implementations.

Refactored (v1.6):
- LangGraphStateAdapter: PRIMARY for all workflows (string IDs native)
- InMemoryStateAdapter: For testing (string IDs)
- AgentGitStateAdapter: REMOVED (use LangGraph instead)

All adapters now use string IDs throughout (UUIDs).
"""

from .inmemory_state_adapter import InMemoryStateAdapter

# Conditionally import LangGraphStateAdapter (requires langgraph package)
try:
    from .langgraph_state_adapter import (
        LangGraphStateAdapter,
        LangGraphConfig,
        LangGraphStateAdapterFactory,
        CheckpointerType,
        LANGGRAPH_AVAILABLE,
    )
    _HAS_LANGGRAPH = LANGGRAPH_AVAILABLE
except ImportError:
    LangGraphStateAdapter = None  # type: ignore
    LangGraphConfig = None  # type: ignore
    LangGraphStateAdapterFactory = None  # type: ignore
    CheckpointerType = None  # type: ignore
    _HAS_LANGGRAPH = False

__all__ = [
    "InMemoryStateAdapter",
    "LangGraphStateAdapter",
    "LangGraphConfig",
    "LangGraphStateAdapterFactory",
    "CheckpointerType",
    "LANGGRAPH_AVAILABLE",
]

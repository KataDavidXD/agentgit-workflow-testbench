"""
State adapters - Anti-corruption layer implementations.

Provides different implementations of IStateAdapter for various backends.
"""

from .inmemory_state_adapter import InMemoryStateAdapter

__all__ = [
    "InMemoryStateAdapter",
]


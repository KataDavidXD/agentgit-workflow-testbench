"""
Infrastructure Layer - Data access, external system adapters, and persistence.

This layer implements the interfaces defined in the domain layer,
handling all technical concerns like database access and external integrations.
"""

from .database.unit_of_work import SQLAlchemyUnitOfWork
from .adapters.inmemory_state_adapter import InMemoryStateAdapter

__all__ = [
    "SQLAlchemyUnitOfWork",
    "InMemoryStateAdapter",
]


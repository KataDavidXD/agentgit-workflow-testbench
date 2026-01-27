"""
Infrastructure Layer - Data access, external system adapters, and persistence.

This layer implements the interfaces defined in the domain layer,
handling all technical concerns like database access and external integrations.
"""

from .database.unit_of_work import SQLAlchemyUnitOfWork
from .adapters.inmemory_state_adapter import InMemoryStateAdapter

# Checkpoint Stores (DDD - 2026-01-15)
from .stores.inmemory_checkpoint_store import (
    InMemoryCheckpointStore,
    InMemoryCheckpointStoreFactory,
)
from .stores.langgraph_checkpoint_store import (
    LangGraphCheckpointStore,
    LangGraphCheckpointConfig,
    LangGraphCheckpointStoreFactory,
)

# Event Bus and Audit Trail
from .events.wtb_event_bus import (
    WTBEventBus,
    get_wtb_event_bus,
    set_wtb_event_bus,
    reset_wtb_event_bus,
)
from .events.wtb_audit_trail import (
    WTBAuditEventType,
    WTBAuditSeverity,
    WTBAuditEntry,
    WTBAuditTrail,
    AuditEventListener,
)

# Environment Providers
from .environment.providers import (
    InProcessEnvironmentProvider,
    RayEnvironmentProvider,
)

__all__ = [
    # Database
    "SQLAlchemyUnitOfWork",
    # Adapters (Legacy)
    "InMemoryStateAdapter",
    # Checkpoint Stores (DDD - 2026-01-15)
    "InMemoryCheckpointStore",
    "InMemoryCheckpointStoreFactory",
    "LangGraphCheckpointStore",
    "LangGraphCheckpointConfig",
    "LangGraphCheckpointStoreFactory",
    # Event Bus
    "WTBEventBus",
    "get_wtb_event_bus",
    "set_wtb_event_bus",
    "reset_wtb_event_bus",
    # Audit Trail
    "WTBAuditEventType",
    "WTBAuditSeverity",
    "WTBAuditEntry",
    "WTBAuditTrail",
    "AuditEventListener",
    # Environment Providers
    "InProcessEnvironmentProvider",
    "RayEnvironmentProvider",
]


"""
Infrastructure Layer - Data access, external system adapters, and persistence.

This layer implements the interfaces defined in the domain layer,
handling all technical concerns like database access and external integrations.
"""

from .database.unit_of_work import SQLAlchemyUnitOfWork
from .adapters.inmemory_state_adapter import InMemoryStateAdapter

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
    # Adapters
    "InMemoryStateAdapter",
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


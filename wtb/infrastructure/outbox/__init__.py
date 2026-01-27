"""
Outbox Pattern Infrastructure - Processor, Lifecycle, and Handlers.

v1.7 ISS-006 Resolution: Added lifecycle management with:
- OutboxLifecycleManager: Managed lifecycle with auto-start, health, graceful shutdown
- create_managed_processor: Factory for production use
"""

from .processor import OutboxProcessor
from .lifecycle import (
    OutboxLifecycleManager,
    LifecycleStatus,
    HealthStatus,
    create_managed_processor,
)

__all__ = [
    "OutboxProcessor",
    "OutboxLifecycleManager",
    "LifecycleStatus",
    "HealthStatus",
    "create_managed_processor",
]


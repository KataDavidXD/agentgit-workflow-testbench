"""
Infrastructure Events - WTB Event Bus and Audit Trail implementations.

Provides:
- WTBEventBus: Thread-safe event bus extending AgentGit EventBus
- WTBAuditTrail: Execution/Node-level audit tracking
- AuditEventListener: Auto-records WTB events to audit
"""

from .wtb_event_bus import (
    WTBEventBus,
    get_wtb_event_bus,
    set_wtb_event_bus,
    reset_wtb_event_bus,
)
from .wtb_audit_trail import (
    WTBAuditEventType,
    WTBAuditSeverity,
    WTBAuditEntry,
    WTBAuditTrail,
    AuditEventListener,
)

__all__ = [
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
]


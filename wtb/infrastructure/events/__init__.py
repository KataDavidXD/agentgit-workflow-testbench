"""
Infrastructure Events - WTB Event Bus, Audit Trail, and LangGraph/Ray Integration.

Provides:
- WTBEventBus: Thread-safe event bus extending AgentGit EventBus
- WTBAuditTrail: Execution/Node-level audit tracking
- AuditEventListener: Auto-records WTB events to audit
- LangGraphEventBridge: Bridge LangGraph events to WTB EventBus
- RayEventBridge: Bridge Ray batch test events to WTB EventBus (NEW)
- StreamModeConfig: LangGraph stream mode configuration
- MetricsEventListener: Prometheus metrics from events
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
from .stream_mode_config import (
    StreamMode,
    StreamModeConfig,
    get_stream_mode_for_environment,
)
from .langgraph_event_bridge import (
    LangGraphEventBridge,
    NodeExecutionTracker,
    create_event_bridge,
    create_event_bridge_for_testing,
    create_event_bridge_for_development,
)
from .metrics_event_listener import (
    MetricsEventListener,
    InMemoryMetricsCollector,
    PROMETHEUS_AVAILABLE,
)
from .ray_event_bridge import (
    RayEventBridge,
    serialize_ray_event,
    deserialize_ray_event,
    get_ray_event_bridge,
    set_ray_event_bridge,
    reset_ray_event_bridge,
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
    # Stream Mode Config
    "StreamMode",
    "StreamModeConfig",
    "get_stream_mode_for_environment",
    # LangGraph Event Bridge
    "LangGraphEventBridge",
    "NodeExecutionTracker",
    "create_event_bridge",
    "create_event_bridge_for_testing",
    "create_event_bridge_for_development",
    # Metrics
    "MetricsEventListener",
    "InMemoryMetricsCollector",
    "PROMETHEUS_AVAILABLE",
    # Ray Event Bridge
    "RayEventBridge",
    "serialize_ray_event",
    "deserialize_ray_event",
    "get_ray_event_bridge",
    "set_ray_event_bridge",
    "reset_ray_event_bridge",
]


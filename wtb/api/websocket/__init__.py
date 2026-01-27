"""
WebSocket API for real-time updates.

Provides:
- Topic-based subscriptions
- Broadcast to subscribers
- Heartbeat/keepalive
- Event bridge from WTBEventBus
"""

from .handlers import (
    ConnectionManager,
    get_connection_manager,
    websocket_endpoint,
)

__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "websocket_endpoint",
]

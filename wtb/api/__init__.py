"""
WTB External API Layer.

Provides:
- REST API (FastAPI) - Port 8000
- WebSocket for real-time updates - Port 8000/ws
- gRPC API for internal services - Port 50051

Architecture Decision (2026-01-15):
═══════════════════════════════════════════════════════════════════════════════

Protocol Selection:
- REST: Web UI, external clients, CRUD operations
- WebSocket: Real-time UI updates, execution progress
- gRPC: Internal services, Ray workers, streaming

All protocols share the same Application Service Layer for consistent behavior.

Note: FastAPI is an optional dependency. Import create_app/get_app only when needed.
"""

# Lazy imports - FastAPI is optional
def create_app(*args, **kwargs):
    """Create FastAPI app. Requires fastapi to be installed."""
    from .rest.app import create_app as _create_app
    return _create_app(*args, **kwargs)

def get_app(*args, **kwargs):
    """Get FastAPI app instance. Requires fastapi to be installed."""
    from .rest.app import get_app as _get_app
    return _get_app(*args, **kwargs)

__all__ = [
    "create_app",
    "get_app",
]

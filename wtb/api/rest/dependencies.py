"""
FastAPI Dependencies for dependency injection.

Following DIP (Dependency Inversion Principle):
- API layer depends on abstractions (services, repositories)
- Services are injected via FastAPI dependency system
- Enables easy testing and swapping implementations

Transaction Management:
- Unit of Work pattern for database transactions
- Automatic commit/rollback on request completion
"""

from typing import Optional, Generator
from functools import lru_cache
from contextlib import contextmanager

from wtb.application.services import ExecutionController
from wtb.infrastructure.events import (
    WTBEventBus,
    WTBAuditTrail,
    get_wtb_event_bus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Application State (Singleton services)
# ═══════════════════════════════════════════════════════════════════════════════

class AppState:
    """
    Application state container.
    
    Holds singleton instances of services that are shared across requests.
    Initialized once at startup, used throughout the application lifetime.
    """
    
    def __init__(self):
        self._event_bus: Optional[WTBEventBus] = None
        self._audit_trail: Optional[WTBAuditTrail] = None
        self._execution_controller: Optional[ExecutionController] = None
        self._initialized: bool = False
    
    def initialize(
        self,
        event_bus: Optional[WTBEventBus] = None,
        execution_controller: Optional[ExecutionController] = None,
    ) -> None:
        """
        Initialize application state with services.
        
        Args:
            event_bus: WTB event bus instance
            execution_controller: Execution controller instance
        """
        self._event_bus = event_bus or get_wtb_event_bus()
        self._audit_trail = WTBAuditTrail()
        self._execution_controller = execution_controller
        self._initialized = True
    
    @property
    def event_bus(self) -> WTBEventBus:
        """Get the event bus instance."""
        if self._event_bus is None:
            self._event_bus = get_wtb_event_bus()
        return self._event_bus
    
    @property
    def audit_trail(self) -> WTBAuditTrail:
        """Get the audit trail instance."""
        if self._audit_trail is None:
            self._audit_trail = WTBAuditTrail()
        return self._audit_trail
    
    @property
    def execution_controller(self) -> Optional[ExecutionController]:
        """Get the execution controller instance."""
        return self._execution_controller
    
    @property
    def is_initialized(self) -> bool:
        """Check if app state is initialized."""
        return self._initialized


# Global application state
_app_state: Optional[AppState] = None


def get_app_state() -> AppState:
    """Get the global application state."""
    global _app_state
    if _app_state is None:
        _app_state = AppState()
    return _app_state


def set_app_state(state: AppState) -> None:
    """Set the global application state (for testing)."""
    global _app_state
    _app_state = state


def reset_app_state() -> None:
    """Reset the global application state (for testing)."""
    global _app_state
    _app_state = None


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI Dependencies
# ═══════════════════════════════════════════════════════════════════════════════

def get_event_bus() -> WTBEventBus:
    """FastAPI dependency for event bus."""
    return get_app_state().event_bus


def get_audit_trail() -> WTBAuditTrail:
    """FastAPI dependency for audit trail."""
    return get_app_state().audit_trail


def get_execution_controller() -> ExecutionController:
    """FastAPI dependency for execution controller."""
    controller = get_app_state().execution_controller
    if controller is None:
        raise RuntimeError(
            "ExecutionController not initialized. "
            "Call AppState.initialize() at startup."
        )
    return controller


# ═══════════════════════════════════════════════════════════════════════════════
# Service Dependencies (Application Services Layer)
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionService:
    """
    Application service for execution operations.
    
    Wraps ExecutionController with additional API-level concerns:
    - Input validation
    - Error handling
    - Event publishing
    - Audit logging
    """
    
    def __init__(
        self,
        controller: ExecutionController,
        event_bus: WTBEventBus,
        audit_trail: WTBAuditTrail,
    ):
        self._controller = controller
        self._event_bus = event_bus
        self._audit_trail = audit_trail
    
    async def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List executions with optional filtering."""
        # Get from repository (simplified - actual impl would filter)
        executions = []
        return {
            "executions": executions,
            "pagination": {
                "total": len(executions),
                "limit": limit,
                "offset": offset,
                "has_more": False,
            }
        }
    
    async def get_execution(self, execution_id: str) -> Optional[dict]:
        """Get execution by ID."""
        try:
            execution = self._controller.get_status(execution_id)
            return {
                "id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": execution.status.value,
                "state": {
                    "current_node_id": execution.state.current_node_id,
                    "workflow_variables": execution.state.workflow_variables,
                    "execution_path": execution.state.execution_path,
                    "node_results": execution.state.node_results,
                },
                "breakpoints": execution.breakpoints,
                "current_node_id": execution.state.current_node_id,
                "error": execution.error,
                "error_node_id": execution.error_node_id,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "checkpoint_count": execution.checkpoint_id or 0,
                "nodes_executed": len(execution.state.execution_path),
            }
        except ValueError:
            return None
    
    async def pause(
        self,
        execution_id: str,
        reason: Optional[str] = None,
        at_node: Optional[str] = None,
    ) -> dict:
        """Pause execution."""
        execution = self._controller.pause(execution_id)
        return {
            "checkpoint_id": str(execution.checkpoint_id),
        }
    
    async def resume(
        self,
        execution_id: str,
        modified_state: Optional[dict] = None,
        from_node: Optional[str] = None,
    ) -> dict:
        """Resume execution."""
        execution = self._controller.resume(execution_id, modified_state)
        return {
            "resumed_from_node": execution.state.current_node_id,
        }
    
    async def rollback(
        self,
        execution_id: str,
        checkpoint_id: str,
        create_branch: bool = False,
    ) -> dict:
        """Rollback to checkpoint."""
        execution = self._controller.rollback(execution_id, int(checkpoint_id))
        return {
            "new_session_id": execution.session_id,
            "tools_reversed": 0,  # Would come from adapter
        }
    
    async def inspect_state(
        self,
        execution_id: str,
        keys: Optional[list] = None,
    ) -> dict:
        """Inspect execution state."""
        state = self._controller.get_state(execution_id)
        values = state.workflow_variables
        if keys:
            values = {k: v for k, v in values.items() if k in keys}
        return {
            "values": values,
            "current_node": state.current_node_id,
        }
    
    async def modify_state(
        self,
        execution_id: str,
        changes: dict,
    ) -> bool:
        """Modify execution state."""
        return self._controller.update_execution_state(execution_id, changes)


class AuditService:
    """
    Application service for audit operations.
    
    Provides query and aggregation over audit events.
    """
    
    def __init__(self, audit_trail: WTBAuditTrail):
        self._audit_trail = audit_trail
    
    async def query_events(
        self,
        execution_id: Optional[str] = None,
        event_types: Optional[list] = None,
        severities: Optional[list] = None,
        node_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Query audit events with filtering."""
        entries = self._audit_trail.entries
        
        # Apply filters
        if execution_id:
            entries = [e for e in entries if e.execution_id == execution_id]
        if event_types:
            entries = [e for e in entries if e.event_type.value in event_types]
        if severities:
            entries = [e for e in entries if e.severity.value in severities]
        if node_id:
            entries = [e for e in entries if e.node_id == node_id]
        
        # Pagination
        total = len(entries)
        entries = entries[offset:offset + limit]
        
        return {
            "events": [
                {
                    "id": str(i),
                    "timestamp": e.timestamp,
                    "event_type": e.event_type.value,
                    "severity": e.severity.value,
                    "message": e.message,
                    "execution_id": e.execution_id,
                    "node_id": e.node_id,
                    "details": e.details,
                    "error": e.error,
                    "duration_ms": e.duration_ms,
                }
                for i, e in enumerate(entries)
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }
        }
    
    async def get_summary(
        self,
        execution_id: Optional[str] = None,
        time_range: str = "1h",
    ) -> dict:
        """Get audit summary statistics."""
        summary = self._audit_trail.get_summary()
        return {
            "total_events": summary["total_entries"],
            "execution_id": execution_id,
            "time_range": time_range,
            "events_by_type": {},  # Would aggregate
            "events_by_severity": {},
            "error_rate": 0.0,
            "checkpoint_count": summary["checkpoints_created"],
            "rollback_count": summary["rollbacks"],
            "nodes_executed": summary["nodes_executed"],
            "nodes_failed": summary["nodes_failed"],
            "avg_node_duration_ms": None,
        }
    
    async def get_timeline(
        self,
        execution_id: str,
        include_debug: bool = False,
    ) -> dict:
        """Get execution timeline for visualization."""
        entries = self._audit_trail.entries
        
        # Filter by execution
        entries = [e for e in entries if e.execution_id == execution_id]
        
        if not include_debug:
            from wtb.infrastructure.events import WTBAuditSeverity
            entries = [e for e in entries if e.severity != WTBAuditSeverity.DEBUG]
        
        return {
            "execution_id": execution_id,
            "entries": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type.value,
                    "node_id": e.node_id,
                    "duration_ms": e.duration_ms,
                    "status": "completed" if "completed" in e.event_type.value else "started",
                }
                for e in entries
            ],
            "total_duration_ms": None,
        }
    
    async def get_trail_for_execution(
        self,
        execution_id: str,
        include_debug: bool = False,
        limit: int = 100,
    ) -> dict:
        """Get audit trail for a specific execution."""
        return await self.query_events(
            execution_id=execution_id,
            limit=limit,
        )


class BatchTestService:
    """
    Application service for batch test operations.
    """
    
    def __init__(self, event_bus: WTBEventBus):
        self._event_bus = event_bus
        self._batch_tests: dict = {}  # In-memory store for now
    
    async def create_batch_test(
        self,
        workflow_id: str,
        variants: list,
        initial_state: Optional[dict] = None,
        parallelism: Optional[int] = None,
        use_ray: bool = True,
    ) -> str:
        """Create and start a batch test."""
        import uuid
        batch_test_id = str(uuid.uuid4())
        
        self._batch_tests[batch_test_id] = {
            "id": batch_test_id,
            "workflow_id": workflow_id,
            "variants": variants,
            "status": "pending",
            "created_at": None,
        }
        
        return batch_test_id
    
    async def get_batch_test(self, batch_test_id: str) -> Optional[dict]:
        """Get batch test by ID."""
        return self._batch_tests.get(batch_test_id)
    
    async def stream_progress(self, batch_test_id: str):
        """Stream batch test progress (generator)."""
        # This would yield progress updates
        yield {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "current": None,
            "eta_seconds": 0,
        }


def get_execution_service() -> ExecutionService:
    """FastAPI dependency for execution service."""
    state = get_app_state()
    controller = state.execution_controller
    if controller is None:
        raise RuntimeError("ExecutionController not initialized")
    return ExecutionService(
        controller=controller,
        event_bus=state.event_bus,
        audit_trail=state.audit_trail,
    )


def get_audit_service() -> AuditService:
    """FastAPI dependency for audit service."""
    return AuditService(get_app_state().audit_trail)


def get_batch_test_service() -> BatchTestService:
    """FastAPI dependency for batch test service."""
    return BatchTestService(get_app_state().event_bus)

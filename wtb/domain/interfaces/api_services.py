"""
API Service Interfaces - Abstract contracts for API-level operations.

Created: 2026-01-28
Status: Active
Reference: SOLID principles, DIP (Dependency Inversion Principle)

Design Principles:
- ISP: Separate interfaces for different operation domains
- DIP: API layer depends on abstractions, not concrete implementations
- SRP: Each interface has a single responsibility

Architecture:
    REST/gRPC Endpoints
           │
           ▼
    IExecutionAPIService (abstraction)
           │
           ▼
    ExecutionAPIService (concrete)
           │
           ├──► IUnitOfWork (transaction boundary)
           ├──► IExecutionController (domain operations)
           └──► IEventBus (async events)

ACID Compliance:
- All operations wrapped in Unit of Work transactions
- Automatic rollback on failure
- Audit logging for all state changes
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Result DTOs for API Operations
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ExecutionDTO:
    """Data Transfer Object for Execution."""
    id: str
    workflow_id: str
    status: str
    state: Dict[str, Any]
    breakpoints: List[str] = field(default_factory=list)
    current_node_id: Optional[str] = None
    error: Optional[str] = None
    error_node_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checkpoint_count: int = 0
    nodes_executed: int = 0
    thread_id: Optional[str] = None


@dataclass
class ControlResultDTO:
    """Result of a control operation (pause, resume, stop)."""
    success: bool
    status: str
    checkpoint_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RollbackResultDTO:
    """Result of a rollback operation."""
    success: bool
    to_checkpoint: str
    new_session_id: Optional[str] = None
    tools_reversed: int = 0
    files_restored: int = 0
    restored_state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None  # Error message if success=False


@dataclass
class CheckpointDTO:
    """Data Transfer Object for Checkpoint."""
    id: str
    execution_id: str
    node_id: Optional[str] = None
    trigger_type: str = "auto"
    created_at: Optional[datetime] = None
    state_snapshot: Optional[Dict[str, Any]] = None
    has_file_commit: bool = False
    file_commit_id: Optional[str] = None


@dataclass
class PaginatedResultDTO:
    """Paginated result container."""
    items: List[Any]
    total: int
    limit: int
    offset: int
    has_more: bool


@dataclass
class AuditEventDTO:
    """Data Transfer Object for Audit Event."""
    id: str
    timestamp: datetime
    event_type: str
    severity: str
    message: str
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class AuditSummaryDTO:
    """Audit summary statistics."""
    total_events: int
    execution_id: Optional[str] = None
    time_range: str = "1h"
    events_by_type: Dict[str, int] = field(default_factory=dict)
    events_by_severity: Dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0
    checkpoint_count: int = 0
    rollback_count: int = 0
    nodes_executed: int = 0
    nodes_failed: int = 0
    avg_node_duration_ms: Optional[float] = None


@dataclass
class BatchTestDTO:
    """Data Transfer Object for Batch Test."""
    id: str
    workflow_id: str
    status: str
    variant_count: int
    variants_completed: int = 0
    variants_failed: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    comparison_matrix: Optional[Dict[str, Any]] = None
    best_variant: Optional[str] = None


@dataclass
class BatchTestProgressDTO:
    """Progress update for batch test."""
    batch_test_id: str
    total: int
    completed: int
    failed: int
    current: Optional[str] = None
    eta_seconds: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Execution API Service Interface
# ═══════════════════════════════════════════════════════════════════════════════


class IExecutionAPIService(ABC):
    """
    Interface for execution API operations.
    
    Provides ACID-compliant operations for managing workflow executions
    through the API layer. All operations are wrapped in transactions.
    
    SOLID Compliance:
    - SRP: Only handles execution-related API operations
    - ISP: Separate from audit and batch test interfaces
    - DIP: API layer depends on this abstraction
    """
    
    @abstractmethod
    async def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResultDTO:
        """
        List executions with optional filtering.
        
        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status
            limit: Maximum items to return
            offset: Pagination offset
            
        Returns:
            Paginated list of ExecutionDTO
        """
        pass
    
    @abstractmethod
    async def get_execution(self, execution_id: str) -> Optional[ExecutionDTO]:
        """
        Get execution by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionDTO if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def pause_execution(
        self,
        execution_id: str,
        reason: Optional[str] = None,
        at_node: Optional[str] = None,
    ) -> ControlResultDTO:
        """
        Pause a running execution.
        
        ACID: Creates checkpoint atomically.
        
        Args:
            execution_id: Execution to pause
            reason: Pause reason
            at_node: Optional node to pause at
            
        Returns:
            Control result with checkpoint ID
        """
        pass
    
    @abstractmethod
    async def resume_execution(
        self,
        execution_id: str,
        modified_state: Optional[Dict[str, Any]] = None,
        from_node: Optional[str] = None,
    ) -> ControlResultDTO:
        """
        Resume a paused execution.
        
        ACID: State modifications applied atomically.
        
        Args:
            execution_id: Execution to resume
            modified_state: Optional state modifications (HITL)
            from_node: Optional node to resume from
            
        Returns:
            Control result
        """
        pass
    
    @abstractmethod
    async def stop_execution(
        self,
        execution_id: str,
        reason: Optional[str] = None,
    ) -> ControlResultDTO:
        """
        Stop and cancel an execution.
        
        ACID: Final checkpoint created before stop.
        
        Args:
            execution_id: Execution to stop
            reason: Stop reason
            
        Returns:
            Control result
        """
        pass
    
    @abstractmethod
    async def rollback_execution(
        self,
        execution_id: str,
        checkpoint_id: str,
        create_branch: bool = False,
    ) -> RollbackResultDTO:
        """
        Rollback execution to a checkpoint.
        
        ACID: Rollback is atomic - either fully applied or not at all.
        
        Args:
            execution_id: Execution to rollback
            checkpoint_id: Target checkpoint (UUID string)
            create_branch: Create new branch instead of in-place rollback
            
        Returns:
            Rollback result with details
        """
        pass
    
    @abstractmethod
    async def get_execution_state(
        self,
        execution_id: str,
        keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get current execution state.
        
        Args:
            execution_id: Execution ID
            keys: Optional specific keys to retrieve
            
        Returns:
            State values
        """
        pass
    
    @abstractmethod
    async def modify_execution_state(
        self,
        execution_id: str,
        changes: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> ControlResultDTO:
        """
        Modify execution state (human-in-the-loop).
        
        ACID: Creates checkpoint before modification.
        
        Args:
            execution_id: Execution ID
            changes: State changes to apply
            reason: Modification reason
            
        Returns:
            Control result
        """
        pass
    
    @abstractmethod
    async def list_checkpoints(
        self,
        execution_id: str,
        limit: int = 100,
    ) -> List[CheckpointDTO]:
        """
        List checkpoints for an execution.
        
        Args:
            execution_id: Execution ID
            limit: Maximum checkpoints to return
            
        Returns:
            List of checkpoints
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Audit API Service Interface
# ═══════════════════════════════════════════════════════════════════════════════


class IAuditAPIService(ABC):
    """
    Interface for audit API operations.
    
    Provides read-only access to audit events and analytics.
    
    SOLID Compliance:
    - SRP: Only handles audit-related operations
    - ISP: Separate from execution and batch test
    """
    
    @abstractmethod
    async def query_events(
        self,
        execution_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        node_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResultDTO:
        """
        Query audit events with filtering.
        
        Args:
            execution_id: Filter by execution
            event_types: Filter by event types
            severities: Filter by severities
            node_id: Filter by node
            since: Events after this time
            until: Events before this time
            limit: Maximum items
            offset: Pagination offset
            
        Returns:
            Paginated list of AuditEventDTO
        """
        pass
    
    @abstractmethod
    async def get_summary(
        self,
        execution_id: Optional[str] = None,
        time_range: str = "1h",
    ) -> AuditSummaryDTO:
        """
        Get audit summary statistics.
        
        Args:
            execution_id: Filter by execution
            time_range: Time range (1h, 24h, 7d)
            
        Returns:
            Summary statistics
        """
        pass
    
    @abstractmethod
    async def get_timeline(
        self,
        execution_id: str,
        include_debug: bool = False,
    ) -> List[AuditEventDTO]:
        """
        Get execution timeline for visualization.
        
        Args:
            execution_id: Execution ID
            include_debug: Include debug-level events
            
        Returns:
            Timeline of audit events
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Test API Service Interface
# ═══════════════════════════════════════════════════════════════════════════════


class IBatchTestAPIService(ABC):
    """
    Interface for batch test API operations.
    
    Provides ACID-compliant batch test management.
    
    SOLID Compliance:
    - SRP: Only handles batch test operations
    - ISP: Separate from execution and audit
    """
    
    @abstractmethod
    async def create_batch_test(
        self,
        workflow_id: str,
        variants: List[Dict[str, Any]],
        initial_state: Optional[Dict[str, Any]] = None,
        parallelism: Optional[int] = None,
        use_ray: bool = True,
    ) -> BatchTestDTO:
        """
        Create and start a batch test.
        
        ACID: Batch test record created atomically.
        
        Args:
            workflow_id: Workflow to test
            variants: Variant configurations
            initial_state: Initial state for all variants
            parallelism: Number of parallel workers
            use_ray: Use Ray for execution
            
        Returns:
            Created batch test DTO
        """
        pass
    
    @abstractmethod
    async def get_batch_test(self, batch_test_id: str) -> Optional[BatchTestDTO]:
        """
        Get batch test by ID.
        
        Args:
            batch_test_id: Batch test ID
            
        Returns:
            BatchTestDTO if found
        """
        pass
    
    @abstractmethod
    async def list_batch_tests(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResultDTO:
        """
        List batch tests with filtering.
        
        Args:
            workflow_id: Filter by workflow
            status: Filter by status
            limit: Maximum items
            offset: Pagination offset
            
        Returns:
            Paginated list of BatchTestDTO
        """
        pass
    
    @abstractmethod
    async def stream_progress(
        self,
        batch_test_id: str,
    ) -> AsyncIterator[BatchTestProgressDTO]:
        """
        Stream batch test progress updates.
        
        Args:
            batch_test_id: Batch test ID
            
        Yields:
            Progress updates
        """
        pass
    
    @abstractmethod
    async def cancel_batch_test(
        self,
        batch_test_id: str,
        reason: Optional[str] = None,
    ) -> ControlResultDTO:
        """
        Cancel a running batch test.
        
        ACID: Cancellation recorded atomically.
        
        Args:
            batch_test_id: Batch test to cancel
            reason: Cancellation reason
            
        Returns:
            Control result
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow API Service Interface
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WorkflowDTO:
    """Data Transfer Object for Workflow."""
    id: str
    name: str
    description: Optional[str] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    entry_point: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1


class IWorkflowAPIService(ABC):
    """
    Interface for workflow API operations.
    
    Provides CRUD operations for workflow definitions.
    """
    
    @abstractmethod
    async def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        entry_point: str,
        description: Optional[str] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowDTO:
        """Create a new workflow definition."""
        pass
    
    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowDTO]:
        """Get workflow by ID."""
        pass
    
    @abstractmethod
    async def list_workflows(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResultDTO:
        """List workflows with pagination."""
        pass
    
    @abstractmethod
    async def update_workflow(
        self,
        workflow_id: str,
        **updates,
    ) -> WorkflowDTO:
        """Update workflow definition."""
        pass
    
    @abstractmethod
    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow definition."""
        pass


__all__ = [
    # DTOs
    "ExecutionDTO",
    "ControlResultDTO",
    "RollbackResultDTO",
    "CheckpointDTO",
    "PaginatedResultDTO",
    "AuditEventDTO",
    "AuditSummaryDTO",
    "BatchTestDTO",
    "BatchTestProgressDTO",
    "WorkflowDTO",
    # Interfaces
    "IExecutionAPIService",
    "IAuditAPIService",
    "IBatchTestAPIService",
    "IWorkflowAPIService",
]

"""
REST API Pydantic Models (Request/Response Schemas).

Following SOLID principles:
- Single Responsibility: Each model represents one concept
- Open/Closed: Extensible via inheritance
- Interface Segregation: Separate request/response models

ACID Compliance:
- All models support serialization for audit logging
- Validation ensures data consistency
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionStatusEnum(str, Enum):
    """Execution status enum for API."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditEventTypeEnum(str, Enum):
    """Audit event type enum for API."""
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    CHECKPOINT_CREATED = "checkpoint_created"
    ROLLBACK_PERFORMED = "rollback_performed"
    BRANCH_CREATED = "branch_created"
    STATE_MODIFIED = "state_modified"
    BREAKPOINT_HIT = "breakpoint_hit"
    # Ray events
    RAY_BATCH_TEST_STARTED = "ray_batch_test_started"
    RAY_BATCH_TEST_COMPLETED = "ray_batch_test_completed"
    RAY_BATCH_TEST_FAILED = "ray_batch_test_failed"
    RAY_VARIANT_EXECUTION_COMPLETED = "ray_variant_execution_completed"


class AuditSeverityEnum(str, Enum):
    """Audit severity enum for API."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class BatchTestStatusEnum(str, Enum):
    """Batch test status enum for API."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# Common Models
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, str] = Field(
        default_factory=dict, 
        description="Component health status"
    )


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether more items exist")


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Models
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowNodeSchema(BaseModel):
    """Node definition in a workflow."""
    id: str = Field(..., description="Node ID")
    name: str = Field(..., description="Node name")
    type: str = Field(..., description="Node type (action, decision, start, end)")
    tool_name: Optional[str] = Field(None, description="Tool name for action nodes")
    config: Optional[Dict[str, Any]] = Field(None, description="Node configuration")


class WorkflowEdgeSchema(BaseModel):
    """Edge definition in a workflow."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    condition: Optional[str] = Field(None, description="Edge condition expression")


class WorkflowCreateRequest(BaseModel):
    """Request to create a workflow."""
    name: str = Field(..., min_length=1, max_length=100, description="Workflow name")
    description: Optional[str] = Field(None, max_length=500)
    nodes: List[WorkflowNodeSchema] = Field(..., min_length=1)
    edges: List[WorkflowEdgeSchema] = Field(default_factory=list)
    entry_point: str = Field(..., description="Entry node ID")
    metadata: Optional[Dict[str, Any]] = Field(None)


class WorkflowUpdateRequest(BaseModel):
    """Request to update a workflow."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    nodes: Optional[List[WorkflowNodeSchema]] = None
    edges: Optional[List[WorkflowEdgeSchema]] = None
    entry_point: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowResponse(BaseModel):
    """Workflow response."""
    id: str = Field(..., description="Workflow ID")
    name: str
    description: Optional[str] = None
    nodes: List[WorkflowNodeSchema]
    edges: List[WorkflowEdgeSchema]
    entry_point: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(default=1, description="Workflow version")
    
    model_config = ConfigDict(from_attributes=True)


class WorkflowListResponse(BaseModel):
    """List of workflows response."""
    workflows: List[WorkflowResponse]
    pagination: PaginationMeta


# ═══════════════════════════════════════════════════════════════════════════════
# Execution Models
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionCreateRequest(BaseModel):
    """Request to create/start an execution."""
    workflow_id: str = Field(..., description="Workflow to execute")
    initial_state: Optional[Dict[str, Any]] = Field(
        None, 
        description="Initial state variables"
    )
    breakpoints: Optional[List[str]] = Field(
        None, 
        description="Node IDs to break at"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution configuration"
    )


class ExecutionConfigSchema(BaseModel):
    """Execution configuration."""
    enable_file_tracking: bool = Field(default=True)
    enable_audit: bool = Field(default=True)
    checkpoint_interval: int = Field(default=0, description="0 = every node")
    metadata: Optional[Dict[str, Any]] = None


class ExecutionStateSchema(BaseModel):
    """Current execution state."""
    current_node_id: Optional[str] = None
    workflow_variables: Dict[str, Any] = Field(default_factory=dict)
    execution_path: List[str] = Field(default_factory=list)
    node_results: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    """Execution response."""
    id: str = Field(..., description="Execution ID")
    workflow_id: str
    workflow_name: Optional[str] = None
    status: ExecutionStatusEnum
    state: ExecutionStateSchema
    breakpoints: List[str] = Field(default_factory=list)
    current_node_id: Optional[str] = None
    error: Optional[str] = None
    error_node_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    checkpoint_count: int = Field(default=0)
    nodes_executed: int = Field(default=0)
    thread_id: Optional[str] = Field(None, description="LangGraph thread ID")
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionListResponse(BaseModel):
    """List of executions response."""
    executions: List[ExecutionResponse]
    pagination: PaginationMeta


class PauseRequest(BaseModel):
    """Request to pause an execution."""
    reason: Optional[str] = Field(None, max_length=500, description="Pause reason")
    at_node: Optional[str] = Field(None, description="Node ID to pause at")


class ResumeRequest(BaseModel):
    """Request to resume an execution."""
    modified_state: Optional[Dict[str, Any]] = Field(
        None,
        description="State modifications before resume"
    )
    from_node: Optional[str] = Field(
        None,
        description="Node ID to resume from"
    )


class RollbackRequest(BaseModel):
    """Request to rollback an execution."""
    checkpoint_id: str = Field(..., description="Checkpoint ID to rollback to")
    create_branch: bool = Field(
        default=False,
        description="Create a new branch instead of modifying in-place"
    )


class RollbackResponse(BaseModel):
    """Rollback operation response."""
    success: bool
    to_checkpoint: str
    new_session_id: Optional[str] = Field(
        None, 
        description="New session ID if branch created"
    )
    tools_reversed: int = Field(default=0)
    files_restored: int = Field(default=0)
    restored_state: Optional[Dict[str, Any]] = None


class StateModifyRequest(BaseModel):
    """Request to modify execution state (human-in-the-loop)."""
    changes: Dict[str, Any] = Field(..., description="State changes to apply")
    reason: Optional[str] = Field(None, max_length=500, description="Modification reason")


class ControlResponse(BaseModel):
    """Generic control operation response."""
    success: bool
    status: ExecutionStatusEnum
    checkpoint_id: Optional[str] = None
    message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint Models
# ═══════════════════════════════════════════════════════════════════════════════

class CheckpointResponse(BaseModel):
    """Checkpoint response."""
    id: str = Field(..., description="Checkpoint ID")
    execution_id: str
    node_id: Optional[str] = None
    trigger_type: str = Field(..., description="auto, manual, breakpoint")
    created_at: datetime
    state_snapshot: Optional[Dict[str, Any]] = None
    has_file_commit: bool = Field(default=False)
    file_commit_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CheckpointListResponse(BaseModel):
    """List of checkpoints response."""
    checkpoints: List[CheckpointResponse]
    execution_id: str
    total: int


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Models
# ═══════════════════════════════════════════════════════════════════════════════

class AuditEventResponse(BaseModel):
    """Audit event response."""
    id: str = Field(default="", description="Event ID")
    timestamp: datetime
    event_type: AuditEventTypeEnum
    severity: AuditSeverityEnum
    message: str
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


class AuditEventListResponse(BaseModel):
    """List of audit events response."""
    events: List[AuditEventResponse]
    pagination: PaginationMeta


class AuditSummaryResponse(BaseModel):
    """Audit summary statistics."""
    total_events: int
    execution_id: Optional[str] = None
    time_range: str
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    error_rate: float = Field(default=0.0, description="Error rate percentage")
    checkpoint_count: int = Field(default=0)
    rollback_count: int = Field(default=0)
    nodes_executed: int = Field(default=0)
    nodes_failed: int = Field(default=0)
    avg_node_duration_ms: Optional[float] = None


class AuditTimelineEntry(BaseModel):
    """Timeline entry for visualization."""
    timestamp: datetime
    event_type: str
    node_id: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str  # started, completed, failed, skipped


class AuditTimelineResponse(BaseModel):
    """Execution timeline for visualization."""
    execution_id: str
    entries: List[AuditTimelineEntry]
    total_duration_ms: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Test Models
# ═══════════════════════════════════════════════════════════════════════════════

class VariantCombinationRequest(BaseModel):
    """A variant combination for batch testing."""
    name: str = Field(..., description="Combination name")
    node_variants: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of node_id to variant_id"
    )
    workflow_variant: Optional[str] = Field(
        None,
        description="Workflow-level variant name"
    )


class BatchTestCreateRequest(BaseModel):
    """Request to create/run a batch test."""
    workflow_id: str = Field(..., description="Workflow to test")
    variants: List[VariantCombinationRequest] = Field(
        ...,
        min_length=1,
        description="Variant combinations to test"
    )
    initial_state: Optional[Dict[str, Any]] = Field(
        None,
        description="Initial state for all variants"
    )
    test_cases: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Multiple test cases to run"
    )
    parallelism: Optional[int] = Field(
        None,
        ge=1,
        description="Number of parallel workers (0=auto)"
    )
    use_ray: bool = Field(default=True, description="Use Ray for execution")
    enable_file_tracking: bool = Field(default=True)


class VariantResultSchema(BaseModel):
    """Result for a single variant execution."""
    variant_name: str
    status: Literal["completed", "failed", "cancelled"]
    metrics: Dict[str, float] = Field(default_factory=dict)
    overall_score: float = Field(default=0.0)
    duration_ms: float = Field(default=0.0)
    error: Optional[str] = None
    checkpoint_count: int = Field(default=0)
    nodes_executed: int = Field(default=0)
    file_commit_id: Optional[str] = None


class ComparisonMatrixResponse(BaseModel):
    """Comparison matrix for batch test results."""
    metric_names: List[str]
    variants: List[VariantResultSchema]
    best_variant: Optional[str] = None
    best_score: Optional[float] = None


class BatchTestProgressSchema(BaseModel):
    """Progress update for batch test."""
    batch_test_id: str
    total_variants: int
    completed: int
    failed: int
    pending: int
    current_variant: Optional[str] = None
    current_progress_percent: float = Field(default=0.0)
    eta_seconds: Optional[float] = None


class BatchTestResponse(BaseModel):
    """Batch test response."""
    id: str = Field(..., description="Batch test ID")
    workflow_id: str
    workflow_name: Optional[str] = None
    status: BatchTestStatusEnum
    variant_count: int
    variants_completed: int = Field(default=0)
    variants_failed: int = Field(default=0)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    comparison_matrix: Optional[ComparisonMatrixResponse] = None
    best_variant: Optional[str] = None
    use_ray: bool = Field(default=True)
    
    model_config = ConfigDict(from_attributes=True)


class BatchTestListResponse(BaseModel):
    """List of batch tests response."""
    batch_tests: List[BatchTestResponse]
    pagination: PaginationMeta


# ═══════════════════════════════════════════════════════════════════════════════
# Node Models (Fine-Grained Control)
# ═══════════════════════════════════════════════════════════════════════════════

class NodeExecutionStatusSchema(BaseModel):
    """Node execution status within an execution."""
    node_id: str
    node_name: str
    node_type: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    checkpoint_id: Optional[str] = None


class ExecuteSingleNodeRequest(BaseModel):
    """Request to execute a single node."""
    input_state: Optional[Dict[str, Any]] = Field(
        None,
        description="Input state override"
    )


class NodeBatchTestRequest(BaseModel):
    """Request to batch test a single node with variants."""
    variants: List[str] = Field(..., min_length=1, description="Variant names to test")
    input_state: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Branch Models
# ═══════════════════════════════════════════════════════════════════════════════

class BranchCreateRequest(BaseModel):
    """Request to create a branch from checkpoint."""
    checkpoint_id: str = Field(..., description="Checkpoint to branch from")
    name: Optional[str] = Field(None, max_length=100, description="Branch name")
    description: Optional[str] = Field(None, max_length=500)


class BranchResponse(BaseModel):
    """Branch response."""
    id: str = Field(..., description="Branch ID")
    parent_execution_id: str
    from_checkpoint_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    execution_id: str = Field(..., description="New execution ID for the branch")
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BranchListResponse(BaseModel):
    """List of branches response."""
    branches: List[BranchResponse]
    parent_execution_id: str
    total: int


# ═══════════════════════════════════════════════════════════════════════════════
# Variant Registry Models
# ═══════════════════════════════════════════════════════════════════════════════

class VariantCreateRequest(BaseModel):
    """Request to register a variant."""
    node_id: str = Field(..., description="Node this variant applies to")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    implementation_path: str = Field(
        ..., 
        description="Module path to implementation (e.g., 'myapp.variants:func')"
    )
    environment: Optional[Dict[str, Any]] = Field(
        None,
        description="Environment specification"
    )
    resources: Optional[Dict[str, Any]] = Field(
        None,
        description="Resource allocation"
    )


class VariantResponse(BaseModel):
    """Variant response."""
    id: str
    node_id: str
    name: str
    description: Optional[str] = None
    implementation_path: str
    environment: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class VariantListResponse(BaseModel):
    """List of variants response."""
    variants: List[VariantResponse]
    pagination: PaginationMeta


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket Models
# ═══════════════════════════════════════════════════════════════════════════════

class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str = Field(..., description="Message type")
    execution_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebSocketSubscribeRequest(BaseModel):
    """WebSocket subscription request."""
    action: Literal["subscribe", "unsubscribe"]
    topics: List[str] = Field(..., description="Topics to subscribe/unsubscribe")

"""
Node Boundary Domain Model.

Represents a marker pointing to checkpoints at node boundaries.
NOT a separate checkpoint - just references to entry/exit checkpoints.

Design Philosophy:
- Checkpoint = Atomic state snapshot (always at tool/message level)
- Node Boundary = Marker pointing to checkpoints (NOT a duplicate checkpoint)
- Rollback is unified: "node rollback" = rollback to exit_checkpoint_id
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


@dataclass
class NodeBoundary:
    """
    Entity - Marker for node execution boundaries.
    
    Points to the first and last checkpoints within a node's execution.
    Used for node-level rollback (which is just rollback to exit_checkpoint).
    
    Stored in WTB's own database (wtb_node_boundaries), NOT in AgentGit.
    """
    # Identity
    id: Optional[int] = None  # Auto-assigned by DB
    
    # WTB Execution Context
    execution_id: str = ""  # WTB execution UUID
    
    # AgentGit Reference
    internal_session_id: int = 0  # → agentgit.internal_sessions.id
    
    # Node Identification
    node_id: str = ""  # Workflow node name
    
    # Checkpoint Pointers (to AgentGit checkpoints)
    entry_checkpoint_id: Optional[int] = None  # First checkpoint when entering node
    exit_checkpoint_id: Optional[int] = None   # Last checkpoint when exiting (rollback target)
    
    # Node Execution Status
    node_status: str = "started"  # "started", "completed", "failed", "skipped"
    
    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Metrics
    tool_count: int = 0
    checkpoint_count: int = 0
    duration_ms: Optional[int] = None
    
    # Error Info
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def complete(self, exit_checkpoint_id: int, tool_count: int = 0, checkpoint_count: int = 0):
        """Mark node as completed."""
        self.node_status = "completed"
        self.exit_checkpoint_id = exit_checkpoint_id
        self.completed_at = datetime.now()
        self.tool_count = tool_count
        self.checkpoint_count = checkpoint_count
        self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
    
    def fail(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark node as failed."""
        self.node_status = "failed"
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.error_details = error_details
        self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
    
    def skip(self, reason: str = ""):
        """Mark node as skipped."""
        self.node_status = "skipped"
        self.completed_at = datetime.now()
        if reason:
            self.error_message = f"Skipped: {reason}"
    
    def is_completed(self) -> bool:
        """Check if node completed successfully."""
        return self.node_status == "completed"
    
    def is_rollback_target(self) -> bool:
        """Check if this boundary can be used as a rollback target."""
        return self.node_status == "completed" and self.exit_checkpoint_id is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "internal_session_id": self.internal_session_id,
            "node_id": self.node_id,
            "entry_checkpoint_id": self.entry_checkpoint_id,
            "exit_checkpoint_id": self.exit_checkpoint_id,
            "node_status": self.node_status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tool_count": self.tool_count,
            "checkpoint_count": self.checkpoint_count,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "error_details": self.error_details,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeBoundary":
        """Deserialize from dictionary."""
        boundary = cls(
            id=data.get("id"),
            execution_id=data.get("execution_id", ""),
            internal_session_id=data.get("internal_session_id", 0),
            node_id=data.get("node_id", ""),
            entry_checkpoint_id=data.get("entry_checkpoint_id"),
            exit_checkpoint_id=data.get("exit_checkpoint_id"),
            node_status=data.get("node_status", "started"),
            tool_count=data.get("tool_count", 0),
            checkpoint_count=data.get("checkpoint_count", 0),
            duration_ms=data.get("duration_ms"),
            error_message=data.get("error_message"),
            error_details=data.get("error_details"),
        )
        
        if data.get("started_at"):
            boundary.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            boundary.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return boundary


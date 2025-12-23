"""
Checkpoint-related domain events.

Published during checkpoint and rollback operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid


@dataclass
class CheckpointEvent:
    """Base class for checkpoint events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    execution_id: str = ""
    session_id: int = 0
    
    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass
class CheckpointCreatedEvent(CheckpointEvent):
    """Published when a checkpoint is created."""
    checkpoint_id: int = 0
    checkpoint_name: Optional[str] = None
    node_id: str = ""
    trigger_type: str = ""  # "tool_start", "tool_end", "auto", "user_request"
    tool_name: Optional[str] = None
    tool_track_position: int = 0
    is_auto: bool = True
    has_file_commit: bool = False
    file_commit_id: Optional[str] = None


@dataclass
class RollbackPerformedEvent(CheckpointEvent):
    """Published when a rollback is performed."""
    to_checkpoint_id: int = 0
    from_checkpoint_id: Optional[int] = None
    rollback_type: str = ""  # "node_level", "tool_level", "manual"
    tools_reversed: int = 0
    files_restored: bool = False
    file_commit_id: Optional[str] = None
    new_session_id: Optional[int] = None


@dataclass
class BranchCreatedEvent(CheckpointEvent):
    """Published when a new branch is created from a checkpoint."""
    from_checkpoint_id: int = 0
    new_session_id: int = 0
    parent_session_id: int = 0
    branch_reason: str = ""  # "rollback", "variant_test", "manual"


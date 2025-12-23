"""
In-Memory State Adapter Implementation.

A simple in-memory implementation of IStateAdapter for testing and development.
Does not persist data between runs.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from copy import deepcopy

from wtb.domain.interfaces.state_adapter import (
    IStateAdapter,
    CheckpointTrigger,
    CheckpointInfo,
    NodeBoundaryInfo,
)
from wtb.domain.models import ExecutionState


class InMemoryCheckpoint:
    """Internal checkpoint representation."""
    def __init__(
        self,
        id: int,
        session_id: int,
        state: ExecutionState,
        node_id: str,
        trigger: CheckpointTrigger,
        tool_name: Optional[str],
        name: Optional[str],
        metadata: Dict[str, Any],
        tool_track_position: int,
    ):
        self.id = id
        self.session_id = session_id
        self.state = deepcopy(state)
        self.node_id = node_id
        self.trigger = trigger
        self.tool_name = tool_name
        self.name = name
        self.metadata = metadata
        self.tool_track_position = tool_track_position
        self.created_at = datetime.now().isoformat()
        self.is_auto = trigger != CheckpointTrigger.USER_REQUEST
        self.file_commit_id: Optional[str] = None


class InMemoryNodeBoundary:
    """Internal node boundary representation."""
    def __init__(
        self,
        id: int,
        execution_id: str,
        session_id: int,
        node_id: str,
        entry_checkpoint_id: int,
    ):
        self.id = id
        self.execution_id = execution_id
        self.session_id = session_id
        self.node_id = node_id
        self.entry_checkpoint_id = entry_checkpoint_id
        self.exit_checkpoint_id: Optional[int] = None
        self.node_status = "started"
        self.started_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.tool_count = 0
        self.checkpoint_count = 0
        self.error_message: Optional[str] = None


class InMemoryStateAdapter(IStateAdapter):
    """
    In-memory implementation of IStateAdapter.
    
    Useful for:
    - Unit testing
    - Development without database setup
    - Prototyping
    
    Limitations:
    - No persistence between runs
    - No cross-process sharing
    - Memory grows with checkpoints
    """
    
    def __init__(self):
        # ID counters
        self._next_session_id = 1
        self._next_checkpoint_id = 1
        self._next_boundary_id = 1
        
        # Storage
        self._sessions: Dict[int, Dict[str, Any]] = {}
        self._checkpoints: Dict[int, InMemoryCheckpoint] = {}
        self._boundaries: Dict[int, InMemoryNodeBoundary] = {}
        
        # Current session tracking
        self._current_session_id: Optional[int] = None
        self._current_execution_id: Optional[str] = None
        self._tool_track_position = 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def initialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[int]:
        """Initialize a new session."""
        session_id = self._next_session_id
        self._next_session_id += 1
        
        self._sessions[session_id] = {
            "id": session_id,
            "execution_id": execution_id,
            "initial_state": deepcopy(initial_state),
            "created_at": datetime.now().isoformat(),
        }
        
        self._current_session_id = session_id
        self._current_execution_id = execution_id
        self._tool_track_position = 0
        
        return session_id
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoint Operations
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_checkpoint(
        self,
        state: ExecutionState,
        node_id: str,
        trigger: CheckpointTrigger,
        tool_name: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Save a state checkpoint."""
        if self._current_session_id is None:
            raise RuntimeError("No active session")
        
        self._tool_track_position += 1
        
        checkpoint_id = self._next_checkpoint_id
        self._next_checkpoint_id += 1
        
        checkpoint = InMemoryCheckpoint(
            id=checkpoint_id,
            session_id=self._current_session_id,
            state=state,
            node_id=node_id,
            trigger=trigger,
            tool_name=tool_name,
            name=name,
            metadata=metadata or {},
            tool_track_position=self._tool_track_position,
        )
        
        self._checkpoints[checkpoint_id] = checkpoint
        return checkpoint_id
    
    def load_checkpoint(self, checkpoint_id: int) -> ExecutionState:
        """Load a checkpoint's state."""
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        return deepcopy(self._checkpoints[checkpoint_id].state)
    
    def link_file_commit(
        self, 
        checkpoint_id: int, 
        file_commit_id: str,
        file_count: int = 0,
        total_size_bytes: int = 0
    ) -> bool:
        """Link a FileTracker commit to a checkpoint."""
        if checkpoint_id not in self._checkpoints:
            return False
        
        self._checkpoints[checkpoint_id].file_commit_id = file_commit_id
        return True
    
    def get_file_commit(self, checkpoint_id: int) -> Optional[str]:
        """Get linked file commit ID."""
        if checkpoint_id not in self._checkpoints:
            return None
        return self._checkpoints[checkpoint_id].file_commit_id
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Node Boundary Operations
    # ═══════════════════════════════════════════════════════════════════════════
    
    def mark_node_started(self, node_id: str, entry_checkpoint_id: int) -> int:
        """Mark node as started."""
        if self._current_session_id is None:
            raise RuntimeError("No active session")
        
        boundary_id = self._next_boundary_id
        self._next_boundary_id += 1
        
        boundary = InMemoryNodeBoundary(
            id=boundary_id,
            execution_id=self._current_execution_id or "",
            session_id=self._current_session_id,
            node_id=node_id,
            entry_checkpoint_id=entry_checkpoint_id,
        )
        
        self._boundaries[boundary_id] = boundary
        return boundary_id
    
    def mark_node_completed(
        self, 
        node_id: str, 
        exit_checkpoint_id: int,
        tool_count: int = 0,
        checkpoint_count: int = 0
    ) -> bool:
        """Mark node as completed."""
        boundary = self._find_boundary(node_id)
        if boundary:
            boundary.exit_checkpoint_id = exit_checkpoint_id
            boundary.node_status = "completed"
            boundary.completed_at = datetime.now().isoformat()
            boundary.tool_count = tool_count
            boundary.checkpoint_count = checkpoint_count
            return True
        return False
    
    def mark_node_failed(self, node_id: str, error_message: str) -> bool:
        """Mark node as failed."""
        boundary = self._find_boundary(node_id)
        if boundary:
            boundary.node_status = "failed"
            boundary.completed_at = datetime.now().isoformat()
            boundary.error_message = error_message
            return True
        return False
    
    def _find_boundary(self, node_id: str) -> Optional[InMemoryNodeBoundary]:
        """Find boundary by node ID in current session."""
        for boundary in self._boundaries.values():
            if (boundary.session_id == self._current_session_id and 
                boundary.node_id == node_id):
                return boundary
        return None
    
    def get_node_boundaries(self, session_id: int) -> List[NodeBoundaryInfo]:
        """Get all node boundaries for a session."""
        return [
            NodeBoundaryInfo(
                id=b.id,
                node_id=b.node_id,
                entry_checkpoint_id=b.entry_checkpoint_id,
                exit_checkpoint_id=b.exit_checkpoint_id or 0,
                node_status=b.node_status,
                tool_count=b.tool_count,
                checkpoint_count=b.checkpoint_count,
                started_at=b.started_at,
                completed_at=b.completed_at,
            )
            for b in self._boundaries.values()
            if b.session_id == session_id
        ]
    
    def get_node_boundary(self, session_id: int, node_id: str) -> Optional[NodeBoundaryInfo]:
        """Get a specific node boundary."""
        for b in self._boundaries.values():
            if b.session_id == session_id and b.node_id == node_id:
                return NodeBoundaryInfo(
                    id=b.id,
                    node_id=b.node_id,
                    entry_checkpoint_id=b.entry_checkpoint_id,
                    exit_checkpoint_id=b.exit_checkpoint_id or 0,
                    node_status=b.node_status,
                    tool_count=b.tool_count,
                    checkpoint_count=b.checkpoint_count,
                    started_at=b.started_at,
                    completed_at=b.completed_at,
                )
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Rollback & Branching
    # ═══════════════════════════════════════════════════════════════════════════
    
    def rollback(self, to_checkpoint_id: int) -> ExecutionState:
        """Rollback to a specific checkpoint."""
        if to_checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint {to_checkpoint_id} not found")
        
        checkpoint = self._checkpoints[to_checkpoint_id]
        
        # Reset tool track position to checkpoint's position
        self._tool_track_position = checkpoint.tool_track_position
        
        return deepcopy(checkpoint.state)
    
    def create_branch(self, from_checkpoint_id: int) -> int:
        """Create a new branch from a checkpoint."""
        if from_checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint {from_checkpoint_id} not found")
        
        checkpoint = self._checkpoints[from_checkpoint_id]
        
        # Create new session for the branch
        new_session_id = self._next_session_id
        self._next_session_id += 1
        
        self._sessions[new_session_id] = {
            "id": new_session_id,
            "execution_id": self._current_execution_id,
            "parent_session_id": checkpoint.session_id,
            "branch_point_checkpoint_id": from_checkpoint_id,
            "initial_state": deepcopy(checkpoint.state),
            "created_at": datetime.now().isoformat(),
        }
        
        self._current_session_id = new_session_id
        self._tool_track_position = checkpoint.tool_track_position
        
        return new_session_id
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Query Operations
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_checkpoints(
        self, 
        session_id: int,
        node_id: Optional[str] = None
    ) -> List[CheckpointInfo]:
        """Get checkpoints for a session."""
        result = []
        for cp in self._checkpoints.values():
            if cp.session_id != session_id:
                continue
            if node_id and cp.node_id != node_id:
                continue
            
            result.append(CheckpointInfo(
                id=cp.id,
                name=cp.name,
                node_id=cp.node_id,
                tool_track_position=cp.tool_track_position,
                trigger_type=cp.trigger,
                created_at=cp.created_at,
                is_auto=cp.is_auto,
                has_file_commit=cp.file_commit_id is not None,
            ))
        
        return sorted(result, key=lambda c: c.tool_track_position)
    
    def get_node_rollback_targets(self, session_id: int) -> List[CheckpointInfo]:
        """Get valid node-level rollback targets."""
        result = []
        for b in self._boundaries.values():
            if b.session_id == session_id and b.node_status == "completed" and b.exit_checkpoint_id:
                cp = self._checkpoints.get(b.exit_checkpoint_id)
                if cp:
                    result.append(CheckpointInfo(
                        id=cp.id,
                        name=cp.name or f"Node: {b.node_id}",
                        node_id=b.node_id,
                        tool_track_position=cp.tool_track_position,
                        trigger_type=cp.trigger,
                        created_at=cp.created_at,
                        is_auto=cp.is_auto,
                        has_file_commit=cp.file_commit_id is not None,
                    ))
        return result
    
    def get_checkpoints_in_node(self, session_id: int, node_id: str) -> List[CheckpointInfo]:
        """Get all checkpoints within a specific node."""
        return self.get_checkpoints(session_id, node_id)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_current_session_id(self) -> Optional[int]:
        """Get current session ID."""
        return self._current_session_id
    
    def set_current_session(self, session_id: int) -> bool:
        """Set current session."""
        if session_id in self._sessions:
            self._current_session_id = session_id
            return True
        return False
    
    def cleanup(self, session_id: int, keep_latest: int = 5) -> int:
        """Cleanup old checkpoints."""
        session_cps = [
            cp for cp in self._checkpoints.values()
            if cp.session_id == session_id and cp.is_auto
        ]
        
        # Sort by creation time (newest first)
        session_cps.sort(key=lambda c: c.created_at, reverse=True)
        
        # Remove old ones
        to_delete = session_cps[keep_latest:]
        for cp in to_delete:
            del self._checkpoints[cp.id]
        
        return len(to_delete)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Testing Utilities
    # ═══════════════════════════════════════════════════════════════════════════
    
    def reset(self):
        """Reset all state (for testing)."""
        self._next_session_id = 1
        self._next_checkpoint_id = 1
        self._next_boundary_id = 1
        self._sessions.clear()
        self._checkpoints.clear()
        self._boundaries.clear()
        self._current_session_id = None
        self._current_execution_id = None
        self._tool_track_position = 0
    
    def get_checkpoint_count(self) -> int:
        """Get total checkpoint count (for testing)."""
        return len(self._checkpoints)
    
    def get_session_count(self) -> int:
        """Get total session count (for testing)."""
        return len(self._sessions)


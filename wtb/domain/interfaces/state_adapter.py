"""
State Adapter Interface.

Anti-corruption layer between WTB and state persistence systems (AgentGit, etc.).
Follows Dependency Inversion Principle - high-level WTB depends on this abstraction.

Design Philosophy:
==================
"Design at smallest granularity, separate concerns, compose at higher levels."

- Checkpoint = Atomic state snapshot (ALWAYS at tool/message level)
- Node Boundary = Marker pointing to checkpoints (NOT a separate checkpoint)
- File Commit = Linked to Checkpoint (not to Node)

Rollback is unified: always to a checkpoint. "Node-level rollback" = rollback to
the node's exit_checkpoint_id.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from ..models.workflow import ExecutionState


class CheckpointTrigger(Enum):
    """What triggered the checkpoint creation."""
    TOOL_START = "tool_start"      # Before tool execution
    TOOL_END = "tool_end"          # After tool execution
    LLM_CALL = "llm_call"          # After LLM invocation
    USER_REQUEST = "user_request"  # Manual checkpoint
    AUTO = "auto"                  # System auto-checkpoint


@dataclass
class CheckpointInfo:
    """Lightweight checkpoint information for listings."""
    id: int
    name: Optional[str]
    node_id: Optional[str]
    tool_track_position: int
    trigger_type: CheckpointTrigger
    created_at: str
    is_auto: bool
    has_file_commit: bool = False  # True if linked to FileTracker commit


@dataclass
class NodeBoundaryInfo:
    """Node boundary information - pointers to checkpoints."""
    id: int
    node_id: str
    entry_checkpoint_id: int       # First checkpoint when entering node
    exit_checkpoint_id: int        # Last checkpoint when exiting node (rollback target)
    node_status: str               # "started", "completed", "failed"
    tool_count: int
    checkpoint_count: int
    started_at: str
    completed_at: Optional[str]


class IStateAdapter(ABC):
    """
    Anti-corruption layer between WTB and state persistence systems.
    
    Implementations:
    - InMemoryStateAdapter: For testing
    - AgentGitStateAdapter: Production integration with AgentGit
    
    Key Design Decisions:
    1. All checkpoints are at tool/message level (finest granularity)
    2. Node boundaries are separate markers pointing to checkpoints
    3. Rollback always goes to a checkpoint; node rollback = rollback to exit_checkpoint
    4. File commits are linked to checkpoints via a separate table
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def initialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[int]:
        """
        Initialize a new session for execution.
        
        Creates the underlying session in AgentGit (InternalSession_mdp).
        
        Args:
            execution_id: WTB execution ID for correlation
            initial_state: Initial workflow execution state
            
        Returns:
            Session ID, or None if creation failed
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoint Operations (Always at tool/message level)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def save_checkpoint(
        self,
        state: ExecutionState,
        node_id: str,
        trigger: CheckpointTrigger,
        tool_name: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save a state checkpoint (always at tool/message level).
        
        This is the ONLY way to create checkpoints. All checkpoints are equal;
        node boundaries are created separately via mark_node_boundary().
        
        Args:
            state: Current execution state to save
            node_id: Which workflow node this checkpoint belongs to
            trigger: What triggered this checkpoint (tool_end, llm_call, etc.)
            tool_name: If triggered by tool, which one
            name: Optional human-readable name
            metadata: Additional metadata (audit_trail, etc.)
            
        Returns:
            Checkpoint ID
            
        Raises:
            RuntimeError: If no active session
        """
        pass
    
    @abstractmethod
    def load_checkpoint(self, checkpoint_id: int) -> ExecutionState:
        """
        Load a checkpoint's state by ID.
        
        Args:
            checkpoint_id: ID of the checkpoint to load
            
        Returns:
            ExecutionState restored from the checkpoint
            
        Raises:
            ValueError: If checkpoint not found
        """
        pass
    
    @abstractmethod
    def link_file_commit(
        self, 
        checkpoint_id: int, 
        file_commit_id: str,
        file_count: int = 0,
        total_size_bytes: int = 0
    ) -> bool:
        """
        Link a FileTracker commit to a checkpoint.
        
        Creates an entry in checkpoint_file_commits table.
        
        Args:
            checkpoint_id: The checkpoint to link
            file_commit_id: FileTracker commit UUID
            file_count: Number of files in commit
            total_size_bytes: Total size of files
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_file_commit(self, checkpoint_id: int) -> Optional[str]:
        """
        Get the FileTracker commit ID linked to a checkpoint.
        
        Args:
            checkpoint_id: The checkpoint to query
            
        Returns:
            FileTracker commit UUID, or None if no files linked
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Node Boundary Operations (Markers, not checkpoints)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def mark_node_started(self, node_id: str, entry_checkpoint_id: int) -> int:
        """
        Mark that a node has started executing.
        
        Creates a node_boundary record with status="started".
        
        Args:
            node_id: The workflow node ID
            entry_checkpoint_id: First checkpoint created in this node
            
        Returns:
            Node boundary ID
        """
        pass
    
    @abstractmethod
    def mark_node_completed(
        self, 
        node_id: str, 
        exit_checkpoint_id: int,
        tool_count: int = 0,
        checkpoint_count: int = 0
    ) -> bool:
        """
        Mark that a node has completed.
        
        Updates node_boundary: status="completed", exit_checkpoint_id, etc.
        
        Args:
            node_id: The workflow node ID
            exit_checkpoint_id: Last checkpoint in this node (rollback target)
            tool_count: Number of tools executed in this node
            checkpoint_count: Number of checkpoints created in this node
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def mark_node_failed(self, node_id: str, error_message: str) -> bool:
        """
        Mark that a node has failed.
        
        Updates node_boundary: status="failed", error info.
        
        Args:
            node_id: The workflow node ID
            error_message: Error description
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_node_boundaries(self, session_id: int) -> List[NodeBoundaryInfo]:
        """
        Get all node boundaries for a session.
        
        Args:
            session_id: Session to query
            
        Returns:
            List of NodeBoundaryInfo objects
        """
        pass
    
    @abstractmethod
    def get_node_boundary(self, session_id: int, node_id: str) -> Optional[NodeBoundaryInfo]:
        """
        Get a specific node boundary.
        
        Args:
            session_id: Session to query
            node_id: Node to look up
            
        Returns:
            NodeBoundaryInfo or None if not found
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Rollback & Branching (Unified - always to checkpoint)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def rollback(self, to_checkpoint_id: int) -> ExecutionState:
        """
        Rollback to a specific checkpoint.
        
        This is the UNIFIED rollback operation:
        - "Node-level rollback": pass node_boundary.exit_checkpoint_id
        - "Tool-level rollback": pass any checkpoint.id
        
        The logic is identical:
        1. Load checkpoint state
        2. Reverse tools after this checkpoint (via AgentGit ToolRollbackRegistry)
        3. Restore files (via FileTracker, if checkpoint has linked file_commit)
        4. Return restored state
        
        Args:
            to_checkpoint_id: Checkpoint ID to rollback to
            
        Returns:
            Restored execution state
            
        Raises:
            ValueError: If checkpoint not found
        """
        pass
    
    @abstractmethod
    def create_branch(self, from_checkpoint_id: int) -> int:
        """
        Create a new branch from a checkpoint.
        
        Creates a new session branched from the specified checkpoint.
        
        Args:
            from_checkpoint_id: Checkpoint ID to branch from
            
        Returns:
            New session ID for the branch
            
        Raises:
            ValueError: If checkpoint not found
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Query Operations
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def get_checkpoints(
        self, 
        session_id: int,
        node_id: Optional[str] = None
    ) -> List[CheckpointInfo]:
        """
        Get checkpoints for a session.
        
        Args:
            session_id: Session to query
            node_id: Optional filter by node
            
        Returns:
            List of CheckpointInfo objects
        """
        pass
    
    @abstractmethod
    def get_node_rollback_targets(self, session_id: int) -> List[CheckpointInfo]:
        """
        Get valid node-level rollback targets.
        
        Returns the exit_checkpoint for each completed node.
        Convenience method equivalent to:
            [get_checkpoint(b.exit_checkpoint_id) for b in get_node_boundaries() 
             if b.status == "completed"]
        
        Args:
            session_id: Session to query
            
        Returns:
            List of CheckpointInfo (one per completed node)
        """
        pass
    
    @abstractmethod
    def get_checkpoints_in_node(self, session_id: int, node_id: str) -> List[CheckpointInfo]:
        """
        Get all checkpoints within a specific node (for debugging).
        
        Args:
            session_id: Session to query
            node_id: Node to filter by
            
        Returns:
            List of CheckpointInfo objects in execution order
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def get_current_session_id(self) -> Optional[int]:
        """Get the current active session ID."""
        pass
    
    @abstractmethod
    def set_current_session(self, session_id: int) -> bool:
        """Set the current active session."""
        pass
    
    @abstractmethod
    def cleanup(self, session_id: int, keep_latest: int = 5) -> int:
        """
        Cleanup old checkpoints, keeping only the most recent.
        
        Removes auto-generated checkpoints to manage storage.
        User-requested checkpoints are preserved.
        
        Args:
            session_id: Session to cleanup
            keep_latest: Number of recent auto-checkpoints to keep
            
        Returns:
            Number of checkpoints removed
        """
        pass


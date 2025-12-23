"""
Checkpoint-File Link Domain Model.

Bridges AgentGit checkpoints to FileTracker commits.
Enables coordinated rollback of both agent state AND file state.

Design Philosophy:
- File commits are linked to Checkpoints (not to Nodes!)
- Each checkpoint can optionally have one linked file commit
- Rollback restores both state AND files
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class CheckpointFile:
    """
    Entity - Links an AgentGit checkpoint to a FileTracker commit.
    
    Stored in WTB's own database (wtb_checkpoint_files).
    Enables unified rollback of state + files.
    
    Cross-database references:
    - checkpoint_id → agentgit.checkpoints.id
    - file_commit_id → filetracker.commits.commit_id (UUID)
    """
    # Identity
    id: Optional[int] = None  # Auto-assigned by DB
    
    # AgentGit Reference
    checkpoint_id: int = 0  # → agentgit.checkpoints.id
    
    # FileTracker Reference  
    file_commit_id: str = ""  # → filetracker.commits.commit_id (UUID)
    
    # Summary (denormalized for quick access without querying FileTracker)
    file_count: int = 0
    total_size_bytes: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "checkpoint_id": self.checkpoint_id,
            "file_commit_id": self.file_commit_id,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointFile":
        """Deserialize from dictionary."""
        cf = cls(
            id=data.get("id"),
            checkpoint_id=data.get("checkpoint_id", 0),
            file_commit_id=data.get("file_commit_id", ""),
            file_count=data.get("file_count", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
        )
        
        if data.get("created_at"):
            cf.created_at = datetime.fromisoformat(data["created_at"])
        
        return cf
    
    def format_size(self) -> str:
        """Format total size as human-readable string."""
        size = self.total_size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


"""
File Processing Value Objects.

Immutable value objects for file processing domain.
Follows DDD Value Object pattern with type safety and validation.

Design Principles:
- Immutable: All value objects are frozen dataclasses
- Type Safety: Strong typing prevents ID mix-ups
- Self-Validating: Validation in __post_init__
- Rich API: Useful properties and factory methods

Value Objects:
- BlobId: Content-addressable identifier (SHA-256)
- CommitId: Unique commit identifier (UUID)
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .exceptions import InvalidBlobIdError, InvalidCommitIdError


@dataclass(frozen=True)
class BlobId:
    """
    Content-addressable blob identifier (SHA-256 hash).
    
    Value object ensuring type safety for blob references.
    Immutable for thread-safety and hash consistency.
    
    Attributes:
        value: 64-character hexadecimal string (SHA-256 hash)
        
    Examples:
        >>> blob_id = BlobId.from_content(b"hello world")
        >>> print(blob_id.short)
        'b94d27b9'
        
        >>> blob_id = BlobId.from_file("data.csv")
    """
    value: str
    
    def __post_init__(self):
        """Validate blob ID format."""
        if not isinstance(self.value, str):
            raise InvalidBlobIdError(f"BlobId value must be string, got {type(self.value)}")
        if len(self.value) != 64:
            raise InvalidBlobIdError(
                f"BlobId must be 64 hex characters (SHA-256), got {len(self.value)}"
            )
        if not all(c in '0123456789abcdef' for c in self.value.lower()):
            raise InvalidBlobIdError(f"BlobId must be hexadecimal: {self.value}")
    
    @classmethod
    def from_content(cls, content: bytes) -> "BlobId":
        """
        Create BlobId from content bytes.
        
        Args:
            content: Binary content to hash
            
        Returns:
            BlobId with SHA-256 hash of content
        """
        hash_value = hashlib.sha256(content).hexdigest()
        return cls(value=hash_value)
    
    @classmethod
    def from_file(cls, file_path: str) -> "BlobId":
        """
        Create BlobId from file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            BlobId with SHA-256 hash of file content
        """
        content = Path(file_path).read_bytes()
        return cls.from_content(content)
    
    @property
    def storage_path(self) -> str:
        """
        Git-like storage path for content-addressable storage.
        
        Format: objects/{hash[:2]}/{hash[2:]}
        
        Returns:
            Relative storage path
        """
        return f"objects/{self.value[:2]}/{self.value[2:]}"
    
    @property
    def short(self) -> str:
        """Short representation (first 8 characters)."""
        return self.value[:8]
    
    def to_dict(self) -> Dict[str, str]:
        """Serialize to dictionary."""
        return {"value": self.value}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "BlobId":
        """Deserialize from dictionary."""
        return cls(value=data["value"])
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"BlobId({self.short}...)"


@dataclass(frozen=True)
class CommitId:
    """
    Unique commit identifier (UUID).
    
    Value object ensuring type safety for commit references.
    Uses UUID v4 for globally unique, collision-free IDs.
    
    Attributes:
        value: UUID string (36 characters with hyphens or 32 without)
        
    Examples:
        >>> commit_id = CommitId.generate()
        >>> print(commit_id.short)
        'a1b2c3d4'
        
        >>> commit_id = CommitId("550e8400-e29b-41d4-a716-446655440000")
    """
    value: str
    
    def __post_init__(self):
        """Validate commit ID format."""
        if not isinstance(self.value, str):
            raise InvalidCommitIdError(f"CommitId value must be string, got {type(self.value)}")
        # Validate UUID format (with or without hyphens)
        try:
            # Normalize to UUID then back to string
            uuid.UUID(self.value)
        except ValueError as e:
            raise InvalidCommitIdError(f"CommitId must be valid UUID: {self.value}") from e
    
    @classmethod
    def generate(cls) -> "CommitId":
        """Generate a new unique commit ID."""
        return cls(value=str(uuid.uuid4()))
    
    @property
    def short(self) -> str:
        """Short representation (first 8 characters)."""
        return self.value[:8]
    
    def to_dict(self) -> Dict[str, str]:
        """Serialize to dictionary."""
        return {"value": self.value}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "CommitId":
        """Deserialize from dictionary."""
        return cls(value=data["value"])
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"CommitId({self.short}...)"


__all__ = [
    "BlobId",
    "CommitId",
]

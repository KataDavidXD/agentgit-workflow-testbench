"""
File Processing Domain Models Package.

Domain models for file version control following DDD principles.
Implements the Memento Pattern for file state snapshots.

Package Structure (SRP Compliant):
- exceptions.py: All file processing exceptions
- value_objects.py: BlobId, CommitId (immutable identifiers)
- entities.py: FileMemento, FileCommit, CommitStatus
- checkpoint_link.py: CheckpointFileLink (association entity)

Design Principles:
- SOLID: Single responsibility per module
- Immutable value objects (frozen dataclasses)
- Rich domain model with business logic
- ACID: Transaction-safe through UoW pattern

Usage:
    from wtb.domain.models.file_processing import (
        FileCommit,
        FileMemento,
        BlobId,
        CommitId,
        CheckpointFileLink,
    )
    
    # Create a commit with mementos
    commit = FileCommit.create(message="Initial file snapshot")
    memento = FileMemento.from_path_and_hash("data.csv", blob_id, 1024)
    commit.add_memento(memento)
    
    # Link to checkpoint
    link = CheckpointFileLink.create(checkpoint_id=42, commit=commit)

Migration Note (2026-01-27):
    This package was refactored from a single file_processing.py (717 lines)
    to improve maintainability and follow SRP. All imports remain backward
    compatible through this __init__.py re-export.
"""

# Exceptions
from .exceptions import (
    FileProcessingError,
    DuplicateFileError,
    InvalidBlobIdError,
    InvalidCommitIdError,
    CommitAlreadyFinalized,
)

# Value Objects
from .value_objects import (
    BlobId,
    CommitId,
)

# Entities
from .entities import (
    CommitStatus,
    FileMemento,
    FileCommit,
)

# Association Entity
from .checkpoint_link import (
    CheckpointFileLink,
)


__all__ = [
    # Value Objects
    "BlobId",
    "CommitId",
    "FileMemento",
    # Entities
    "FileCommit",
    "CheckpointFileLink",
    "CommitStatus",
    # Errors
    "FileProcessingError",
    "DuplicateFileError",
    "InvalidBlobIdError",
    "InvalidCommitIdError",
    "CommitAlreadyFinalized",
]

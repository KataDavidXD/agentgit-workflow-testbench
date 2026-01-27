# File Processing Architecture

**Last Updated:** 2026-01-15  
**Status:** Refactoring from legacy `file_processing/` to DDD structure

## 1. Overview

This document describes the refactored File Processing module architecture, designed for integration with the WTB (Workflow Test Bench) system following SOLID principles and ensuring ACID compliance.

## 2. Design Goals

1. **SOLID Compliance** - Clean separation of concerns
2. **ACID Transactions** - Atomic file tracking operations
3. **Event Consistency** - Domain events for audit trail
4. **Testability** - In-memory implementations for unit tests
5. **DDD Alignment** - Domain models, interfaces, infrastructure layers

## 3. Architecture Layers

### 3.1 Domain Layer

```
wtb/domain/
├── models/
│   └── file_processing.py      # FileCommit, FileMemento, BlobId
├── interfaces/
│   └── file_processing_repository.py  # IFileCommitRepository, IBlobRepository
└── events/
    └── file_processing_events.py      # FileCommitCreatedEvent, etc.
```

### 3.2 Infrastructure Layer

```
wtb/infrastructure/
├── database/
│   ├── models/
│   │   └── file_processing_orm.py     # FileCommitORM, FileMementoORM, BlobORM
│   └── repositories/
│       └── file_processing_repository.py  # SQLAlchemyFileCommitRepository
└── file_tracking/
    ├── filetracker_service.py         # IFileTrackingService implementation
    └── mock_service.py                # MockFileTrackingService for testing
```

## 4. Domain Models

### 4.1 FileCommit (Aggregate Root)

```python
@dataclass
class FileCommit:
    """
    Aggregate root for file version commits.
    
    Invariants:
    - commit_id is immutable after creation
    - mementos list is append-only within transaction
    - timestamp is set at creation time
    """
    commit_id: CommitId           # Value object (UUID string)
    message: Optional[str]
    timestamp: datetime
    mementos: List[FileMemento]   # Child entities
    
    def add_memento(self, memento: FileMemento) -> None:
        """Add file snapshot to commit (domain method)."""
        if memento.file_path in [m.file_path for m in self.mementos]:
            raise DuplicateFileError(f"File already tracked: {memento.file_path}")
        self._mementos.append(memento)
    
    def get_files(self) -> List[str]:
        """Get list of tracked file paths."""
        return [m.file_path for m in self.mementos]
```

### 4.2 FileMemento (Value Object)

```python
@dataclass(frozen=True)
class FileMemento:
    """
    Immutable snapshot of a file's state (Memento Pattern).
    
    Does NOT store file content - only metadata.
    Content is stored separately in BlobRepository.
    """
    file_path: str
    file_hash: BlobId             # SHA-256 content hash
    file_size: int                # Size in bytes
    
    @classmethod
    def from_file(cls, file_path: str, blob_repo: IBlobRepository) -> "FileMemento":
        """Create memento from file, storing blob content."""
        content = Path(file_path).read_bytes()
        blob_id = blob_repo.save(content)
        return cls(
            file_path=file_path,
            file_hash=blob_id,
            file_size=len(content),
        )
```

### 4.3 BlobId (Value Object)

```python
@dataclass(frozen=True)
class BlobId:
    """
    Content-addressable blob identifier (SHA-256 hash).
    
    Value object ensuring type safety for blob references.
    """
    value: str  # 64-character hex string
    
    def __post_init__(self):
        if len(self.value) != 64:
            raise ValueError(f"BlobId must be 64 hex characters, got {len(self.value)}")
    
    @property
    def storage_path(self) -> str:
        """Git-like storage path: objects/{hash[:2]}/{hash[2:]}"""
        return f"objects/{self.value[:2]}/{self.value[2:]}"
```

## 5. Repository Interfaces

### 5.1 IFileCommitRepository

```python
class IFileCommitRepository(ABC):
    """Repository interface for FileCommit aggregate."""
    
    @abstractmethod
    def save(self, commit: FileCommit) -> None:
        """Save commit with all mementos (transactional)."""
        pass
    
    @abstractmethod
    def get_by_id(self, commit_id: CommitId) -> Optional[FileCommit]:
        """Get commit by ID with mementos loaded."""
        pass
    
    @abstractmethod
    def get_all(self, limit: int = 100) -> List[FileCommit]:
        """Get all commits (without mementos for performance)."""
        pass
    
    @abstractmethod
    def delete(self, commit_id: CommitId) -> None:
        """Delete commit and cascade to mementos."""
        pass
```

### 5.2 IBlobRepository

```python
class IBlobRepository(ABC):
    """Repository interface for blob content storage."""
    
    @abstractmethod
    def save(self, content: bytes) -> BlobId:
        """Save content, return content-addressed ID."""
        pass
    
    @abstractmethod
    def get(self, blob_id: BlobId) -> Optional[bytes]:
        """Retrieve content by blob ID."""
        pass
    
    @abstractmethod
    def exists(self, blob_id: BlobId) -> bool:
        """Check if blob exists."""
        pass
    
    @abstractmethod
    def restore_to_file(self, blob_id: BlobId, output_path: str) -> None:
        """Restore blob content to file system."""
        pass
```

## 6. Domain Events

```python
@dataclass
class FileCommitCreatedEvent(WTBEvent):
    """Emitted when a file commit is created."""
    commit_id: str
    file_count: int
    total_size_bytes: int
    message: Optional[str]

@dataclass
class FileRestoredEvent(WTBEvent):
    """Emitted when files are restored from a commit."""
    commit_id: str
    restored_paths: List[str]
    total_size_bytes: int

@dataclass
class CheckpointFileLinkCreatedEvent(WTBEvent):
    """Emitted when checkpoint-file link is created."""
    checkpoint_id: int
    commit_id: str
    file_count: int
```

## 7. Transaction Flow

### 7.1 Create File Commit with UoW

```python
def track_files(
    self,
    file_paths: List[str],
    message: Optional[str],
    uow: IUnitOfWork,
    event_bus: WTBEventBus,
) -> FileCommit:
    """
    Track files with full ACID compliance.
    
    Transaction boundary is managed by UoW.
    """
    with uow:
        # 1. Create commit entity
        commit = FileCommit.create(message=message)
        
        # 2. Create mementos and save blobs
        for path in file_paths:
            memento = FileMemento.from_file(path, uow.blobs)
            commit.add_memento(memento)
        
        # 3. Save commit (cascades to mementos)
        uow.file_commits.save(commit)
        
        # 4. Add outbox event for verification
        uow.outbox.add(OutboxEvent(
            event_type=OutboxEventType.FILE_COMMIT_VERIFY,
            payload={"file_commit_id": commit.commit_id.value},
        ))
        
        # 5. Commit transaction (all or nothing)
        uow.commit()
        
        # 6. Publish domain event (after commit succeeds)
        event_bus.publish(FileCommitCreatedEvent(
            commit_id=commit.commit_id.value,
            file_count=len(commit.mementos),
            total_size_bytes=commit.total_size,
            message=message,
        ))
        
        return commit
```

### 7.2 Restore Files with Audit

```python
def restore_commit(
    self,
    commit_id: CommitId,
    uow: IUnitOfWork,
    event_bus: WTBEventBus,
    audit_trail: WTBAuditTrail,
) -> FileRestoreResult:
    """
    Restore files from commit with audit trail.
    """
    with uow:
        commit = uow.file_commits.get_by_id(commit_id)
        if commit is None:
            raise CommitNotFoundError(commit_id)
        
        restored_paths = []
        total_size = 0
        
        for memento in commit.mementos:
            # Restore blob to file system
            uow.blobs.restore_to_file(memento.file_hash, memento.file_path)
            restored_paths.append(memento.file_path)
            total_size += memento.file_size
        
        # Add audit entry
        audit_trail.add_entry(
            event_type="file_restore",
            data={
                "commit_id": commit_id.value,
                "files": restored_paths,
                "size_bytes": total_size,
            },
        )
        
        uow.commit()
        
        # Publish event
        event_bus.publish(FileRestoredEvent(
            commit_id=commit_id.value,
            restored_paths=restored_paths,
            total_size_bytes=total_size,
        ))
        
        return FileRestoreResult(
            commit_id=commit_id.value,
            files_restored=len(restored_paths),
            total_size_bytes=total_size,
            restored_paths=restored_paths,
            success=True,
        )
```

## 8. SOLID Compliance Matrix

| Principle | Implementation | Evidence |
|-----------|----------------|----------|
| **SRP** | FileCommit manages commits only | No blob storage logic in commit |
| | FileMemento captures metadata only | No file I/O in memento |
| | BlobRepository handles storage | Isolated content management |
| **OCP** | New backends via interface | `IFileCommitRepository` allows SQLAlchemy, InMemory |
| | New storage via `IBlobRepository` | FileSystem, S3, etc. |
| **LSP** | Repositories interchangeable | `InMemoryFileCommitRepository` substitutes `SQLAlchemyFileCommitRepository` |
| **ISP** | Separate interfaces | `IBlobRepository` doesn't know about commits |
| | Focused methods | No bloated interfaces |
| **DIP** | Domain → Interface | `FileTrackingService` depends on `IBlobRepository`, not concrete |

## 9. ACID Compliance Matrix

| Property | Mechanism | Implementation |
|----------|-----------|----------------|
| **Atomicity** | UnitOfWork pattern | `with uow: ... uow.commit()` |
| | SQLAlchemy session | Transaction boundary |
| **Consistency** | Domain invariants | `FileCommit.add_memento()` validates |
| | Value object immutability | `@dataclass(frozen=True)` |
| **Isolation** | Database transactions | PostgreSQL/SQLite isolation |
| | WAL mode for SQLite | Concurrent reads |
| **Durability** | Database persistence | PostgreSQL with fsync |
| | Blob file storage | Content in filesystem |

## 10. Outbox Pattern Integration

Cross-database consistency with AgentGit checkpoints:

```python
# In FileTrackingService.track_and_link()
def track_and_link(
    self,
    checkpoint_id: int,
    file_paths: List[str],
    message: Optional[str],
) -> FileTrackingResult:
    """Atomic track-and-link with outbox verification."""
    
    with self._uow:
        # Track files
        commit = self._track_files_internal(file_paths, message)
        
        # Link to checkpoint
        link = CheckpointFileLink(
            checkpoint_id=checkpoint_id,
            commit_id=commit.commit_id,
            linked_at=datetime.now(),
            file_count=len(commit.mementos),
            total_size_bytes=commit.total_size,
        )
        self._uow.checkpoint_files.add(link)
        
        # Add outbox event for cross-DB verification
        self._uow.outbox.add(OutboxEvent(
            event_type=OutboxEventType.CHECKPOINT_FILE_LINK_VERIFY,
            payload={
                "checkpoint_id": checkpoint_id,
                "file_commit_id": commit.commit_id.value,
                "verify_blobs": True,
            },
        ))
        
        self._uow.commit()
        
        return FileTrackingResult(...)
```

## 11. Critical Decisions

### §1 Blob Storage Strategy

**Decision:** Git-like content-addressable storage with database metadata.

**Rationale:**
- Deduplication: Same content = same hash = stored once
- Integrity: Content hash validates data
- Scalability: Large files on filesystem, metadata in DB

### §2 Transaction Boundary

**Decision:** UnitOfWork encompasses commit + mementos + outbox events.

**Rationale:**
- Ensures atomic file tracking
- Outbox event guarantees eventual verification
- Rollback includes all related data

### §3 Event Publishing

**Decision:** Domain events published AFTER transaction commits.

**Rationale:**
- Events reflect actual state
- No phantom events from rolled-back transactions
- Subscribers see consistent data

### §4 Memento Immutability

**Decision:** FileMemento is a frozen dataclass.

**Rationale:**
- Thread-safety for concurrent access
- Prevents accidental mutation
- Value object semantics

---

## Related Documentation

- [WTB Architecture](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md)
- [Outbox Pattern](../Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md)
- [Event Bus Design](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md)

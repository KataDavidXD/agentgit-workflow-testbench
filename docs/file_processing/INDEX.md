# File Processing Module

**Last Updated:** 2026-01-28  
**Parent:** [Project_Init/INDEX.md](../Project_Init/INDEX.md)

---

## 1. Structure

### 1.1 Domain Layer (`wtb/domain/`)

```
wtb/domain/
├── models/
│   └── file_processing.py       # FileCommit, FileMemento, BlobId
├── interfaces/
│   └── file_processing_repository.py  # IBlobRepository, IFileCommitRepository
└── events/
    └── file_processing_events.py      # 11 event types
```

### 1.2 Infrastructure Layer (`wtb/infrastructure/`)

```
wtb/infrastructure/
├── file_tracking/
│   ├── filetracker_service.py   # IFileTrackingService implementation
│   └── ...
└── database/
    ├── file_processing_orm.py   # SQLAlchemy ORM models
    └── repositories/
        └── file_processing_repository.py  # Repository implementation
```

### 1.3 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FILE PROCESSING ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ExecutionController                                                        │
│          │                                                                   │
│          ▼                                                                   │
│   IFileTrackingService                                                       │
│   ├── track_files(paths) → FileTrackingResult                               │
│   ├── track_and_link(checkpoint_id, paths) → FileTrackingLink               │
│   └── restore_from_checkpoint(checkpoint_id) → FileRestoreResult            │
│          │                                                                   │
│          ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    FILE PROCESSING DOMAIN                            │   │
│   │                                                                      │   │
│   │   FileCommit (Entity)        FileMemento (Value Object)             │   │
│   │   ├── commit_id (UUID)       ├── file_path                          │   │
│   │   ├── timestamp              ├── file_hash (SHA-256)                │   │
│   │   ├── message                └── file_size                          │   │
│   │   └── mementos[]                                                    │   │
│   │                                                                      │   │
│   │   BlobId (Value Object)      CheckpointFileLink                     │   │
│   │   └── hash (SHA-256)         ├── checkpoint_id                      │   │
│   │                              └── commit_id                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│          │                                                                   │
│          ▼                                                                   │
│   Content-Addressable Storage                                                │
│   objects/{hash[:2]}/{hash[2:]}  (Git-like sharding)                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Concepts

| Concept | Description |
|---------|-------------|
| **FileCommit** | Point-in-time snapshot of files (like Git commit) |
| **FileMemento** | Captures file state without exposing content (Memento Pattern) |
| **BlobId** | SHA-256 hash as content identifier |
| **CheckpointFileLink** | Links WTB checkpoints to file commits |

---

## 2. Issues

### 2.1 Active Issues

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| FP-001 | Add `blobs` and `file_commits` repositories to UoW | 🔴 High | Pending |
| FP-002 | Add orphan blob cleanup utility | 🟡 Medium | Planned |

**FP-001 Details:** See [FILE_TRACKING_ARCHITECTURE_DECISION.md](FILE_TRACKING_ARCHITECTURE_DECISION.md) Section 3.2

### 2.2 Implementation Status

| Component | Status | Tests |
|-----------|--------|-------|
| FileCommit domain model | ✅ Complete | ✅ |
| FileMemento value object | ✅ Complete | ✅ |
| BlobId value object | ✅ Complete | ✅ |
| IBlobRepository | ✅ Complete | ✅ |
| IFileCommitRepository | ✅ Complete | ✅ |
| IFileTrackingService | ✅ Complete | ✅ |
| Checkpoint-File linking | ✅ Complete | ✅ |

---

## 3. Gap Analysis (Brief)

| Design Intent | Implementation | Gap |
|--------------|----------------|-----|
| Content-addressable storage | ✅ SHA-256 hashing | None |
| Memento Pattern | ✅ FileMemento | None |
| Checkpoint-file linking | ✅ CheckpointFileLink | None |
| Restore on rollback | ✅ Implemented | None |
| Outbox verification | ✅ FILE_COMMIT_VERIFY events | None |

**Overall:** Full implementation, no gaps identified.

---

## 4. SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | FileCommit handles commits, FileMemento handles snapshots, BlobRepository handles storage |
| **OCP** | New storage backends via interface implementation |
| **LSP** | InMemory, SQLAlchemy repositories interchangeable |
| **ISP** | Separate interfaces for commits, mementos, blobs |
| **DIP** | Domain depends on abstractions (IRepository interfaces) |

---

## 5. Related Documents

| Document | Description |
|----------|-------------|
| [FILE_TRACKING_ARCHITECTURE_DECISION.md](FILE_TRACKING_ARCHITECTURE_DECISION.md) | **Architecture Decision Record (2026-01-27)** |
| [WTB_VS_STANDALONE_COMPARISON.md](WTB_VS_STANDALONE_COMPARISON.md) | **WTB vs Standalone 对比分析 (2026-01-28)** |
| [../Project_Init/INDEX.md](../Project_Init/INDEX.md) | Main documentation |
| [../Project_Init/ARCHITECTURE_STRUCTURE.md](../Project_Init/ARCHITECTURE_STRUCTURE.md) | Full architecture |
| [../LangGraph/INDEX.md](../LangGraph/INDEX.md) | Checkpoint integration |

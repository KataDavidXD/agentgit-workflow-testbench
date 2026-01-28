# File Tracking Architecture Decision Record

**Date:** 2026-01-27  
**Status:** Adopted  
**Decision Makers:** Architecture Team  
**Parent:** [INDEX.md](INDEX.md)

---

## Executive Summary

This document addresses the dual existence of file tracking implementations in the codebase and provides clear guidance on when to use each approach.

---

## 1. Context

### 1.1 Current State Analysis

The codebase contains **two file tracking implementations**:

| Location | Technology | Purpose |
|----------|------------|---------|
| `file_processing/file_processing/FileTracker/` | Raw SQL cursors | Standalone/reference implementation |
| `wtb/infrastructure/database/repositories/file_processing_repository.py` | SQLAlchemy ORM | WTB-integrated with ACID compliance |

### 1.2 Database Landscape

```
┌──────────────────────────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│              wtb.db                   │  │wtb_checkpoints.db│  │  filetrack.db   │
│         (SQLAlchemy ORM)              │  │   (LangGraph)    │  │(native sqlite3) │
│                                       │  │                  │  │                 │
│ ├─ wtb_workflows                     │  │ (managed by      │  │ (managed by     │
│ ├─ wtb_executions                    │  │  LangGraph       │  │  SqliteFile-    │
│ ├─ wtb_outbox                        │  │  SqliteSaver)    │  │  TrackingService│
│ ├─ wtb_audit_logs                    │  │                  │  │                 │
│ ├─ file_blobs          ◄─────────────│──│──────────────────│──│─ DUPLICATED!    │
│ ├─ file_commits        ◄─────────────│──│──────────────────│──│─ DUPLICATED!    │
│ ├─ file_mementos       ◄─────────────│──│──────────────────│──│─ DUPLICATED!    │
│ └─ checkpoint_file_links             │  │                  │  │                 │
└──────────────────────────────────────┘  └──────────────────┘  └─────────────────┘
```

### 1.3 Colleague Review Findings

| Issue ID | Finding | Severity |
|----------|---------|----------|
| **Issue 1** | Legacy `file_processing` module still exists with raw SQL | ⚠️ Low |
| **Issue 2** | Missing `file_commits` repository in UoW | 🔶 Medium |
| **Issue 3** | Blob storage strategy needs documented guarantees | ⚠️ Low |

---

## 2. Decision

### 2.1 Adopt Option B: WTB-Integrated File Tracking

**The SQLAlchemy implementation in `wtb/infrastructure/` is the canonical implementation for WTB.**

Rationale:
1. **Single Database**: All WTB state in `wtb.db` enables cross-table transactions
2. **ACID Compliance**: SQLAlchemy session transactions guarantee consistency
3. **UnitOfWork Pattern**: Proper transaction boundaries across repositories
4. **No Breaking Changes**: `file_processing` module remains untouched

### 2.2 Module Classification

| Module | Classification | Recommendation |
|--------|----------------|----------------|
| `file_processing/file_processing/FileTracker/` | **Reference Implementation** | Keep as educational/standalone example |
| `wtb/infrastructure/database/repositories/file_processing_repository.py` | **Production Implementation** | Use for all WTB integrations |
| `wtb/infrastructure/file_tracking/sqlite_service.py` | **Lightweight Alternative** | Use when SQLAlchemy UoW not needed |

---

## 3. Implementation Status

### 3.1 Already Implemented ✅

| Component | Location | Status |
|-----------|----------|--------|
| `IBlobRepository` | `wtb/domain/interfaces/file_processing_repository.py` | ✅ Complete |
| `IFileCommitRepository` | `wtb/domain/interfaces/file_processing_repository.py` | ✅ Complete |
| `ICheckpointFileLinkRepository` | `wtb/domain/interfaces/file_processing_repository.py` | ✅ Complete |
| `SQLAlchemyBlobRepository` | `wtb/infrastructure/database/repositories/file_processing_repository.py` | ✅ Complete |
| `SQLAlchemyFileCommitRepository` | `wtb/infrastructure/database/repositories/file_processing_repository.py` | ✅ Complete |
| `SQLAlchemyCheckpointFileLinkRepository` | `wtb/infrastructure/database/repositories/file_processing_repository.py` | ✅ Complete |
| ORM Models | `wtb/infrastructure/database/file_processing_orm.py` | ✅ Complete |

### 3.2 Gap: UoW Integration ✅

**Status:** Implemented on 2026-01-28.

**Current UoW (Complete):**

```python
# wtb/infrastructure/database/unit_of_work.py
class SQLAlchemyUnitOfWork(IUnitOfWork):
    # WTB Core
    workflows: IWorkflowRepository
    executions: IExecutionRepository
    variants: INodeVariantRepository
    batch_tests: IBatchTestRepository
    evaluation_results: IEvaluationResultRepository
    audit_logs: IAuditLogRepository
    
    # WTB ACL (Anti-Corruption Layer)
    node_boundaries: INodeBoundaryRepository
    
    # File Processing (COMPLETE)
    blobs: IBlobRepository                          # ✅ Added
    file_commits: IFileCommitRepository             # ✅ Added
    checkpoint_file_links: ICheckpointFileLinkRepository
    
    # Infrastructure
    outbox: IOutboxRepository
```

---

## 4. Blob Storage Strategy

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BLOB STORAGE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Application Layer                                              │
│   ┌───────────────────────────────────────────────────────┐     │
│   │  with UnitOfWork() as uow:                            │     │
│   │      blob_id = uow.blobs.save(content)  # Step 1      │     │
│   │      commit.add_memento(path, blob_id)  # Step 2      │     │
│   │      uow.file_commits.save(commit)      # Step 3      │     │
│   │      uow.commit()                       # Step 4      │     │
│   └───────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│   Repository Layer                                               │
│   ┌───────────────────────────────────────────────────────┐     │
│   │  SQLAlchemyBlobRepository                             │     │
│   │  ├── save(content) → BlobId                           │     │
│   │  │   1. Compute SHA-256 hash                          │     │
│   │  │   2. Write to filesystem (atomic: temp → rename)   │     │
│   │  │   3. Insert FileBlobORM (in session)               │     │
│   │  └── get(blob_id) → bytes                             │     │
│   └───────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│   Storage Layer                                                  │
│   ┌───────────────────────────────────────────────────────┐     │
│   │  Content-Addressable Storage (Git-like)               │     │
│   │                                                       │     │
│   │  data/blobs/objects/                                  │     │
│   │  ├── ab/                                              │     │
│   │  │   └── cdef1234567890...  (SHA-256 hash)           │     │
│   │  ├── cd/                                              │     │
│   │  │   └── ef5678901234...                              │     │
│   │  └── ...                                              │     │
│   └───────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Transaction Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **Atomicity** | Filesystem write happens BEFORE `session.add()` |
| **Consistency** | SHA-256 hash validates content integrity |
| **Isolation** | Per-thread sessions, unique blob paths |
| **Durability** | Filesystem write + DB commit both required |

### 4.3 Rollback Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROLLBACK SCENARIOS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Scenario 1: DB Commit Fails After Blob Write                   │
│  ────────────────────────────────────────────                   │
│  1. blob.save(content) → writes file, adds to session           │
│  2. uow.commit() → FAILS                                        │
│  3. Result: Orphaned blob file on filesystem                    │
│  4. Solution: Background cleanup job (orphan detection)         │
│                                                                  │
│  Scenario 2: Application Crash During Transaction               │
│  ────────────────────────────────────────────────               │
│  1. blob.save(content) → writes file, adds to session           │
│  2. CRASH                                                       │
│  3. Result: Orphaned blob file, no DB record                    │
│  4. Solution: Startup orphan scan + cleanup                     │
│                                                                  │
│  Scenario 3: Restore on Checkpoint Rollback                     │
│  ────────────────────────────────────────────                   │
│  1. rollback_to_checkpoint(checkpoint_id)                       │
│  2. Query: checkpoint_file_links → commit_id                    │
│  3. Query: file_mementos → [(path, blob_hash), ...]            │
│  4. Restore: copy blob content → original paths                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Orphan Blob Cleanup (Recommended)

```python
# Pseudo-code for background orphan cleanup
class BlobOrphanCleaner:
    """
    Detect and clean orphaned blob files.
    
    Run periodically (e.g., daily) or on startup.
    """
    
    def clean_orphans(self, dry_run: bool = True) -> List[str]:
        """
        Find blobs on filesystem without DB records.
        
        Strategy:
        1. List all blob files in objects/
        2. Query DB for all known blob hashes
        3. Delete files not in DB (orphans)
        """
        orphans = []
        for blob_file in self._list_blob_files():
            blob_hash = self._extract_hash(blob_file)
            if not self._exists_in_db(blob_hash):
                orphans.append(blob_file)
                if not dry_run:
                    blob_file.unlink()
        return orphans
```

---

## 5. Usage Guidelines

### 5.1 When to Use Each Implementation

| Scenario | Recommended Implementation | Reason |
|----------|---------------------------|--------|
| WTB workflow execution | `SQLAlchemyFileCommitRepository` | ACID with UoW |
| Checkpoint rollback | `SQLAlchemyCheckpointFileLinkRepository` | Cross-table transaction |
| Standalone file tracking | `SqliteFileTrackingService` | Lightweight, no UoW needed |
| Learning/reference | `file_processing/FileTracker/` | Educational example |
| Unit testing | `InMemoryBlobRepository` | Fast, no I/O |

### 5.2 Code Examples

**Production (WTB-Integrated):**

```python
from wtb.infrastructure.database.unit_of_work import SQLAlchemyUnitOfWork

with SQLAlchemyUnitOfWork(db_url) as uow:
    # Track files with ACID guarantees
    blob_id = uow.blobs.save(file_content)
    
    commit = FileCommit.create(
        mementos=[FileMemento(path, blob_id, size)],
        message="Checkpoint at node_1"
    )
    uow.file_commits.save(commit)
    
    # Link to checkpoint atomically
    link = CheckpointFileLink(checkpoint_id, commit.id)
    uow.checkpoint_file_links.save(link)
    
    uow.commit()  # All-or-nothing
```

**Lightweight (Standalone):**

```python
from wtb.infrastructure.file_tracking import SqliteFileTrackingService

service = SqliteFileTrackingService(workspace_path=Path("./workspace"))

# Track and link in one call
result = service.track_and_link(
    checkpoint_id=42,
    file_paths=["model.pkl", "config.json"],
    message="Checkpoint files"
)
```

---

## 6. Future Recommendations

### 6.1 Short-Term (Next Sprint)

| Task | Priority | Effort |
|------|----------|--------|
| Add `blobs` and `file_commits` to UoW | 🔴 High | 1 day |
| Update `IUnitOfWork` interface | 🔴 High | 0.5 day |
| Add orphan cleanup utility | 🟡 Medium | 1 day |

### 6.2 Medium-Term (Next Quarter)

| Task | Priority | Effort |
|------|----------|--------|
| Deprecate `file_processing/FileTracker/` | 🟡 Medium | - |
| Consolidate `filetrack.db` into `wtb.db` | 🟡 Medium | 2 days |
| Add blob garbage collection job | 🟢 Low | 1 day |

### 6.3 Long-Term (Future)

| Task | Priority | Effort |
|------|----------|--------|
| Consider S3/MinIO blob backend | 🟢 Low | 1 week |
| Distributed blob storage | 🟢 Low | 2 weeks |

### 6.4 Async Architecture (v2.0) - ✅ IMPLEMENTED (2026-01-28)

| Task | Priority | Status | Reference |
|------|----------|--------|-----------|
| Create `IAsyncBlobRepository` interface | 🔴 High | ✅ Complete | `wtb/domain/interfaces/async_repositories.py` |
| Create `IAsyncFileCommitRepository` interface | 🔴 High | ✅ Complete | `wtb/domain/interfaces/async_repositories.py` |
| Create `IAsyncCheckpointFileLinkRepository` interface | 🔴 High | ✅ Complete | `wtb/domain/interfaces/async_repositories.py` |
| Add file repos to `IAsyncUnitOfWork` | 🔴 High | ✅ Complete | `wtb/domain/interfaces/async_unit_of_work.py` |
| Implement `AsyncSQLAlchemyBlobRepository` | 🔴 High | ✅ Complete | `wtb/infrastructure/database/async_repositories/async_file_processing_repository.py` |
| Implement `AsyncFileTrackerService` | 🟡 Medium | ✅ Complete | `wtb/infrastructure/file_tracking/async_filetracker_service.py` |
| Implement `AsyncBlobOrphanCleaner` | 🟡 Medium | ✅ Complete | `wtb/infrastructure/file_tracking/async_orphan_cleaner.py` |
| Create `AsyncLangGraphStateAdapter` | 🔴 High | ✅ Complete | `wtb/infrastructure/adapters/async_langgraph_state_adapter.py` |
| Create `AsyncExecutionController` | 🔴 High | ✅ Complete | `wtb/application/services/async_execution_controller.py` |
| Transaction Consistency Tests | 🟡 Medium | ✅ Complete | `tests/test_file_processing/integration/test_async_transaction_consistency.py` |

---

## 7. Async Architecture Alignment

### 7.1 Overview

The async architecture (WTB v2.0) requires async versions of all file tracking interfaces to enable non-blocking I/O throughout the system.

**Reference Document:** [ASYNC_ARCHITECTURE_PLAN.md](../Project_Init/ASYNC_ARCHITECTURE_PLAN.md)

### 7.2 Async Interface Mapping

| Sync Interface | Async Interface | Notes |
|----------------|-----------------|-------|
| `IBlobRepository` | `IAsyncBlobRepository` | Uses `aiofiles` for file I/O |
| `IFileCommitRepository` | `IAsyncFileCommitRepository` | Same API with `async`/`await` |
| `ICheckpointFileLinkRepository` | `IAsyncCheckpointFileLinkRepository` | Same API with `async`/`await` |
| `IFileProcessingUnitOfWork` | Merged into `IAsyncUnitOfWork` | Single UoW for all repos |

### 7.3 Async Two-Phase Write Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASYNC TWO-PHASE WRITE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Phase 1: Async File Write                                     │
│   ────────────────────────────                                  │
│   blob_id = await uow.blobs.asave(content)                      │
│   │                                                              │
│   │  Internally:                                                │
│   │  1. await aiofiles.open(blob_path, 'wb') as f:             │
│   │  2. await f.write(content)                                 │
│   │  3. session.add(FileBlobORM(...))  # Not yet committed     │
│   ▼                                                              │
│                                                                  │
│   Phase 2: Async Commit                                         │
│   ────────────────────────────                                  │
│   await uow.acommit()                                           │
│   │                                                              │
│   │  If commit FAILS:                                           │
│   │  → Orphaned blob on filesystem                             │
│   │  → AsyncBlobOrphanCleaner handles cleanup                  │
│   ▼                                                              │
│                                                                  │
│   Result: Either BOTH (file + DB record) or NEITHER            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 Async Orphan Cleanup Strategy

**Problem:** Async two-phase writes can leave orphaned blobs if:
- Filesystem write succeeds
- DB commit fails (transaction rollback)

**Solution:** `AsyncBlobOrphanCleaner` (see ASYNC_ARCHITECTURE_PLAN.md §8.3.5)

```python
# Run on startup or scheduled job
cleaner = AsyncBlobOrphanCleaner(
    blobs_dir=Path("./data/blobs/objects"),
    uow_factory=lambda: AsyncSQLAlchemyUnitOfWork(db_url),
    grace_period_minutes=10,  # Don't delete recent blobs
)
orphans = await cleaner.aclean_orphans(dry_run=False)
```

### 7.5 Async Service Usage

```python
# NEW: Async file tracking via repository pattern
async with AsyncSQLAlchemyUnitOfWork(db_url) as uow:
    # All operations through repositories
    blob_id = await uow.blobs.asave(content)
    
    commit = FileCommit.create(
        message="Checkpoint files",
        mementos=[FileMemento(path, blob_id, size)],
    )
    await uow.file_commits.asave(commit)
    
    link = CheckpointFileLink(checkpoint_id, commit.id)
    await uow.checkpoint_file_links.aadd(link)
    
    await uow.acommit()  # ATOMIC
```

---

## 8. SOLID & ACID Compliance Summary

> **Note:** Async implementations maintain the same SOLID and ACID properties.
> See [ASYNC_ARCHITECTURE_PLAN.md](../Project_Init/ASYNC_ARCHITECTURE_PLAN.md) §8 for async-specific compliance.

### 8.1 SOLID Principles

| Principle | Assessment | Evidence |
|-----------|------------|----------|
| **S**ingle Responsibility | ✅ Excellent | `BlobRepository` handles blobs only, `FileCommitRepository` handles commits only |
| **O**pen/Closed | ✅ Excellent | New storage backends via interface implementation |
| **L**iskov Substitution | ✅ Excellent | InMemory, SQLAlchemy implementations interchangeable |
| **I**nterface Segregation | ✅ Excellent | Separate `IBlobRepository`, `IFileCommitRepository`, `ICheckpointFileLinkRepository` |
| **D**ependency Inversion | ✅ Excellent | Domain depends on interfaces, not implementations |

### 8.2 ACID Properties

| Property | Implementation | Status |
|----------|----------------|--------|
| **A**tomicity | SQLAlchemy session + UoW commit/rollback | ✅ |
| **C**onsistency | SHA-256 hash validation, FK constraints | ✅ |
| **I**solation | Per-thread sessions, row-level locks | ✅ |
| **D**urability | SQLite WAL mode, filesystem fsync | ✅ |

---

## 9. Appendix

### 9.1 Related Documents

| Document | Description |
|----------|-------------|
| [INDEX.md](INDEX.md) | File Processing overview |
| [../Project_Init/ARCHITECTURE_STRUCTURE.md](../Project_Init/ARCHITECTURE_STRUCTURE.md) | Full architecture |
| [../Project_Init/ASYNC_ARCHITECTURE_PLAN.md](../Project_Init/ASYNC_ARCHITECTURE_PLAN.md) | **Async architecture (v2.0)** |
| [../Adapter_and_WTB-Storage/INDEX.md](../Adapter_and_WTB-Storage/INDEX.md) | Storage adapters |

### 9.2 Key Files

**Current (Sync):**
```
wtb/domain/interfaces/
├── file_processing_repository.py    # IBlobRepository, IFileCommitRepository, ICheckpointFileLinkRepository
└── unit_of_work.py                  # IUnitOfWork (needs blobs, file_commits)

wtb/infrastructure/database/
├── file_processing_orm.py           # FileBlobORM, FileCommitORM, FileMementoORM
├── repositories/
│   └── file_processing_repository.py # SQLAlchemy implementations
└── unit_of_work.py                  # SQLAlchemyUnitOfWork (needs update)

wtb/infrastructure/file_tracking/
├── sqlite_service.py                # SqliteFileTrackingService (lightweight)
├── mock_service.py                  # MockFileTrackingService (testing)
└── filetracker_service.py           # FileTrackerService (legacy wrapper)
```

**Future (Async - from ASYNC_ARCHITECTURE_PLAN.md):**
```
wtb/domain/interfaces/
├── async_file_processing_repository.py   # IAsyncBlobRepository, IAsyncFileCommitRepository (NEW)
└── async_unit_of_work.py                 # IAsyncUnitOfWork with blobs, file_commits (NEW)

wtb/infrastructure/database/
├── async_repositories/
│   └── async_file_processing_repository.py # AsyncSQLAlchemy implementations (NEW)
└── async_unit_of_work.py                   # AsyncSQLAlchemyUnitOfWork (NEW)

wtb/infrastructure/file_tracking/
├── async_file_tracker_service.py    # AsyncFileTrackerService (NEW)
└── async_orphan_cleaner.py          # AsyncBlobOrphanCleaner (NEW)
```

### 9.3 Decision History

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-27 | Adopt SQLAlchemy for file tracking | Unified DB management, ACID compliance |
| 2026-01-27 | Keep `file_processing/` as reference | No breaking changes, educational value |
| 2026-01-27 | Recommend UoW integration for `file_commits` | Complete ACID across file operations |
| 2026-01-27 | **Add async architecture alignment (v2.0)** | Non-blocking I/O, ASYNC_ARCHITECTURE_PLAN.md alignment |
| 2026-01-28 | **Implement UoW Integration** | Added `blobs` and `file_commits` to `IUnitOfWork` and `SQLAlchemyUnitOfWork` |
| 2026-01-28 | **Implement Async Architecture v2.0** | Full async stack: adapters, controllers, repositories, services |
| 2026-01-28 | **Add Transaction Consistency Tests** | Comprehensive tests for Scenarios A-E (idempotency, partial commit, ordering, isolation, node env) |

### 9.4 Implementation Summary (v2.0)

**New Files Created (2026-01-28):**

| File | Purpose |
|------|---------|
| `wtb/infrastructure/adapters/async_langgraph_state_adapter.py` | Async state adapter implementing `IAsyncStateAdapter` |
| `wtb/application/services/async_execution_controller.py` | Async execution orchestration with ACID transactions |
| `tests/test_file_processing/integration/test_async_transaction_consistency.py` | Comprehensive transaction consistency tests |

**Error Scenarios Tested:**

| Scenario | Problem | Solution | Test Class |
|----------|---------|----------|------------|
| A | Non-idempotent writes cause duplicates | Content-addressable storage (SHA-256) | `TestScenarioA_Idempotency` |
| B | Partial commit leaves orphan data | Two-phase write + orphan cleanup | `TestScenarioB_PartialCommit` |
| C | Async tasks lack ordering | Outbox pattern with FIFO guarantee | `TestScenarioC_AsyncOrdering` |
| D | Stale reads across transactions | Session isolation + explicit commit | `TestScenarioD_StaleReads` |
| E | Node env conflicts with workflow env | Node-level venv via GrpcEnvironmentProvider | `TestScenarioE_NodeEnvironmentIsolation` |

---

**Document Version:** 2.0  
**Last Updated:** 2026-01-28  
**Authors:** Architecture Team

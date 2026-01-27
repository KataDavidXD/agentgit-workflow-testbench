# File Processing Module Documentation

**Last Updated:** 2026-01-15

## Overview

The File Processing module provides Git-like file version control integrated with the WTB (Workflow Test Bench) system. It implements the **Memento Design Pattern** for file state snapshots and follows **DDD** (Domain-Driven Design) principles.

## Documentation Structure

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture, SOLID/ACID compliance, design decisions |
| [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | Database schema, migrations, indexes |

## Quick Links

### Domain Layer
- Domain Models: `wtb/domain/models/file_processing.py`
- Domain Interfaces: `wtb/domain/interfaces/file_processing_repository.py`
- Domain Events: `wtb/domain/events/file_processing_events.py`

### Infrastructure Layer
- ORM Models: `wtb/infrastructure/database/models/file_processing_orm.py`
- Repositories: `wtb/infrastructure/database/repositories/file_processing_repository.py`

### Integration
- WTB Integration: `wtb/infrastructure/file_tracking/` (existing)
- Outbox Events: `wtb/domain/models/outbox.py` (FILE_COMMIT_VERIFY, FILE_BLOB_VERIFY)

## Key Concepts

### 1. File Commit
A commit represents a point-in-time snapshot of one or more files. Similar to Git commits.

### 2. File Memento (Memento Pattern)
Captures a file's state (path, hash, size) without exposing internal file content.

### 3. Blob Storage (Content-Addressable)
Files are stored using their SHA-256 hash as the key (like Git's object storage).

### 4. Checkpoint-File Link
Links WTB checkpoints to file commits for coordinated rollback.

## Integration with WTB

```
┌─────────────────────────────────────────────────────────────────┐
│                     WTB Domain Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Checkpoint  │  │  Execution  │  │    FileTrackingResult   │  │
│  │   (State)   │  │   (Domain)  │  │    (Value Object)       │  │
│  └──────┬──────┘  └─────────────┘  └───────────┬─────────────┘  │
│         │                                       │               │
│         │         ┌─────────────────────────────┘               │
│         │         │                                             │
│  ┌──────▼─────────▼─────────────────────────────────────────┐   │
│  │              IFileTrackingService                         │   │
│  │    (track_files, track_and_link, restore_from_checkpoint) │   │
│  └──────────────────────────┬────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                   File Processing Domain                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FileCommit  │  │ FileMemento │  │        BlobId           │  │
│  │  (Entity)   │  │   (Value)   │  │    (Value Object)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              IFileCommitRepository (Interface)               │ │
│  │           IBlobRepository, IFileMementoRepository            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                   Infrastructure Layer                           │
│  ┌─────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │
│  │   ORM       │  │    Repositories     │  │   Blob Storage  │  │
│  │   Models    │  │  (SQLAlchemy UoW)   │  │   (File System) │  │
│  └─────────────┘  └─────────────────────┘  └─────────────────┘  │
│                                                                  │
│                    PostgreSQL / SQLite                           │
└─────────────────────────────────────────────────────────────────┘
```

## SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | FileCommit handles commits, FileMemento handles snapshots, BlobRepository handles storage |
| **OCP** | New storage backends via interface implementation |
| **LSP** | InMemory, SQLAlchemy repositories interchangeable |
| **ISP** | Separate interfaces for commits, mementos, blobs |
| **DIP** | Domain depends on abstractions (IRepository interfaces) |

## ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomicity** | UnitOfWork pattern ensures all-or-nothing commits |
| **Consistency** | Domain invariants enforced in entity constructors |
| **Isolation** | Database-level isolation via transactions |
| **Durability** | PostgreSQL/SQLite with WAL mode |

## Event Flow

```
File Track Request
       │
       ▼
┌──────────────────┐
│ FileTrackingService │
│  track_and_link()  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌─────────────────┐
│ UnitOfWork Begin │────▶│ Create Mementos │
└────────┬─────────┘     └────────┬────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌─────────────────┐
│ Save Blobs       │────▶│ Create Commit   │
└────────┬─────────┘     └────────┬────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌─────────────────┐
│ Add Outbox Event │────▶│ UoW Commit      │
└────────┬─────────┘     └────────┬────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌─────────────────┐
│ Publish Domain   │────▶│ OutboxProcessor │
│     Event        │     │    Verify       │
└──────────────────┘     └─────────────────┘
```

## Test Categories

| Category | Location | Description |
|----------|----------|-------------|
| Unit Tests | `tests/test_wtb/test_file_processing_domain.py` | Domain models, value objects |
| Unit Tests | `tests/test_wtb/test_file_processing_repository.py` | Repository implementations |
| Integration | `tests/test_wtb/test_file_processing_integration.py` | End-to-end transaction tests |

## Migration from Legacy

The refactoring moves functionality from `file_processing/file_processing/FileTracker/` to WTB's domain-driven structure:

| Legacy | New Location |
|--------|--------------|
| `Commit.py` | `wtb/domain/models/file_processing.py` (FileCommit) |
| `FileMemento.py` | `wtb/domain/models/file_processing.py` (FileMemento) |
| `ORM/*.py` | `wtb/infrastructure/database/models/file_processing_orm.py` |
| `Repository/*.py` | `wtb/infrastructure/database/repositories/file_processing_repository.py` |

## Related Documentation

- [WTB Architecture](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md)
- [Database Design](../Project_Init/DATABASE_DESIGN.md)
- [File Tracking Interface](../LangGraph/WTB_INTEGRATION.md)

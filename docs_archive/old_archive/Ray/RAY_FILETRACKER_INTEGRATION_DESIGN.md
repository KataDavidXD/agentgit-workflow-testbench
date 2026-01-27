# Ray + FileTracker Integration Design

**Date:** 2026-01-15
**Status:** ✅ **IMPLEMENTED** (2026-01-15)
**Priority:** P1

## 1. Overview

### 1.1 Problem Statement

当前 Ray 批量测试执行时：
- ✅ 保存工作流状态 (via LangGraph checkpointer / AgentGit)
- ❌ **不追踪文件变更** (FileTracker 未集成)
- ❌ **回滚时不恢复文件** (只恢复状态)

### 1.2 目标

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         目标架构                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Ray Worker                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  VariantExecutionActor                                                      │ │
│  │                                                                             │ │
│  │  1. 执行工作流节点                                                           │ │
│  │     ↓                                                                       │ │
│  │  2. 创建 Checkpoint (状态)  ──────────────────────┐                         │ │
│  │     ↓                                             │                         │ │
│  │  3. 追踪文件变更 ─────────────────┐               │                         │ │
│  │     ↓                             ↓               ↓                         │ │
│  │  4. 创建 FileCommit          FileTracker DB   AgentGit/LangGraph DB        │ │
│  │     ↓                                                                       │ │
│  │  5. 链接 Checkpoint ↔ FileCommit ───────────► WTB DB (checkpoint_files)   │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  回滚时:                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  1. 恢复 Checkpoint 状态                                                     │ │
│  │  2. 查找 checkpoint_files 链接                                               │ │
│  │  3. 调用 FileTracker.restore_commit() 恢复文件                               │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Architecture Design

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATION ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Application Layer                                                               │
│  ═════════════════                                                               │
│  ┌──────────────────────┐    ┌──────────────────────┐                          │
│  │ RayBatchTestRunner   │    │ ExecutionController  │                          │
│  │                      │    │                      │                          │
│  │ orchestrates actors  │    │ controls single exec │                          │
│  └──────────┬───────────┘    └──────────┬───────────┘                          │
│             │                           │                                        │
│             ▼                           ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    IFileTrackingService (NEW)                             │  │
│  │                                                                           │  │
│  │  • track_files(paths: List[str]) -> FileCommit                           │  │
│  │  • link_to_checkpoint(checkpoint_id, commit_id)                          │  │
│  │  • restore_files(commit_id)                                               │  │
│  │  • get_tracked_files(execution_id) -> List[TrackedFile]                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  Infrastructure Layer                │                                          │
│  ════════════════════                ▼                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐                          │
│  │ RayFileTrackingService│    │ LocalFileTrackingService│                       │
│  │                      │    │                      │                          │
│  │ For Ray Workers      │    │ For Local/Testing   │                          │
│  │ (Serializable config)│    │ (Direct connection) │                          │
│  └──────────┬───────────┘    └──────────┬───────────┘                          │
│             │                           │                                        │
│             └───────────┬───────────────┘                                        │
│                         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                       FileTracker System                                   │  │
│  │                                                                           │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ Commit     │  │FileMemento │  │BlobRepository│  │ PostgreSQL DB     │  │  │
│  │  │ Repository │  │            │  │              │  │ + Storage Path    │  │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Execution with File Tracking:
═════════════════════════════

Step 1: Node Execution
────────────────────────────────────────────────────────────────────────
  ExecutionController.run()
       │
       ├── execute_node("data_load")
       │       │
       │       └── node produces files: ["data/output.csv", "models/v1.pkl"]
       │
       ├── _create_checkpoint() → checkpoint_id = 42
       │
       └── file_tracking_service.track_and_link(
               checkpoint_id=42,
               file_paths=["data/output.csv", "models/v1.pkl"]
           )
               │
               ├── 1. Create FileMemento for each file
               │       └── BlobRepository.save() → content-addressed storage
               │
               ├── 2. Create Commit with all mementos
               │       └── CommitRepository.save() → commit_id = "abc-123"
               │
               └── 3. Link checkpoint to commit
                       └── WTB.checkpoint_files.add(checkpoint_id=42, commit_id="abc-123")


Step 2: Rollback with File Restore
────────────────────────────────────────────────────────────────────────
  ExecutionController.rollback(checkpoint_id=42)
       │
       ├── _state_adapter.rollback_to_checkpoint(42)  # Restore state
       │
       └── file_tracking_service.restore_from_checkpoint(42)
               │
               ├── 1. Find commit_id from checkpoint_files
               │       └── commit_id = "abc-123"
               │
               └── 2. Restore all files
                       └── BlobRepository.restore() for each memento
```

## 3. Interface Design

### 3.1 IFileTrackingService Interface

```python
# wtb/domain/interfaces/file_tracking.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TrackedFile:
    """Information about a tracked file."""
    file_path: str
    file_hash: str
    size_bytes: int
    tracked_at: datetime


@dataclass  
class FileTrackingResult:
    """Result of a file tracking operation."""
    commit_id: str
    files_tracked: int
    total_size_bytes: int
    file_hashes: Dict[str, str]  # path -> hash


class IFileTrackingService(ABC):
    """
    Interface for file tracking integration.
    
    Follows DIP - high-level components depend on this abstraction,
    not on concrete FileTracker implementation.
    """
    
    @abstractmethod
    def track_files(
        self,
        file_paths: List[str],
        message: Optional[str] = None,
    ) -> FileTrackingResult:
        """
        Track specified files and create a commit.
        
        Args:
            file_paths: List of file paths to track
            message: Optional commit message
            
        Returns:
            FileTrackingResult with commit info
        """
        pass
    
    @abstractmethod
    def track_and_link(
        self,
        checkpoint_id: int,
        file_paths: List[str],
        message: Optional[str] = None,
    ) -> FileTrackingResult:
        """
        Track files AND link to checkpoint in single operation.
        
        Args:
            checkpoint_id: Checkpoint to link to
            file_paths: Files to track
            message: Optional commit message
            
        Returns:
            FileTrackingResult with commit info
        """
        pass
    
    @abstractmethod
    def link_to_checkpoint(
        self,
        checkpoint_id: int,
        commit_id: str,
    ) -> bool:
        """
        Link existing commit to checkpoint.
        
        Args:
            checkpoint_id: WTB checkpoint ID
            commit_id: FileTracker commit ID
            
        Returns:
            True if linked successfully
        """
        pass
    
    @abstractmethod
    def restore_from_checkpoint(
        self,
        checkpoint_id: int,
    ) -> bool:
        """
        Restore files from checkpoint's linked commit.
        
        Args:
            checkpoint_id: Checkpoint to restore from
            
        Returns:
            True if restored successfully
        """
        pass
    
    @abstractmethod
    def restore_commit(
        self,
        commit_id: str,
    ) -> bool:
        """
        Restore files from a specific commit.
        
        Args:
            commit_id: FileTracker commit ID
            
        Returns:
            True if restored successfully
        """
        pass
    
    @abstractmethod
    def get_commit_for_checkpoint(
        self,
        checkpoint_id: int,
    ) -> Optional[str]:
        """
        Get the file commit ID linked to a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to query
            
        Returns:
            Commit ID if linked, None otherwise
        """
        pass
```

### 3.2 FileTrackingConfig

```python
# wtb/config.py (additions)

@dataclass
class FileTrackingConfig:
    """
    FileTracker integration configuration.
    
    Attributes:
        enabled: Enable file tracking
        postgres_url: PostgreSQL connection string for FileTracker
        storage_path: Path for blob storage
        auto_track_patterns: Glob patterns for auto-tracking
        excluded_patterns: Patterns to exclude from tracking
    """
    enabled: bool = False
    postgres_url: Optional[str] = None
    storage_path: str = "./file_storage"
    auto_track_patterns: List[str] = field(default_factory=lambda: ["*.csv", "*.pkl", "*.json"])
    excluded_patterns: List[str] = field(default_factory=lambda: ["*.tmp", "*.log"])
    
    @classmethod
    def for_testing(cls) -> "FileTrackingConfig":
        """In-memory mock for testing."""
        return cls(enabled=False)
    
    @classmethod
    def for_development(cls, storage_path: str = "./data/file_storage") -> "FileTrackingConfig":
        """SQLite-based for development."""
        return cls(
            enabled=True,
            postgres_url="postgresql://localhost/filetracker_dev",
            storage_path=storage_path,
        )
    
    @classmethod
    def for_production(cls, postgres_url: str, storage_path: str) -> "FileTrackingConfig":
        """PostgreSQL for production."""
        return cls(
            enabled=True,
            postgres_url=postgres_url,
            storage_path=storage_path,
        )
```

## 4. Implementation Plan

### 4.1 Phase 1: Core Interface & Mock (Day 1)

| Task | File | Description |
|------|------|-------------|
| Create interface | `wtb/domain/interfaces/file_tracking.py` | IFileTrackingService |
| Create config | `wtb/config.py` | FileTrackingConfig |
| Mock implementation | `wtb/infrastructure/file_tracking/mock_service.py` | For testing |
| Unit tests | `tests/test_wtb/test_file_tracking_interface.py` | Interface tests |

### 4.2 Phase 2: FileTracker Implementation (Day 2)

| Task | File | Description |
|------|------|-------------|
| FileTracker service | `wtb/infrastructure/file_tracking/filetracker_service.py` | Real implementation |
| Ray-compatible service | `wtb/infrastructure/file_tracking/ray_filetracker_service.py` | Serializable for actors |
| Integration tests | `tests/test_wtb/test_filetracker_integration.py` | With real FileTracker |

### 4.3 Phase 3: Ray Actor Integration (Day 3)

| Task | File | Description |
|------|------|-------------|
| Update Actor | `wtb/application/services/ray_batch_runner.py` | Add file tracking calls |
| Update Controller | `wtb/application/services/execution_controller.py` | Add file tracking |
| Update Factory | `wtb/application/factories.py` | FileTrackingServiceFactory |
| E2E tests | `tests/test_wtb/test_ray_with_filetracker.py` | Full flow tests |

## 5. Ray Actor Changes

### 5.1 Updated VariantExecutionActor

```python
@ray.remote
class VariantExecutionActor:
    """
    Ray Actor for executing workflow variants WITH file tracking.
    """
    
    def __init__(
        self,
        agentgit_db_url: str,
        wtb_db_url: str,
        actor_id: str,
        # NEW: FileTracker config (serializable)
        filetracker_config: Optional[Dict[str, Any]] = None,
    ):
        self._agentgit_db_url = agentgit_db_url
        self._wtb_db_url = wtb_db_url
        self._actor_id = actor_id
        self._filetracker_config = filetracker_config
        
        # Lazy-initialized
        self._file_tracking_service: Optional[IFileTrackingService] = None
    
    def _ensure_initialized(self):
        """Initialize dependencies including file tracking."""
        if self._initialized:
            return
        
        # ... existing initialization ...
        
        # NEW: Initialize file tracking service
        if self._filetracker_config and self._filetracker_config.get("enabled"):
            from wtb.infrastructure.file_tracking import FileTrackerService
            self._file_tracking_service = FileTrackerService(
                postgres_url=self._filetracker_config["postgres_url"],
                storage_path=self._filetracker_config["storage_path"],
                wtb_db_url=self._wtb_db_url,
            )
    
    def _run_workflow_execution(self, ...):
        """Run workflow with file tracking."""
        # ... execute node ...
        
        # After node execution, track files if service available
        if self._file_tracking_service:
            output_files = self._collect_output_files(node, result)
            if output_files:
                self._file_tracking_service.track_and_link(
                    checkpoint_id=checkpoint_id,
                    file_paths=output_files,
                    message=f"Node {node_id} outputs",
                )
```

### 5.2 Updated RayBatchTestRunner

```python
class RayBatchTestRunner(IBatchTestRunner):
    
    def __init__(
        self,
        config: RayConfig,
        agentgit_db_url: str,
        wtb_db_url: str,
        # NEW: FileTracker config
        filetracker_config: Optional[FileTrackingConfig] = None,
        ...
    ):
        self._filetracker_config = filetracker_config
    
    def _create_actor_pool(self, num_workers: int):
        """Create actors with file tracking config."""
        
        # Serialize config for Ray transmission
        ft_config_dict = None
        if self._filetracker_config and self._filetracker_config.enabled:
            ft_config_dict = {
                "enabled": True,
                "postgres_url": self._filetracker_config.postgres_url,
                "storage_path": self._filetracker_config.storage_path,
            }
        
        for i in range(num_workers):
            actor = VariantExecutionActor.options(...).remote(
                agentgit_db_url=self._agentgit_db_url,
                wtb_db_url=self._wtb_db_url,
                actor_id=f"actor_{i}",
                filetracker_config=ft_config_dict,  # NEW
            )
            self._actors.append(actor)
```

## 6. File Structure

```
wtb/
├── domain/
│   └── interfaces/
│       └── file_tracking.py           [NEW] IFileTrackingService interface
│
├── infrastructure/
│   └── file_tracking/                  [NEW] File tracking implementations
│       ├── __init__.py
│       ├── mock_service.py            Mock for testing
│       ├── filetracker_service.py     Real FileTracker implementation
│       └── ray_filetracker_service.py Ray-compatible wrapper
│
├── application/
│   └── services/
│       └── ray_batch_runner.py        [MODIFIED] Add file tracking
│
└── config.py                          [MODIFIED] Add FileTrackingConfig

tests/
└── test_wtb/
    ├── test_file_tracking_interface.py  [NEW] Interface tests
    ├── test_filetracker_integration.py  [NEW] FileTracker tests
    └── test_ray_with_filetracker.py     [NEW] E2E tests
```

## 7. SOLID & ACID Compliance

### 7.1 SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **SRP** | `IFileTrackingService` only handles file operations |
| **OCP** | New tracking strategies via interface implementation |
| **LSP** | Mock, Local, Ray services are interchangeable |
| **ISP** | Focused interface with single responsibility |
| **DIP** | High-level components depend on `IFileTrackingService` abstraction |

### 7.2 ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | Commit creation is atomic in FileTracker |
| **Consistent** | Checkpoint-file link created in same transaction |
| **Isolated** | Each actor has isolated FileTracker connection |
| **Durable** | PostgreSQL + blob storage ensures durability |

## 8. Configuration Example

```python
# Production setup with Ray + FileTracker
from wtb.config import WTBConfig, RayConfig, FileTrackingConfig

config = WTBConfig(
    wtb_storage_mode="sqlalchemy",
    wtb_db_url="postgresql://wtb_user:pass@localhost/wtb",
    
    ray_enabled=True,
    ray_config=RayConfig.for_production(
        ray_address="ray://cluster:10001",
        num_workers=20,
    ),
    
    # NEW: FileTracker integration
    filetracker_config=FileTrackingConfig.for_production(
        postgres_url="postgresql://ft_user:pass@localhost/filetracker",
        storage_path="/data/file_storage",
    ),
)

# Create runner with file tracking
runner = BatchTestRunnerFactory.create(config)
```

## 9. Rollback Flow with Files

```python
def rollback_with_files(execution_id: str, checkpoint_id: int):
    """
    Unified rollback: state + files.
    
    1. Restore state via LangGraph/AgentGit
    2. Restore files via FileTracker
    """
    
    # Step 1: State rollback
    state_adapter.rollback_to_checkpoint(checkpoint_id)
    
    # Step 2: File rollback
    if file_tracking_service:
        commit_id = file_tracking_service.get_commit_for_checkpoint(checkpoint_id)
        if commit_id:
            file_tracking_service.restore_commit(commit_id)
            logger.info(f"Restored files from commit {commit_id}")
    
    return restored_state
```

## 10. Implementation Status (2026-01-15)

1. [x] Implement `IFileTrackingService` interface - `wtb/domain/interfaces/file_tracking.py`
2. [x] Implement `FileTrackingConfig` - `wtb/config.py`
3. [x] Implement `MockFileTrackingService` for testing - `wtb/infrastructure/file_tracking/mock_service.py`
4. [x] Implement `FileTrackerService` with real FileTracker - `wtb/infrastructure/file_tracking/filetracker_service.py`
5. [x] Implement `RayFileTrackerService` (serializable) - `wtb/infrastructure/file_tracking/ray_filetracker_service.py`
6. [x] Update `VariantExecutionActor` to use file tracking
7. [x] Update `RayBatchTestRunner` to pass config to actors
8. [x] Add comprehensive tests (31 unit tests, 16 integration tests)
9. [x] Update documentation

### Test Results

```
tests/test_wtb/test_file_tracking.py: 31 passed
tests/test_wtb/test_ray_filetracker_integration.py: 16 passed, 4 skipped (Ray not installed)
```

---

## Appendix A: Migration from Current State

If you have existing executions without file tracking:

```python
# Backfill script for existing checkpoints
def backfill_file_links(execution_id: str):
    """
    Scan execution history and create file commits for each checkpoint.
    """
    history = checkpoint_store.load_history(execution_id)
    
    for checkpoint in history.checkpoints:
        # Find files that existed at this checkpoint time
        # (requires separate tracking or heuristics)
        pass
```

**Recommendation**: Start fresh with new executions rather than backfilling.

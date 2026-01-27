# WTB Async Architecture Plan

**Version:** 1.1**Date:** 2026-01-27**Status:** Proposed (Reviewed)**Target Version:** v2.0

> **Review Note (v1.1):** Incorporates colleague code review feedback addressing:
>
> - aiofiles API correctness, async context handling, error handling patterns,
> - ISP compliance, cross-DB consistency, saga compensation, connection pooling

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Async Architecture Vision](#3-async-architecture-vision)
4. [Layer-by-Layer Implementation](#4-layer-by-layer-implementation)
5. [Integration Patterns](#5-integration-patterns)
6. [Transaction Consistency](#6-transaction-consistency)
7. [Migration Strategy](#7-migration-strategy)
8. [SOLID &amp; ACID Compliance](#8-solid--acid-compliance)
   - 8.3 [Best Practices &amp; Additional Patterns](#83-best-practices--additional-patterns)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Appendix: Code Examples](#10-appendix-code-examples)
11. [Appendix: Code Review Summary (v1.1)](#appendix-code-review-summary-v11)

---

## 1. Executive Summary

### 1.1 Goal

Transform WTB from a **mixed sync/async architecture** to a **fully async-first architecture** while maintaining:

- ACID transaction consistency across multiple databases
- SOLID principles compliance
- Backward compatibility during migration
- Clear separation of concerns

### 1.2 Key Benefits

| Benefit                                | Impact                                      |
| -------------------------------------- | ------------------------------------------- |
| **Non-blocking I/O**             | API can handle 10x more concurrent requests |
| **Better Resource Utilization**  | Single process handles multiple workflows   |
| **Native LangGraph Integration** | Direct use of `ainvoke()`, `astream()`  |
| **Unified Async Pattern**        | Consistent codebase, easier maintenance     |
| **Real-time Events**             | WebSocket streaming without blocking        |

### 1.3 Architecture Principle

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ASYNC-FIRST PRINCIPLE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   "Everything that CAN be async SHOULD be async"                                │
│                                                                                  │
│   Exceptions (remain sync):                                                      │
│   1. CPU-bound computation → Offload to Ray/ProcessPool                         │
│   2. Legacy library calls → Wrap in run_in_executor()                           │
│   3. Atomic in-memory operations → No benefit from async                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Current State Analysis

### 2.1 Layer Async Status

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CURRENT ASYNC STATUS BY LAYER                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Layer                    Current          Target           Gap                 │
│   ──────────────────────   ───────          ──────           ───                 │
│   API (FastAPI)            ✅ Async          ✅ Async          None              │
│   WebSocket                ✅ Async          ✅ Async          None              │
│   Application Services     ⚠️  Mixed          ✅ Async          HIGH             │
│   Domain Interfaces        ❌ Sync           ✅ Async          HIGH             │
│   Infrastructure/DB        ❌ Sync           ✅ Async          MEDIUM           │
│   Infrastructure/Events    ✅ Async          ✅ Async          None              │
│   LangGraph Adapter        ⚠️  Mixed          ✅ Async          MEDIUM           │
│   File Tracking            ❌ Sync           ✅ Async          MEDIUM           │
│   Venv Manager             ✅ Async          ✅ Async          LOW              │
│   Ray Integration          ✅ Parallel       ✅ Parallel       None              │
│                                                                                  │
│   Legend: ✅ = Complete  ⚠️ = Partial  ❌ = Not Started                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Current Blocking Points

| Component                              | Blocking Call               | Impact                   |
| -------------------------------------- | --------------------------- | ------------------------ |
| `ExecutionController.run()`          | `state_adapter.execute()` | Blocks entire event loop |
| `IUnitOfWork.commit()`               | SQLAlchemy sync session     | Blocks on DB I/O         |
| `IFileTrackingService.track_files()` | Sync file I/O               | Blocks on disk I/O       |
| `IStateAdapter.save_checkpoint()`    | Sync checkpoint write       | Blocks on DB I/O         |

### 2.3 Current Architecture Flow (Sync)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT SYNC EXECUTION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   API Route (async)      ExecutionService      ExecutionController (SYNC!)      │
│        │                       │                        │                        │
│        │  await service.run()  │                        │                        │
│        │──────────────────────>│                        │                        │
│        │                       │                        │                        │
│        │                       │  controller.run()     │                        │
│        │                       │  ─────────────────────>│                        │
│        │                       │                        │                        │
│        │                       │      ┌─────────────────┤                        │
│        │                       │      │ BLOCKS HERE!    │                        │
│        │                       │      │                 │                        │
│        │                       │      │ state_adapter   │                        │
│        │                       │      │   .execute()    │                        │
│        │                       │      │                 │                        │
│        │                       │      │ (sync call)     │                        │
│        │                       │      └─────────────────┤                        │
│        │                       │                        │                        │
│        │                       │◀──────────────────────│                        │
│        │◀──────────────────────│                        │                        │
│                                                                                  │
│   PROBLEM: Event loop blocked during entire workflow execution!                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Async Architecture Vision

### 3.1 Target Architecture Flow (Async)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     TARGET ASYNC EXECUTION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   API Route              ExecutionService       ExecutionController (ASYNC)     │
│        │                       │                        │                        │
│        │  await service.run()  │                        │                        │
│        │──────────────────────>│                        │                        │
│        │                       │                        │                        │
│        │                       │  await controller      │                        │
│        │                       │    .arun()             │                        │
│        │                       │  ──────────────────────>│                        │
│        │                       │                        │                        │
│        │                       │      ┌─────────────────┤                        │
│        │ ◀─── Event Loop Free  │      │ await state_    │                        │
│        │      to handle other  │      │   adapter       │                        │
│        │      requests! ◀────  │      │   .aexecute()   │                        │
│        │                       │      │                 │                        │
│        │                       │      │ (yields control)│                        │
│        │                       │      └─────────────────┤                        │
│        │                       │                        │                        │
│        │                       │◀──────────────────────│                        │
│        │◀──────────────────────│                        │                        │
│                                                                                  │
│   BENEFIT: Event loop handles multiple concurrent workflows!                    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Async Interface Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ASYNC INTERFACE STRATEGY (ISP COMPLIANT)                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ❌ AVOID: Dual Interface (Violates ISP)                                       │
│   ─────────────────────────────────────────                                     │
│                                                                                  │
│   # BAD - Forces implementers to implement both sync AND async                  │
│   class IStateAdapter(ABC):                                                     │
│       @abstractmethod                                                           │
│       def execute(self, state: Dict) -> Dict:          # Sync                   │
│           pass                                                                   │
│       @abstractmethod                                                           │
│       async def aexecute(self, state: Dict) -> Dict:   # Async                  │
│           pass                                                                   │
│                                                                                  │
│   ─────────────────────────────────────────                                     │
│   ✅ RECOMMENDED: Separate Interfaces (ISP Compliant)                           │
│   ─────────────────────────────────────────                                     │
│                                                                                  │
│   # GOOD - Separate interfaces, implementers choose which to implement          │
│   class IStateAdapter(ABC):              # Existing sync interface (unchanged)  │
│       @abstractmethod                                                           │
│       def execute(self, state: Dict) -> Dict:                                   │
│           pass                                                                   │
│                                                                                  │
│   class IAsyncStateAdapter(ABC):         # NEW: Async-only interface            │
│       @abstractmethod                                                           │
│       async def execute(self, state: Dict) -> Dict:                             │
│           pass                                                                   │
│                                                                                  │
│   ─────────────────────────────────────────                                     │
│   Sync Wrapper (for backward compatibility):                                    │
│   ─────────────────────────────────────────                                     │
│                                                                                  │
│   def run_sync(async_adapter: IAsyncStateAdapter, state: Dict) -> Dict:         │
│       """Run async adapter synchronously - only use outside async context."""   │
│       try:                                                                       │
│           asyncio.get_running_loop()                                            │
│           raise RuntimeError(                                                   │
│               "Cannot call sync wrapper from async context. "                   │
│               "Use 'await adapter.execute()' instead."                          │
│           )                                                                      │
│       except RuntimeError:                                                       │
│           # No running loop - safe to use asyncio.run()                         │
│           return asyncio.run(async_adapter.execute(state))                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Layer-by-Layer Implementation

### 4.1 Domain Layer (`wtb/domain/`)

#### 4.1.1 Async Repository Interfaces

```python
# wtb/domain/interfaces/async_repositories.py

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List

T = TypeVar('T')


class IAsyncReadRepository(ABC, Generic[T]):
    """Async read-only repository interface."""
  
    @abstractmethod
    async def aget(self, id: str) -> Optional[T]:
        """Get entity by ID asynchronously."""
        pass
  
    @abstractmethod
    async def alist(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List entities with pagination asynchronously."""
        pass
  
    @abstractmethod
    async def aexists(self, id: str) -> bool:
        """Check if entity exists asynchronously."""
        pass


class IAsyncWriteRepository(ABC, Generic[T]):
    """Async write repository interface."""
  
    @abstractmethod
    async def aadd(self, entity: T) -> T:
        """Add entity asynchronously."""
        pass
  
    @abstractmethod
    async def aupdate(self, entity: T) -> T:
        """Update entity asynchronously."""
        pass
  
    @abstractmethod
    async def adelete(self, id: str) -> bool:
        """Delete entity asynchronously."""
        pass


class IAsyncRepository(IAsyncReadRepository[T], IAsyncWriteRepository[T]):
    """Combined async read/write repository."""
    pass


class IAsyncOutboxRepository(ABC):
    """
    Async outbox repository with FIFO ordering guarantee.
  
    IMPORTANT: Events MUST be processed in creation order (FIFO)
    to maintain causal consistency.
    """
  
    @abstractmethod
    async def aadd(self, event: "OutboxEvent") -> "OutboxEvent":
        """Add outbox event."""
        pass
  
    @abstractmethod
    async def aget_pending(
        self,
        limit: int = 100,
        order_by: str = "created_at",  # FIFO ordering - DO NOT CHANGE
    ) -> List["OutboxEvent"]:
        """
        Get pending events in FIFO order.
      
        Args:
            limit: Max events to retrieve
            order_by: Column to order by (default: created_at for FIFO)
      
        Returns:
            Events ordered by creation time (oldest first)
        """
        pass
  
    @abstractmethod
    async def aupdate(self, event: "OutboxEvent") -> "OutboxEvent":
        """Update outbox event status."""
        pass
  
    @abstractmethod
    async def adelete_processed(self, older_than_hours: int = 24) -> int:
        """Delete processed events older than threshold."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Async File Processing Repositories
# (Aligned with FILE_TRACKING_ARCHITECTURE_DECISION.md)
# ═══════════════════════════════════════════════════════════════════════════════


class IAsyncBlobRepository(ABC):
    """
    Async blob storage interface.
    
    Content-addressable storage using SHA-256 hashes.
    Aligned with sync IBlobRepository from file_processing_repository.py.
    
    Two-Phase Write Pattern:
    1. Filesystem write (async via aiofiles)
    2. DB record in session
    3. Commit → both or neither persisted
    
    Note: If commit fails, orphaned blobs may remain on filesystem.
    Use AsyncBlobOrphanCleaner for periodic cleanup.
    """
    
    @abstractmethod
    async def asave(self, content: bytes) -> "BlobId":
        """
        Save content to blob storage asynchronously.
        
        Content-addressable: Returns same BlobId for same content.
        Idempotent: Calling with same content multiple times is safe.
        
        Args:
            content: Binary content to store
            
        Returns:
            BlobId (SHA-256 hash of content)
        """
        pass
    
    @abstractmethod
    async def aget(self, blob_id: "BlobId") -> Optional[bytes]:
        """
        Retrieve content by blob ID asynchronously.
        
        Args:
            blob_id: Content-addressable identifier
            
        Returns:
            Binary content if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def aexists(self, blob_id: "BlobId") -> bool:
        """Check if blob exists asynchronously."""
        pass
    
    @abstractmethod
    async def adelete(self, blob_id: "BlobId") -> bool:
        """Delete blob asynchronously. Returns True if deleted."""
        pass
    
    @abstractmethod
    async def arestore_to_file(self, blob_id: "BlobId", output_path: Path) -> None:
        """
        Restore blob content to file system asynchronously.
        
        Creates parent directories if needed using aiofiles.os.makedirs().
        
        Args:
            blob_id: Blob to restore
            output_path: Destination file path
            
        Raises:
            FileNotFoundError: If blob not found
        """
        pass
    
    @abstractmethod
    async def alist_all_hashes(self) -> List["BlobId"]:
        """
        List all blob hashes in storage.
        
        Used by AsyncBlobOrphanCleaner to detect orphans.
        """
        pass


class IAsyncFileCommitRepository(ABC):
    """
    Async repository for FileCommit aggregate root.
    
    Aligned with sync IFileCommitRepository from file_processing_repository.py.
    
    Aggregate Pattern:
    - FileCommit is the aggregate root
    - FileMemento entities are owned by FileCommit
    - Save/delete operations cascade to mementos
    """
    
    @abstractmethod
    async def asave(self, commit: "FileCommit") -> None:
        """
        Save commit with all mementos atomically.
        
        Updates existing commit if ID exists.
        """
        pass
    
    @abstractmethod
    async def aget_by_id(self, commit_id: "CommitId") -> Optional["FileCommit"]:
        """Get commit by ID with mementos loaded."""
        pass
    
    @abstractmethod
    async def aget_by_id_without_mementos(self, commit_id: "CommitId") -> Optional["FileCommit"]:
        """Get commit by ID WITHOUT mementos (performance optimization)."""
        pass
    
    @abstractmethod
    async def aget_by_checkpoint_id(self, checkpoint_id: str) -> Optional["FileCommit"]:
        """Get commit linked to checkpoint."""
        pass
    
    @abstractmethod
    async def aget_by_execution_id(self, execution_id: str) -> List["FileCommit"]:
        """Get all commits for an execution."""
        pass
    
    @abstractmethod
    async def adelete(self, commit_id: "CommitId") -> bool:
        """Delete commit and cascade to mementos."""
        pass
    
    @abstractmethod
    async def acount(self) -> int:
        """Get total number of commits."""
        pass


class IAsyncCheckpointFileLinkRepository(ABC):
    """
    Async repository for checkpoint-file links.
    
    Manages associations between WTB checkpoints and file commits.
    Used for coordinated rollback across state and file systems.
    """
    
    @abstractmethod
    async def aadd(self, link: "CheckpointFileLink") -> None:
        """Add a checkpoint-file link (upsert behavior)."""
        pass
    
    @abstractmethod
    async def aget_by_checkpoint(self, checkpoint_id: str) -> Optional["CheckpointFileLink"]:
        """Get link by checkpoint ID."""
        pass
    
    @abstractmethod
    async def aget_by_commit(self, commit_id: "CommitId") -> List["CheckpointFileLink"]:
        """Get all links for a commit."""
        pass
    
    @abstractmethod
    async def adelete_by_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete link by checkpoint ID."""
        pass
    
    @abstractmethod
    async def adelete_by_commit(self, commit_id: "CommitId") -> int:
        """Delete all links for a commit. Returns count deleted."""
        pass
```

#### 4.1.2 Async Unit of Work Interface

```python
# wtb/domain/interfaces/async_unit_of_work.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from contextlib import asynccontextmanager

if TYPE_CHECKING:
    from .async_repositories import IAsyncRepository


class IAsyncUnitOfWork(ABC):
    """
    Async Unit of Work pattern interface.
    
    ACID Compliance:
    - Atomicity: All changes committed or rolled back together
    - Consistency: Validation before commit
    - Isolation: Session-level isolation
    - Durability: Persistent storage on commit
    
    Usage:
        async with uow:
            workflow = await uow.workflows.aget(workflow_id)
            execution = Execution(workflow_id=workflow.id)
            await uow.executions.aadd(execution)
            await uow.acommit()
    
    File Tracking Usage:
        async with uow:
            blob_id = await uow.blobs.asave(content)
            commit = FileCommit.create(mementos=[...])
            await uow.file_commits.asave(commit)
            await uow.checkpoint_file_links.aadd(link)
            await uow.acommit()  # ATOMIC: all or nothing
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WTB Core Repositories
    # ═══════════════════════════════════════════════════════════════════════════
    workflows: "IAsyncWorkflowRepository"
    executions: "IAsyncExecutionRepository"
    variants: "IAsyncNodeVariantRepository"
    batch_tests: "IAsyncBatchTestRepository"
    evaluation_results: "IAsyncEvaluationResultRepository"
    audit_logs: "IAsyncAuditLogRepository"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # File Processing Repositories (from FILE_TRACKING_ARCHITECTURE_DECISION.md)
    # ═══════════════════════════════════════════════════════════════════════════
    blobs: "IAsyncBlobRepository"
    file_commits: "IAsyncFileCommitRepository"
    checkpoint_file_links: "IAsyncCheckpointFileLinkRepository"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Infrastructure Repositories
    # ═══════════════════════════════════════════════════════════════════════════
    outbox: "IAsyncOutboxRepository"
  
    @abstractmethod
    async def __aenter__(self) -> "IAsyncUnitOfWork":
        """Begin async transaction."""
        pass
  
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End async transaction with auto-rollback on exception."""
        pass
  
    @abstractmethod
    async def acommit(self) -> None:
        """Commit transaction asynchronously."""
        pass
  
    @abstractmethod
    async def arollback(self) -> None:
        """Rollback transaction asynchronously."""
        pass
```

#### 4.1.3 Async State Adapter Interface

```python
# wtb/domain/interfaces/async_state_adapter.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator

from ..models.workflow import ExecutionState


class IAsyncStateAdapter(ABC):
    """
    Async State Adapter Interface.
  
    Provides async operations for:
    - Session management
    - Checkpoint operations
    - Execution control
    - Streaming support
  
    SOLID:
    - SRP: Only state management
    - OCP: New adapters via implementation
    - LSP: All implementations interchangeable
    - ISP: Focused interface (~15 methods)
    - DIP: Application depends on this abstraction
    """
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def ainitialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[str]:
        """Initialize session asynchronously."""
        pass
  
    @abstractmethod
    async def aset_current_session(
        self, 
        session_id: str,
        execution_id: Optional[str] = None,
    ) -> bool:
        """Set current session asynchronously."""
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoint Operations (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def asave_checkpoint(
        self,
        state: ExecutionState,
        node_id: str,
        trigger: "CheckpointTrigger",
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save checkpoint asynchronously. Returns checkpoint_id."""
        pass
  
    @abstractmethod
    async def aload_checkpoint(self, checkpoint_id: str) -> ExecutionState:
        """Load checkpoint asynchronously."""
        pass
  
    @abstractmethod
    async def arollback(self, to_checkpoint_id: str) -> ExecutionState:
        """Rollback to checkpoint asynchronously."""
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Execution (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def aexecute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute workflow asynchronously.
      
        This is the PRIMARY async execution method. Uses LangGraph's ainvoke().
        """
        pass
  
    @abstractmethod
    async def astream(
        self, 
        initial_state: Dict[str, Any],
        stream_mode: str = "updates"
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream execution events asynchronously.
      
        Yields state updates as they occur. Uses LangGraph's astream().
        """
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # State Operations (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def aupdate_state(
        self, 
        values: Dict[str, Any], 
        as_node: Optional[str] = None
    ) -> bool:
        """Update state asynchronously (human-in-the-loop)."""
        pass
  
    @abstractmethod
    async def aget_current_state(self) -> Dict[str, Any]:
        """Get current state asynchronously."""
        pass
```

### 4.2 Application Layer (`wtb/application/`)

#### 4.2.1 Async Execution Controller

```python
# wtb/application/services/async_execution_controller.py

from typing import Optional, Dict, Any, List, AsyncIterator
import logging

from wtb.domain.interfaces.async_state_adapter import IAsyncStateAdapter
from wtb.domain.interfaces.async_unit_of_work import IAsyncUnitOfWork
from wtb.domain.models import Execution, ExecutionState, ExecutionStatus

logger = logging.getLogger(__name__)


class AsyncExecutionController:
    """
    Async Execution Controller.
  
    Orchestrates workflow execution with full async support:
    - Non-blocking execution via arun()
    - Streaming via astream()
    - Async checkpoint operations
    - Async file tracking
  
    SOLID Compliance:
    - SRP: Orchestration only, delegates to adapters
    - OCP: New adapters via IAsyncStateAdapter
    - DIP: Depends on abstractions
  
    ACID Compliance:
    - Atomicity: Async UoW transactions
    - Consistency: State validation before commit
    - Isolation: Session-level isolation
    - Durability: Async commit to persistent storage
    """
  
    def __init__(
        self,
        state_adapter: IAsyncStateAdapter,
        uow_factory: "Callable[[], IAsyncUnitOfWork]",
        file_tracking_service: Optional["IAsyncFileTrackingService"] = None,
    ):
        self._state_adapter = state_adapter
        self._uow_factory = uow_factory
        self._file_tracking = file_tracking_service
  
    async def arun(
        self, 
        execution_id: str, 
        graph: Optional[Any] = None
    ) -> Execution:
        """
        Run workflow asynchronously.
      
        Non-blocking execution that yields control to event loop
        during I/O operations (LLM calls, checkpoints, file I/O).
      
        CROSS-DB CONSISTENCY: After execution completes, a CHECKPOINT_VERIFY
        outbox event is created in the same transaction. The OutboxProcessor
        verifies LangGraph checkpoints match WTB execution records.
        """
        async with self._uow_factory() as uow:
            execution = await uow.executions.aget(execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
          
            # Set graph on adapter
            if graph and hasattr(self._state_adapter, 'set_workflow_graph'):
                self._state_adapter.set_workflow_graph(graph, force_recompile=True)
          
            # Initialize session
            initial_state = execution.state.workflow_variables.copy()
            session_id = await self._state_adapter.ainitialize_session(
                execution.id, 
                execution.state
            )
            execution.session_id = session_id
            execution.start()
          
            try:
                # Execute via async LangGraph
                final_state = await self._state_adapter.aexecute(initial_state)
              
                # Update execution with results
                execution.state.workflow_variables = final_state
              
                # Track output files asynchronously
                if self._file_tracking:
                    await self._track_output_files_async(execution, final_state)
              
                execution.complete()
              
            except Exception as e:
                logger.error(f"Async execution failed: {e}")
                execution.fail(str(e), execution.state.current_node_id)
          
            await uow.executions.aupdate(execution)
          
            # CROSS-DB CONSISTENCY: Add verification outbox event in SAME transaction
            # This ensures we can verify LangGraph checkpoints match WTB records
            if execution.status == ExecutionStatus.COMPLETED:
                from wtb.domain.models.outbox import OutboxEvent, OutboxEventType
                import hashlib
                import json
              
                # Hash final state for verification
                state_hash = hashlib.sha256(
                    json.dumps(final_state, sort_keys=True, default=str).encode()
                ).hexdigest()[:16]
              
                verification_event = OutboxEvent(
                    event_type=OutboxEventType.CHECKPOINT_VERIFY,
                    aggregate_type="Execution",
                    aggregate_id=execution_id,
                    payload={
                        "thread_id": session_id,
                        "execution_id": execution_id,
                        "expected_final_state_hash": state_hash,
                    }
                )
                await uow.outbox.aadd(verification_event)
          
            await uow.acommit()  # ATOMIC: Execution + Verification event
          
            return execution
  
    async def astream(
        self,
        execution_id: str,
        graph: Optional[Any] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream execution events asynchronously.
      
        Yields state updates in real-time without blocking.
        Ideal for WebSocket streaming to clients.
      
        ERROR HANDLING: If streaming fails midway, the execution is marked
        as FAILED (not left in RUNNING state forever).
        """
        async with self._uow_factory() as uow:
            execution = await uow.executions.aget(execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
          
            if graph:
                self._state_adapter.set_workflow_graph(graph, force_recompile=True)
          
            initial_state = execution.state.workflow_variables.copy()
            await self._state_adapter.ainitialize_session(execution.id, execution.state)
            execution.start()
            await uow.executions.aupdate(execution)
            await uow.acommit()
      
        # Stream execution events with proper error handling
        streaming_failed = False
        streaming_error: Optional[Exception] = None
      
        try:
            async for event in self._state_adapter.astream(initial_state):
                yield {
                    "execution_id": execution_id,
                    "event_type": "state_update",
                    "data": event,
                }
        except Exception as e:
            # Mark streaming as failed - will update execution status below
            streaming_failed = True
            streaming_error = e
            logger.error(f"Streaming failed for execution {execution_id}: {e}")
      
        # Final commit - update status based on streaming outcome
        async with self._uow_factory() as uow:
            execution = await uow.executions.aget(execution_id)
          
            if streaming_failed:
                # Mark execution as FAILED, not leave it in RUNNING state
                execution.fail(
                    str(streaming_error), 
                    execution.state.current_node_id
                )
            else:
                # Success path
                final_state = await self._state_adapter.aget_current_state()
                execution.state.workflow_variables = final_state
                execution.complete()
          
            await uow.executions.aupdate(execution)
            await uow.acommit()
      
        # Re-raise error after cleanup so caller knows streaming failed
        if streaming_failed and streaming_error:
            raise streaming_error
  
    async def apause(self, execution_id: str) -> Execution:
        """Pause execution asynchronously."""
        async with self._uow_factory() as uow:
            execution = await uow.executions.aget(execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
          
            # Create checkpoint before pause
            checkpoint_id = await self._state_adapter.asave_checkpoint(
                state=execution.state,
                node_id=execution.state.current_node_id or "unknown",
                trigger=CheckpointTrigger.USER_REQUEST,
                name="Manual Pause",
            )
          
            execution.pause()
            execution.checkpoint_id = checkpoint_id
            await uow.executions.aupdate(execution)
            await uow.acommit()
          
            return execution
  
    async def arollback(
        self, 
        execution_id: str, 
        checkpoint_id: str
    ) -> Execution:
        """Rollback to checkpoint asynchronously."""
        async with self._uow_factory() as uow:
            execution = await uow.executions.aget(execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
          
            # Restore state from checkpoint
            restored_state = await self._state_adapter.arollback(checkpoint_id)
          
            # Restore files asynchronously
            if self._file_tracking:
                await self._restore_files_async(execution, restored_state)
          
            execution.state = restored_state
            execution.status = ExecutionStatus.PAUSED
            execution.checkpoint_id = checkpoint_id
          
            await uow.executions.aupdate(execution)
            await uow.acommit()
          
            return execution
  
    async def _track_output_files_async(
        self, 
        execution: Execution, 
        final_state: Dict[str, Any]
    ) -> None:
        """Track output files asynchronously."""
        output_files = final_state.get("_output_files", {})
        if not output_files:
            return
      
        await self._file_tracking.atrack_files(
            file_paths=list(output_files.keys()),
            message=f"Execution {execution.id} outputs",
        )
  
    async def _restore_files_async(
        self, 
        execution: Execution, 
        restored_state: ExecutionState
    ) -> None:
        """Restore files from checkpoint asynchronously."""
        output_files = restored_state.workflow_variables.get("_output_files", {})
        if not output_files:
            return
      
        await self._file_tracking.arestore_files(
            checkpoint_id=execution.checkpoint_id,
            file_data=output_files,
        )
```

### 4.3 Infrastructure Layer (`wtb/infrastructure/`)

#### 4.3.1 Async SQLAlchemy Unit of Work

```python
# wtb/infrastructure/database/async_unit_of_work.py

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import Optional

from wtb.domain.interfaces.async_unit_of_work import IAsyncUnitOfWork


class AsyncSQLAlchemyUnitOfWork(IAsyncUnitOfWork):
    """
    Async SQLAlchemy Unit of Work implementation.
  
    Uses SQLAlchemy 2.0 async support with:
    - aiosqlite for SQLite
    - asyncpg for PostgreSQL
  
    ACID Compliance:
    - Atomicity: Session transaction
    - Consistency: ORM validation
    - Isolation: Session-level isolation
    - Durability: Async commit to disk
    """
  
    def __init__(self, db_url: str):
        # Convert sync URL to async URL
        if db_url.startswith("sqlite:///"):
            async_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif db_url.startswith("postgresql://"):
            async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = db_url
      
        self._engine = create_async_engine(async_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, 
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._session: Optional[AsyncSession] = None
  
    async def __aenter__(self) -> "AsyncSQLAlchemyUnitOfWork":
        self._session = self._session_factory()
        self._init_repositories()
        return self
  
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        End transaction with guaranteed session cleanup.
      
        IMPORTANT: Uses try/finally to ensure session.close() is always called,
        even if rollback() raises an exception.
        """
        try:
            if exc_type is not None:
                await self.arollback()
        finally:
            await self._session.close()  # Always cleanup, even if rollback fails
  
    async def acommit(self) -> None:
        await self._session.commit()
  
    async def arollback(self) -> None:
        await self._session.rollback()
  
    def _init_repositories(self):
        """Initialize async repositories with session."""
        from .async_repositories import (
            AsyncWorkflowRepository,
            AsyncExecutionRepository,
            AsyncOutboxRepository,
        )
        self.workflows = AsyncWorkflowRepository(self._session)
        self.executions = AsyncExecutionRepository(self._session)
        self.outbox = AsyncOutboxRepository(self._session)
```

#### 4.3.2 Async LangGraph State Adapter

```python
# wtb/infrastructure/adapters/async_langgraph_state_adapter.py

from typing import Optional, Dict, Any, List, AsyncIterator
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from wtb.domain.interfaces.async_state_adapter import IAsyncStateAdapter
from wtb.domain.models.workflow import ExecutionState


class AsyncLangGraphStateAdapter(IAsyncStateAdapter):
    """
    Async LangGraph State Adapter.
  
    Uses LangGraph's native async support:
    - AsyncSqliteSaver for checkpoints
    - ainvoke() for execution
    - astream() for streaming
  
    ACID via LangGraph:
    - Atomicity: Super-step checkpoints
    - Consistency: TypedDict state schema
    - Isolation: Thread-based (thread_id)
    - Durability: SQLite/PostgreSQL persistence
    """
  
    def __init__(self, checkpoint_db_path: str):
        self._checkpoint_db = checkpoint_db_path
        self._checkpointer: Optional[AsyncSqliteSaver] = None
        self._compiled_graph = None
        self._current_thread_id: Optional[str] = None
        self._pending_graph: Optional[Any] = None  # For lazy compilation
  
    async def _ensure_checkpointer(self):
        """Lazy initialize async checkpointer."""
        if self._checkpointer is None:
            self._checkpointer = AsyncSqliteSaver.from_conn_string(
                self._checkpoint_db
            )
  
    async def _ensure_compiled(self):
        """Ensure graph is compiled with checkpointer (called from async context)."""
        await self._ensure_checkpointer()
        if self._pending_graph is not None:
            self._compiled_graph = self._pending_graph.compile(
                checkpointer=self._checkpointer
            )
            self._pending_graph = None
  
    def set_workflow_graph(self, graph: Any, force_recompile: bool = False):
        """
        Set graph for lazy compilation.
      
        NOTE: Does NOT compile immediately. Compilation happens lazily in
        aexecute() or astream() when the async checkpointer is available.
        This avoids RuntimeError from calling run_until_complete() in async context.
        """
        if force_recompile:
            self._compiled_graph = None
        self._pending_graph = graph
  
    async def aset_workflow_graph(self, graph: Any, force_recompile: bool = False):
        """
        Async graph initialization - use this from async context.
      
        Preferred over set_workflow_graph() when already in async context.
        """
        if force_recompile:
            self._compiled_graph = None
        self._pending_graph = graph
        await self._ensure_compiled()
  
    async def ainitialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[str]:
        """Initialize session (thread_id) asynchronously."""
        await self._ensure_compiled()  # Lazy compile if graph is pending
        self._current_thread_id = f"wtb-{execution_id}"
        return self._current_thread_id
  
    async def aexecute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow asynchronously via LangGraph ainvoke()."""
        await self._ensure_compiled()  # Lazy compile if graph is pending
      
        if not self._compiled_graph:
            raise RuntimeError("Graph not set. Call set_workflow_graph() or aset_workflow_graph() first.")
      
        config = {"configurable": {"thread_id": self._current_thread_id}}
        result = await self._compiled_graph.ainvoke(initial_state, config)
        return result
  
    async def astream(
        self, 
        initial_state: Dict[str, Any],
        stream_mode: str = "updates"
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream execution events asynchronously."""
        if not self._compiled_graph:
            raise RuntimeError("Graph not set")
      
        config = {"configurable": {"thread_id": self._current_thread_id}}
        async for event in self._compiled_graph.astream(
            initial_state, 
            config, 
            stream_mode=stream_mode
        ):
            yield event
  
    async def asave_checkpoint(
        self,
        state: ExecutionState,
        node_id: str,
        trigger: "CheckpointTrigger",
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save checkpoint asynchronously."""
        if not self._compiled_graph:
            raise RuntimeError("Graph not set")
      
        config = {"configurable": {"thread_id": self._current_thread_id}}
      
        # Update state to trigger checkpoint
        await self._compiled_graph.aupdate_state(
            config,
            state.workflow_variables,
            as_node=node_id,
        )
      
        # Get latest checkpoint ID
        state_snapshot = await self._compiled_graph.aget_state(config)
        return state_snapshot.config["configurable"]["checkpoint_id"]
  
    async def arollback(self, to_checkpoint_id: str) -> ExecutionState:
        """Rollback to checkpoint asynchronously."""
        config = {
            "configurable": {
                "thread_id": self._current_thread_id,
                "checkpoint_id": to_checkpoint_id,
            }
        }
      
        state_snapshot = await self._compiled_graph.aget_state(config)
      
        return ExecutionState(
            current_node_id=list(state_snapshot.next)[0] if state_snapshot.next else None,
            workflow_variables=state_snapshot.values,
        )
```

#### 4.3.3 Async File Tracking Service

```python
# wtb/infrastructure/file_tracking/async_filetracker_service.py

import aiofiles
import aiofiles.os
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any

from wtb.domain.interfaces.file_tracking import IAsyncFileTrackingService


class AsyncFileTrackerService(IAsyncFileTrackingService):
    """
    Async File Tracking Service using Repository Pattern.
    
    ARCHITECTURE ALIGNMENT (FILE_TRACKING_ARCHITECTURE_DECISION.md):
    - Uses IAsyncBlobRepository for content storage
    - Uses IAsyncFileCommitRepository for commit management  
    - Uses IAsyncCheckpointFileLinkRepository for checkpoint links
    - All operations through UoW for ACID compliance
    
    Content-Addressable Storage:
    - SHA-256 hashing for deduplication (handled by BlobRepository)
    - Atomic transactions via UoW
    
    Orphan Handling:
    - If commit fails after blob write, orphaned blobs may exist
    - Use AsyncBlobOrphanCleaner for periodic cleanup
    """
    
    def __init__(
        self,
        uow_factory: "Callable[[], IAsyncUnitOfWork]",
    ):
        self._uow_factory = uow_factory
    
    async def _path_exists(self, path: Path) -> bool:
        """
        Check if path exists asynchronously.
        
        NOTE: aiofiles.os.path.exists() doesn't exist!
        Use aiofiles.os.stat() with try/except instead.
        """
        try:
            await aiofiles.os.stat(path)
            return True
        except FileNotFoundError:
            return False
    
    async def atrack_files(
        self,
        file_paths: List[str],
        message: str,
        checkpoint_id: Optional[str] = None,
    ) -> "FileTrackingResult":
        """
        Track files asynchronously with content-addressable storage.
        
        ACID Compliance:
        - All operations within single UoW transaction
        - Blob storage + commit + link atomically committed
        - Rollback on any failure
        """
        async with self._uow_factory() as uow:
            mementos = []
            total_size = 0
            
            for file_path in file_paths:
                path = Path(file_path)
                if not await self._path_exists(path):
                    continue
                
                # Read file content asynchronously
                async with aiofiles.open(path, 'rb') as f:
                    content = await f.read()
                
                # Save via repository (content-addressable)
                blob_id = await uow.blobs.asave(content)
                
                mementos.append(FileMemento(
                    path=str(path),
                    blob_hash=blob_id,
                    size_bytes=len(content),
                ))
                total_size += len(content)
            
            # Create commit with mementos
            commit = FileCommit.create(
                message=message,
                mementos=mementos,
            )
            await uow.file_commits.asave(commit)
            
            # Link to checkpoint if provided
            if checkpoint_id:
                link = CheckpointFileLink(
                    checkpoint_id=checkpoint_id,
                    commit_id=commit.id,
                )
                await uow.checkpoint_file_links.aadd(link)
            
            await uow.acommit()  # ATOMIC: blobs + commit + link
            
            return FileTrackingResult(
                commit_id=commit.id,
                files_tracked=len(mementos),
                total_size_bytes=total_size,
            )
    
    async def arestore_files(
        self,
        checkpoint_id: str,
        output_dir: Path,
    ) -> int:
        """
        Restore files from checkpoint asynchronously.
        
        Lookup flow:
        1. checkpoint_id → CheckpointFileLink → commit_id
        2. commit_id → FileCommit → mementos
        3. memento.blob_hash → BlobRepository → content
        4. Write content to output_dir
        """
        async with self._uow_factory() as uow:
            # Get commit via checkpoint link
            commit = await uow.file_commits.aget_by_checkpoint_id(checkpoint_id)
            if not commit:
                return 0
            
            restored_count = 0
            for memento in commit.mementos:
                # Restore via repository
                output_path = output_dir / Path(memento.path).name
                try:
                    await uow.blobs.arestore_to_file(
                        blob_id=memento.blob_hash,
                        output_path=output_path,
                    )
                    restored_count += 1
                except FileNotFoundError:
                    # Blob may have been orphaned/cleaned - log and continue
                    logger.warning(f"Blob not found: {memento.blob_hash}")
            
            return restored_count
    
    async def atrack_and_link(
        self,
        checkpoint_id: str,
        file_paths: List[str],
        message: str,
    ) -> "FileTrackingResult":
        """
        Convenience method: Track files and link to checkpoint in one call.
        
        Equivalent to atrack_files() with checkpoint_id parameter.
        """
        return await self.atrack_files(
            file_paths=file_paths,
            message=message,
            checkpoint_id=checkpoint_id,
        )
```

---

## 5. Integration Patterns

### 5.1 LangGraph Async Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      LANGGRAPH ASYNC INTEGRATION                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   LangGraph Native Async Methods:                                               │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                               │
│                                                                                  │
│   graph.ainvoke(state, config)     → Async full execution                       │
│   graph.astream(state, config)     → Async streaming                            │
│   graph.aget_state(config)         → Async state retrieval                      │
│   graph.aupdate_state(config, ...)  → Async state update                        │
│                                                                                  │
│   Checkpointer Selection:                                                       │
│   ━━━━━━━━━━━━━━━━━━━━━━━━                                                       │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                      ASYNC CHECKPOINTER OPTIONS                         │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                         │   │
│   │   SQLite:     AsyncSqliteSaver.from_conn_string(db_path)               │   │
│   │   PostgreSQL: AsyncPostgresSaver.from_conn_string(db_url)              │   │
│   │   Memory:     MemorySaver() (testing, not truly async)                 │   │
│   │                                                                         │   │
│   │   Recommendation: AsyncSqliteSaver for dev, AsyncPostgresSaver for prod│   │
│   │                                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│   Integration Pattern:                                                          │
│   ━━━━━━━━━━━━━━━━━━━━━                                                          │
│                                                                                  │
│   class AsyncLangGraphStateAdapter:                                             │
│       async def aexecute(self, state):                                          │
│           return await self._compiled_graph.ainvoke(                            │
│               state,                                                            │
│               {"configurable": {"thread_id": self._thread_id}}                  │
│           )                                                                      │
│                                                                                  │
│       async def astream(self, state):                                           │
│           async for event in self._compiled_graph.astream(                      │
│               state,                                                            │
│               {"configurable": {"thread_id": self._thread_id}},                 │
│               stream_mode="updates"                                             │
│           ):                                                                     │
│               yield event                                                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 File System Async Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FILE SYSTEM ASYNC INTEGRATION                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Library: aiofiles                                                             │
│   ━━━━━━━━━━━━━━━━━                                                             │
│                                                                                  │
│   import aiofiles                                                               │
│   import aiofiles.os                                                            │
│                                                                                  │
│   # Async file read                                                             │
│   async with aiofiles.open(path, 'rb') as f:                                    │
│       content = await f.read()                                                  │
│                                                                                  │
│   # Async file write                                                            │
│   async with aiofiles.open(path, 'wb') as f:                                    │
│       await f.write(content)                                                    │
│                                                                                  │
│   # Async directory operations                                                  │
│   await aiofiles.os.makedirs(path, exist_ok=True)                               │
│   exists = await aiofiles.os.path.exists(path)                                  │
│                                                                                  │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                                  │
│   File Tracking Flow (Async):                                                   │
│                                                                                  │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐   │
│   │ Node Output  │ ──▶ │ Async Read   │ ──▶ │ SHA-256 Hash │ ──▶ │ Async    │   │
│   │ _output_files│     │ aiofiles     │     │ (sync, fast) │     │ Blob     │   │
│   │              │     │              │     │              │     │ Write    │   │
│   └──────────────┘     └──────────────┘     └──────────────┘     └──────────┘   │
│                                                                                  │
│   Note: SHA-256 hashing is CPU-bound but fast (~100MB/s).                      │
│         Only file I/O is async.                                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Ray Async Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RAY ASYNC INTEGRATION                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Pattern: Ray handles parallelism, Async handles concurrency                   │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                    │
│                                                                                  │
│   Ray Architecture (unchanged):                                                 │
│   - ActorPool for parallel variant execution                                    │
│   - Each Actor has isolated UoW + StateAdapter                                  │
│   - ObjectRef tracking for cancellation                                         │
│                                                                                  │
│   Async Enhancement:                                                            │
│   - Actors can use async internally for I/O                                     │
│   - Main thread uses asyncio.to_thread() for ray.get()                         │
│   - Event bridge remains async                                                  │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                   ASYNC RAY BATCH RUNNER                                │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                         │   │
│   │   class AsyncRayBatchTestRunner:                                        │   │
│   │       async def arun_batch_test(self, batch_test):                      │   │
│   │           """Run batch test with async result collection."""            │   │
│   │                                                                         │   │
│   │           # Submit to Ray (sync API)                                    │   │
│   │           refs = [actor.execute_variant.remote(...) for ...]            │   │
│   │                                                                         │   │
│   │           # Collect results without blocking event loop                 │   │
│   │           while refs:                                                   │   │
│   │               # Use asyncio.to_thread to avoid blocking                 │   │
│   │               ready, refs = await asyncio.to_thread(                    │   │
│   │                   ray.wait, refs, num_returns=1, timeout=0.1            │   │
│   │               )                                                         │   │
│   │                                                                         │   │
│   │               for ref in ready:                                         │   │
│   │                   result = await asyncio.to_thread(ray.get, ref)        │   │
│   │                   yield result                                          │   │
│   │                                                                         │   │
│   │               # Yield control to event loop                             │   │
│   │               await asyncio.sleep(0)                                    │   │
│   │                                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│   Actor Internal Async (Optional Enhancement):                                  │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                   │
│                                                                                  │
│   @ray.remote                                                                   │
│   class AsyncVariantExecutionActor:                                             │
│       async def execute_variant(self, ...):                                     │
│           """Execute variant with internal async operations."""                 │
│           # Async execution via LangGraph                                       │
│           result = await self._state_adapter.aexecute(initial_state)            │
│                                                                                  │
│           # Async file tracking                                                 │
│           await self._file_tracking.atrack_files(...)                           │
│                                                                                  │
│           return result                                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Venv Manager Async Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     VENV MANAGER ASYNC INTEGRATION                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Status: Already Async ✅                                                      │
│   ━━━━━━━━━━━━━━━━━━━━━━━━                                                       │
│                                                                                  │
│   The UV Venv Manager already uses async interfaces:                            │
│                                                                                  │
│   class IVenvExecutor(ABC):                                                     │
│       async def init_project(self, env_id, python_version) -> VenvResult        │
│       async def add_packages(self, env_id, packages) -> VenvResult              │
│       async def sync_env(self, env_id) -> VenvResult                            │
│                                                                                  │
│   class EnvManager:                                                             │
│       async def create_env(self, env_id, python_version, packages)              │
│       async def delete_env(self, env_id)                                        │
│       async def cleanup_stale_envs(self, idle_hours)                            │
│                                                                                  │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                                  │
│   WTB Integration Pattern:                                                      │
│                                                                                  │
│   class AsyncExecutionController:                                               │
│       async def _ensure_node_environment(self, node_id, node_config):           │
│           """Ensure node has required environment before execution."""          │
│                                                                                  │
│           env_id = EnvManager.get_env_id(                                       │
│               workflow_id=self._workflow_id,                                    │
│               node_id=node_id,                                                  │
│           )                                                                      │
│                                                                                  │
│           # Check if environment exists                                         │
│           env_status = await self._env_manager.get_status(env_id)               │
│                                                                                  │
│           if env_status.status == "NOT_EXISTS":                                 │
│               # Create environment asynchronously                               │
│               await self._env_manager.create_env(                               │
│                   env_id=env_id,                                                │
│                   python_version=node_config.python_version,                    │
│                   packages=node_config.packages,                                │
│               )                                                                  │
│                                                                                  │
│           return env_id                                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Transaction Consistency

### 6.1 Async Outbox Pattern

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ASYNC OUTBOX PATTERN                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Problem: Cross-database consistency (WTB DB ↔ LangGraph DB ↔ FileTracker)    │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                                  │
│   Solution: Async Outbox Pattern with background processor                      │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                     ASYNC OUTBOX FLOW                                   │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                         │   │
│   │   1. Business Transaction (Async)                                       │   │
│   │   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                       │   │
│   │   async with uow:                                                       │   │
│   │       execution = Execution(...)                                        │   │
│   │       await uow.executions.aadd(execution)                              │   │
│   │                                                                         │   │
│   │       # Add outbox event in SAME transaction                            │   │
│   │       outbox_event = OutboxEvent(                                       │   │
│   │           event_type="CHECKPOINT_VERIFY",                               │   │
│   │           payload={"checkpoint_id": cp_id}                              │   │
│   │       )                                                                  │   │
│   │       await uow.outbox.aadd(outbox_event)                               │   │
│   │                                                                         │   │
│   │       await uow.acommit()  # ATOMIC: Both or neither                    │   │
│   │                                                                         │   │
│   │   2. Background Processor (Async)                                       │   │
│   │   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                       │   │
│   │   class AsyncOutboxProcessor:                                           │   │
│   │       async def aprocess_pending(self):                                 │   │
│   │           async with self._uow_factory() as uow:                        │   │
│   │               # FIFO ordering guaranteed by order_by="created_at"       │   │
│   │               events = await uow.outbox.aget_pending(                   │   │
│   │                   limit=100,                                            │   │
│   │                   order_by="created_at"  # IMPORTANT: FIFO ordering!    │   │
│   │               )                                                         │   │
│   │                                                                         │   │
│   │               for event in events:                                      │   │
│   │                   try:                                                   │   │
│   │                       await self._process_event(event)                  │   │
│   │                       event.status = "PROCESSED"                        │   │
│   │                   except Exception as e:                                │   │
│   │                       event.retry_count += 1                            │   │
│   │                       event.status = "FAILED" if retries > 5 else ...   │   │
│   │                                                                         │   │
│   │                   await uow.outbox.aupdate(event)                       │   │
│   │                                                                         │   │
│   │               await uow.acommit()                                       │   │
│   │                                                                         │   │
│   │       async def _process_event(self, event):                            │   │
│   │           if event.event_type == "CHECKPOINT_VERIFY":                   │   │
│   │               # Verify checkpoint exists in LangGraph DB                │   │
│   │               exists = await self._verify_checkpoint(...)               │   │
│   │               if not exists:                                            │   │
│   │                   raise ConsistencyError("Checkpoint not found")        │   │
│   │                                                                         │   │
│   │           elif event.event_type == "FILE_COMMIT_VERIFY":                │   │
│   │               # Verify file commit in FileTracker                       │   │
│   │               exists = await self._verify_file_commit(...)              │   │
│   │                                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Async Saga Pattern (Complex Transactions)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ASYNC SAGA PATTERN                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Use Case: Rollback with file restore across multiple systems                  │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                   │
│                                                                                  │
│   class AsyncRollbackSaga:                                                      │
│       """                                                                        │
│       Saga for coordinated rollback across:                                     │
│       1. WTB Execution State                                                    │
│       2. LangGraph Checkpoint State                                             │
│       3. FileTracker File State                                                 │
│                                                                                  │
│       Compensating actions on failure.                                          │
│       """                                                                        │
│                                                                                  │
│       async def aexecute(                                                       │
│           self,                                                                  │
│           execution_id: str,                                                    │
│           checkpoint_id: str,                                                   │
│       ) -> RollbackResult:                                                      │
│           steps_completed = []                                                  │
│                                                                                  │
│           try:                                                                   │
│               # Step 1: Restore LangGraph state                                 │
│               lg_state = await self._state_adapter.arollback(checkpoint_id)     │
│               steps_completed.append("langgraph_rollback")                      │
│                                                                                  │
│               # Step 2: Restore files from checkpoint                           │
│               files_restored = await self._file_tracking.arestore_files(        │
│                   checkpoint_id=checkpoint_id,                                  │
│                   output_dir=self._output_dir,                                  │
│               )                                                                  │
│               steps_completed.append("file_restore")                            │
│                                                                                  │
│               # Step 3: Update WTB execution record                             │
│               async with self._uow_factory() as uow:                            │
│                   execution = await uow.executions.aget(execution_id)           │
│                   execution.state = lg_state                                    │
│                   execution.checkpoint_id = checkpoint_id                       │
│                   execution.status = ExecutionStatus.PAUSED                     │
│                   await uow.executions.aupdate(execution)                       │
│                   await uow.acommit()                                           │
│               steps_completed.append("wtb_update")                              │
│                                                                                  │
│               return RollbackResult(success=True, files_restored=files_restored)│
│                                                                                  │
│           except Exception as e:                                                │
│               # Compensating transactions                                       │
│               await self._compensate(steps_completed, execution_id)             │
│               raise RollbackError(f"Rollback failed: {e}") from e               │
│                                                                                  │
│       async def _compensate(self, steps: List[str], execution_id: str):         │
│           """                                                                    │
│           Execute compensating actions in reverse order with error tracking.    │
│                                                                                  │
│           IMPORTANT: Continues executing remaining compensations even if one    │
│           fails. Collects all errors and raises CompensationError at end.       │
│           """                                                                    │
│           compensation_errors: List[Tuple[str, str]] = []                       │
│                                                                                  │
│           for step in reversed(steps):                                          │
│               try:                                                               │
│                   if step == "wtb_update":                                      │
│                       # Restore original execution state                        │
│                       await self._restore_execution_state(execution_id)         │
│                   elif step == "file_restore":                                  │
│                       # Delete restored files                                   │
│                       await self._cleanup_restored_files()                      │
│                   # langgraph_rollback: checkpoint history preserved, no action │
│               except Exception as e:                                            │
│                   # Log error but continue with remaining compensations         │
│                   compensation_errors.append((step, str(e)))                    │
│                   logger.error(f"Compensation failed for {step}: {e}")          │
│                                                                                  │
│           # Raise if any compensations failed                                   │
│           if compensation_errors:                                               │
│               raise CompensationError(                                          │
│                   f"Saga compensation partially failed: {compensation_errors}. "│
│                   f"Manual intervention may be required."                       │
│               )                                                                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Migration Strategy

### 7.1 Incremental Migration Approach

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      INCREMENTAL MIGRATION STRATEGY                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Principle: "Strangle Fig" Pattern                                             │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                              │
│   - New async code grows alongside sync code                                    │
│   - Gradual migration with feature flags                                        │
│   - No big-bang rewrite                                                         │
│                                                                                  │
│   Phase Timeline:                                                               │
│   ━━━━━━━━━━━━━━━━                                                               │
│                                                                                  │
│   Phase A (Week 1-2):  Async Interfaces & Dual Implementation                   │
│   Phase B (Week 3-4):  Async Infrastructure (DB, Files)                         │
│   Phase C (Week 5-6):  Async Application Services                               │
│   Phase D (Week 7-8):  Integration & Migration                                  │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                    MIGRATION TIMELINE                                   │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │                                                                         │   │
│   │   Week 1-2: PHASE A - Interfaces                                        │   │
│   │   ══════════════════════════════════════                                │   │
│   │   ├── Create IAsyncStateAdapter interface                               │   │
│   │   ├── Create IAsyncUnitOfWork interface                                 │   │
│   │   ├── Create IAsyncRepository interfaces                                │   │
│   │   └── Create IAsyncFileTrackingService interface                        │   │
│   │                                                                         │   │
│   │   Week 3-4: PHASE B - Infrastructure                                    │   │
│   │   ══════════════════════════════════════                                │   │
│   │   ├── Implement AsyncSQLAlchemyUnitOfWork                               │   │
│   │   ├── Implement AsyncLangGraphStateAdapter                              │   │
│   │   ├── Implement AsyncFileTrackerService                                 │   │
│   │   └── Add aiosqlite, asyncpg, aiofiles dependencies                     │   │
│   │                                                                         │   │
│   │   Week 5-6: PHASE C - Application                                       │   │
│   │   ══════════════════════════════════════                                │   │
│   │   ├── Implement AsyncExecutionController                                │   │
│   │   ├── Update API routes to use async controller                         │   │
│   │   ├── Add async streaming endpoint                                      │   │
│   │   └── Implement AsyncRayBatchTestRunner (optional)                      │   │
│   │                                                                         │   │
│   │   Week 7-8: PHASE D - Integration                                       │   │
│   │   ══════════════════════════════════════                                │   │
│   │   ├── Add feature flag for async mode                                   │   │
│   │   ├── Migration testing & benchmarks                                    │   │
│   │   ├── Documentation update                                              │   │
│   │   └── Deprecation warnings for sync APIs                                │   │
│   │                                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Backward Compatibility Pattern

```python
# wtb/application/services/execution_controller_compat.py

from typing import Union, Optional, Any
import asyncio


class ExecutionControllerCompat:
    """
    Compatibility wrapper providing both sync and async interfaces.
  
    Usage:
        # Sync (backward compatible - only outside async context!)
        result = controller.run(execution_id, graph)
      
        # Async (new, preferred)
        result = await controller.arun(execution_id, graph)
  
    IMPORTANT: Sync methods will raise RuntimeError if called from async context.
    This is intentional - calling sync wrappers from async code is a bug.
    """
  
    def __init__(
        self,
        async_controller: "AsyncExecutionController",
    ):
        self._async_controller = async_controller
  
    def _run_sync(self, coro):
        """
        Run coroutine synchronously - only works outside async context.
      
        Uses asyncio.run() (Python 3.7+) instead of deprecated
        get_event_loop().run_until_complete().
      
        Raises RuntimeError if called from within an async context.
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                "Cannot call sync method from async context. "
                "Use the async version (e.g., 'await arun()' instead of 'run()'). "
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # No running loop - safe to use asyncio.run()
                return asyncio.run(coro)
            raise  # Re-raise if it's our "Cannot call sync" error
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Sync Methods (Backward Compatible - Outside Async Context Only)
    # ═══════════════════════════════════════════════════════════════════════════
  
    def run(self, execution_id: str, graph: Optional[Any] = None) -> "Execution":
        """
        Sync execution (backward compatible).
      
        WARNING: Only works outside async context. Use arun() in async code.
      
        Raises:
            RuntimeError: If called from within async context
        """
        import warnings
        warnings.warn(
            "run() is deprecated, use 'await arun()' for async execution",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._run_sync(self._async_controller.arun(execution_id, graph))
  
    def pause(self, execution_id: str) -> "Execution":
        """Sync pause (backward compatible - outside async context only)."""
        return self._run_sync(self._async_controller.apause(execution_id))
  
    def rollback(self, execution_id: str, checkpoint_id: str) -> "Execution":
        """Sync rollback (backward compatible - outside async context only)."""
        return self._run_sync(
            self._async_controller.arollback(execution_id, checkpoint_id)
        )
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Async Methods (New)
    # ═══════════════════════════════════════════════════════════════════════════
  
    async def arun(self, execution_id: str, graph: Optional[Any] = None) -> "Execution":
        """Async execution (preferred)."""
        return await self._async_controller.arun(execution_id, graph)
  
    async def apause(self, execution_id: str) -> "Execution":
        """Async pause."""
        return await self._async_controller.apause(execution_id)
  
    async def arollback(self, execution_id: str, checkpoint_id: str) -> "Execution":
        """Async rollback."""
        return await self._async_controller.arollback(execution_id, checkpoint_id)
  
    async def astream(
        self, 
        execution_id: str, 
        graph: Optional[Any] = None
    ) -> "AsyncIterator[Dict[str, Any]]":
        """Async streaming (new capability)."""
        async for event in self._async_controller.astream(execution_id, graph):
            yield event
```

---

## 8. SOLID & ACID Compliance

### 8.1 SOLID Compliance Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SOLID COMPLIANCE (ASYNC ARCHITECTURE)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   S - Single Responsibility                                                     │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━                                                    │
│   ✅ AsyncExecutionController: Orchestration only                               │
│   ✅ AsyncLangGraphStateAdapter: LangGraph interaction only                     │
│   ✅ AsyncFileTrackerService: File tracking only                                │
│   ✅ AsyncOutboxProcessor: Event processing only                                │
│                                                                                  │
│   O - Open/Closed                                                               │
│   ━━━━━━━━━━━━━━━━━                                                              │
│   ✅ IAsyncStateAdapter: Extend via new implementations                         │
│   ✅ IAsyncUnitOfWork: New DB backends without core changes                     │
│   ✅ IAsyncFileTrackingService: New storage backends                            │
│                                                                                  │
│   L - Liskov Substitution                                                       │
│   ━━━━━━━━━━━━━━━━━━━━━━━                                                        │
│   ✅ All async adapters are interchangeable                                     │
│   ✅ AsyncSQLiteUoW ↔ AsyncPostgresUoW                                          │
│   ✅ AsyncLangGraphAdapter ↔ AsyncInMemoryAdapter                               │
│                                                                                  │
│   I - Interface Segregation (ISP)                                              │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                                │
│   ✅ IAsyncReadRepository vs IAsyncWriteRepository (separated read/write)       │
│   ✅ IStateAdapter (sync) vs IAsyncStateAdapter (async) - SEPARATE interfaces   │
│   ✅ IAsyncUnitOfWork (4 methods: __aenter__, __aexit__, acommit, arollback)    │
│   ✅ No dual sync+async in single interface (violates ISP)                     │
│                                                                                  │
│   D - Dependency Inversion                                                      │
│   ━━━━━━━━━━━━━━━━━━━━━━━━                                                       │
│   ✅ Application layer depends on IAsync* interfaces                            │
│   ✅ Infrastructure implements interfaces                                       │
│   ✅ No direct dependency on SQLAlchemy/LangGraph in application                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 ACID Compliance Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ACID COMPLIANCE (ASYNC ARCHITECTURE)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   A - Atomicity                                                                 │
│   ━━━━━━━━━━━━━━━                                                                │
│   ✅ Async UoW: All changes committed or rolled back together                   │
│   ✅ Outbox Pattern: Business data + event in same transaction                  │
│   ✅ Saga Pattern: Compensating transactions on failure                         │
│                                                                                  │
│   Implementation:                                                               │
│   async with uow:                                                               │
│       await uow.executions.aadd(execution)                                      │
│       await uow.outbox.aadd(outbox_event)                                       │
│       await uow.acommit()  # Both succeed or both fail                          │
│                                                                                  │
│   C - Consistency                                                               │
│   ━━━━━━━━━━━━━━━━━                                                              │
│   ✅ Pydantic/TypedDict validation at boundaries                                │
│   ✅ Domain model invariants enforced                                           │
│   ✅ Outbox processor ensures cross-DB consistency                              │
│   ✅ CHECKPOINT_VERIFY events verify LangGraph ↔ WTB alignment                 │
│                                                                                  │
│   I - Isolation                                                                 │
│   ━━━━━━━━━━━━━━━                                                                │
│   ✅ Session-level isolation (each execution has unique thread_id)              │
│   ✅ Ray Actor isolation (each actor has own UoW)                               │
│   ✅ Workspace isolation (parallel variants)                                    │
│                                                                                  │
│   Implementation:                                                               │
│   - LangGraph: thread_id = f"wtb-{execution_id}"                               │
│   - Ray: Each actor creates isolated UoW via factory                            │
│   - Workspace: Copy-on-write directory per variant                              │
│                                                                                  │
│   D - Durability                                                                │
│   ━━━━━━━━━━━━━━━                                                                │
│   ✅ SQLite/PostgreSQL for WTB data                                             │
│   ✅ LangGraph checkpointer for state                                           │
│   ✅ Content-addressable storage for files                                      │
│                                                                                  │
│   Persistence Points:                                                           │
│   1. await uow.acommit()           → WTB DB                                     │
│   2. LangGraph super-step          → Checkpoint DB                              │
│   3. File tracking commit          → Blob storage + FileTracker DB              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Best Practices & Additional Patterns

#### 8.3.1 Connection Pool Management

```python
# wtb/infrastructure/database/async_unit_of_work.py

from typing import ClassVar, Dict
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class AsyncSQLAlchemyUnitOfWork(IAsyncUnitOfWork):
    """
    Async UoW with connection pool caching.
  
    IMPORTANT: Reuses engines across UoW instances for efficiency.
    Connection pools are expensive to create.
    """
  
    # Class-level engine cache - shared across all instances
    _engine_pool: ClassVar[Dict[str, AsyncEngine]] = {}
  
    @classmethod
    async def get_engine(cls, db_url: str) -> AsyncEngine:
        """
        Get or create async engine with connection pooling.
      
        Pool Configuration:
        - pool_size=5: Base connections
        - max_overflow=10: Additional connections under load
        - pool_recycle=3600: Recycle connections hourly (prevent stale)
        """
        if db_url not in cls._engine_pool:
            cls._engine_pool[db_url] = create_async_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                echo=False,
            )
        return cls._engine_pool[db_url]
  
    @classmethod
    async def close_all_engines(cls):
        """Close all cached engines - call on shutdown."""
        for engine in cls._engine_pool.values():
            await engine.dispose()
        cls._engine_pool.clear()
```

#### 8.3.2 Async Health Checks

```python
# wtb/infrastructure/health/async_health.py

from dataclasses import dataclass
from typing import Dict


@dataclass
class HealthStatus:
    healthy: bool
    checks: Dict[str, bool]
    details: Dict[str, str]


async def check_async_health() -> HealthStatus:
    """
    Verify all async dependencies are working.
  
    Call this on startup and expose via /health endpoint.
    """
    checks = {}
    details = {}
  
    # Test aiosqlite
    try:
        import aiosqlite
        async with aiosqlite.connect(":memory:") as db:
            await db.execute("SELECT 1")
        checks["aiosqlite"] = True
    except Exception as e:
        checks["aiosqlite"] = False
        details["aiosqlite"] = str(e)
  
    # Test aiofiles
    try:
        import aiofiles
        import tempfile
        async with aiofiles.tempfile.NamedTemporaryFile(delete=True) as f:
            await f.write(b"test")
        checks["aiofiles"] = True
    except Exception as e:
        checks["aiofiles"] = False
        details["aiofiles"] = str(e)
  
    # Test LangGraph async checkpointer
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        checkpointer = AsyncSqliteSaver.from_conn_string(":memory:")
        # Just verify import and instantiation work
        checks["langgraph_async"] = True
    except Exception as e:
        checks["langgraph_async"] = False
        details["langgraph_async"] = str(e)
  
    return HealthStatus(
        healthy=all(checks.values()),
        checks=checks,
        details=details,
    )
```

#### 8.3.3 Structured Logging for Async Operations

```python
# wtb/infrastructure/logging/async_logger.py

import structlog
from functools import wraps
from typing import Callable, Any

logger = structlog.get_logger()


def log_async_operation(operation_name: str):
    """
    Decorator for logging async operations with structured context.
  
    Usage:
        @log_async_operation("arun")
        async def arun(self, execution_id: str, ...) -> Execution:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Extract execution_id from kwargs or args
            execution_id = kwargs.get("execution_id") or (
                args[1] if len(args) > 1 else "unknown"
            )
          
            logger.info(
                f"async_{operation_name}_started",
                execution_id=execution_id,
                operation=operation_name,
            )
          
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    f"async_{operation_name}_completed",
                    execution_id=execution_id,
                    operation=operation_name,
                )
                return result
            except Exception as e:
                logger.error(
                    f"async_{operation_name}_failed",
                    execution_id=execution_id,
                    operation=operation_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
      
        return wrapper
    return decorator


# Usage in AsyncExecutionController:
class AsyncExecutionController:
    @log_async_operation("execution")
    async def arun(self, execution_id: str, graph: Optional[Any] = None) -> Execution:
        # ... implementation ...
        pass
```

#### 8.3.4 Type Hints with AsyncContextManager

```python
# wtb/domain/interfaces/async_unit_of_work.py

from typing import AsyncContextManager, TypeVar
from contextlib import asynccontextmanager

T = TypeVar("T", bound="IAsyncUnitOfWork")


def get_async_uow(db_url: str) -> AsyncContextManager[IAsyncUnitOfWork]:
    """
    Factory function returning typed async context manager.
  
    Usage:
        async with get_async_uow("sqlite:///wtb.db") as uow:
            workflow = await uow.workflows.aget(workflow_id)
    """
    return AsyncSQLAlchemyUnitOfWork(db_url)


# Alternative: asynccontextmanager decorator
@asynccontextmanager
async def managed_uow(db_url: str):
    """
    Async context manager for UoW with guaranteed cleanup.
    """
    uow = AsyncSQLAlchemyUnitOfWork(db_url)
    async with uow:
        yield uow
```

#### 8.3.5 Async Blob Orphan Cleanup

```python
# wtb/infrastructure/file_tracking/async_orphan_cleaner.py

from pathlib import Path
from typing import List, Callable, Set
import aiofiles.os
import logging

from wtb.domain.interfaces.async_unit_of_work import IAsyncUnitOfWork

logger = logging.getLogger(__name__)


class AsyncBlobOrphanCleaner:
    """
    Async orphan blob detection and cleanup.
    
    BACKGROUND (from FILE_TRACKING_ARCHITECTURE_DECISION.md Section 4.3):
    
    Two-Phase Write Pattern creates potential orphans:
    1. Blob written to filesystem (success)
    2. DB commit fails → orphaned blob remains
    
    This cleaner runs periodically or on startup to:
    1. Scan all blob files on filesystem
    2. Query DB for known blob hashes
    3. Delete files not in DB (orphans)
    
    SAFETY:
    - Always run with dry_run=True first
    - Log all deletions
    - Consider grace period for in-flight transactions
    """
    
    def __init__(
        self,
        blobs_dir: Path,
        uow_factory: Callable[[], IAsyncUnitOfWork],
        grace_period_minutes: int = 10,
    ):
        self._blobs_dir = blobs_dir
        self._uow_factory = uow_factory
        self._grace_period_minutes = grace_period_minutes
    
    async def aclean_orphans(self, dry_run: bool = True) -> List[str]:
        """
        Find and optionally delete orphaned blob files.
        
        Args:
            dry_run: If True, only report orphans without deleting
        
        Returns:
            List of orphaned blob file paths
        """
        orphans = []
        
        # Get all blobs from filesystem
        fs_blobs = await self._list_blob_files_async()
        logger.info(f"Found {len(fs_blobs)} blob files on filesystem")
        
        # Get all known blobs from DB
        async with self._uow_factory() as uow:
            known_hashes: Set[str] = set(await uow.blobs.alist_all_hashes())
        logger.info(f"Found {len(known_hashes)} blob hashes in database")
        
        # Find orphans (on filesystem but not in DB)
        for blob_path in fs_blobs:
            blob_hash = self._extract_hash(blob_path)
            if blob_hash not in known_hashes:
                # Check grace period (skip recently created files)
                if await self._is_within_grace_period(blob_path):
                    logger.debug(f"Skipping recent blob: {blob_hash}")
                    continue
                
                orphans.append(str(blob_path))
                if not dry_run:
                    await aiofiles.os.remove(blob_path)
                    logger.info(f"Deleted orphan blob: {blob_hash}")
        
        logger.info(
            f"Found {len(orphans)} orphaned blobs "
            f"({'DRY RUN - not deleted' if dry_run else 'DELETED'})"
        )
        return orphans
    
    async def _list_blob_files_async(self) -> List[Path]:
        """List all blob files in storage directory."""
        blobs = []
        if not self._blobs_dir.exists():
            return blobs
        
        # Blob storage uses sharding: blobs_dir/ab/cdef123...
        for prefix_dir in self._blobs_dir.iterdir():
            if prefix_dir.is_dir() and len(prefix_dir.name) == 2:
                for blob_file in prefix_dir.iterdir():
                    if blob_file.is_file():
                        blobs.append(blob_file)
        return blobs
    
    def _extract_hash(self, blob_path: Path) -> str:
        """Extract blob hash from path: prefix_dir/rest → prefix + rest."""
        return blob_path.parent.name + blob_path.name
    
    async def _is_within_grace_period(self, blob_path: Path) -> bool:
        """Check if blob was created within grace period."""
        import time
        stat = await aiofiles.os.stat(blob_path)
        age_minutes = (time.time() - stat.st_ctime) / 60
        return age_minutes < self._grace_period_minutes


# Usage example:
async def cleanup_orphaned_blobs():
    """Run orphan cleanup - call on startup or via scheduled job."""
    cleaner = AsyncBlobOrphanCleaner(
        blobs_dir=Path("./data/blobs/objects"),
        uow_factory=lambda: AsyncSQLAlchemyUnitOfWork("sqlite:///wtb.db"),
        grace_period_minutes=10,  # Don't delete blobs < 10 min old
    )
    
    # Always dry run first
    orphans = await cleaner.aclean_orphans(dry_run=True)
    print(f"Would delete {len(orphans)} orphaned blobs")
    
    # Actual cleanup (uncomment when ready)
    # await cleaner.aclean_orphans(dry_run=False)
```

---

## 9. Implementation Roadmap

### 9.1 Task Breakdown

| Phase       | Task                                           | Priority | Effort | Dependencies |
| ----------- | ---------------------------------------------- | -------- | ------ | ------------ |
| **A** | Create `IAsyncStateAdapter` interface        | P0       | 2h     | None         |
| **A** | Create `IAsyncUnitOfWork` interface          | P0       | 2h     | None         |
| **A** | Create `IAsyncRepository` interfaces         | P0       | 2h     | None         |
| **A** | Create `IAsyncFileTrackingService` interface | P0       | 1h     | None         |
| **B** | Implement `AsyncSQLAlchemyUnitOfWork`        | P0       | 4h     | Phase A      |
| **B** | Implement `AsyncLangGraphStateAdapter`       | P0       | 6h     | Phase A      |
| **B** | Implement `AsyncFileTrackerService`          | P1       | 4h     | Phase A      |
| **B** | Add async dependencies (aiosqlite, aiofiles)   | P0       | 1h     | None         |
| **C** | Implement `AsyncExecutionController`         | P0       | 6h     | Phase B      |
| **C** | Update API routes for async streaming          | P1       | 4h     | Phase C      |
| **C** | Implement `ExecutionControllerCompat`        | P1       | 2h     | Phase C      |
| **C** | Implement `AsyncOutboxProcessor`             | P1       | 4h     | Phase B      |
| **D** | Add feature flag for async mode                | P1       | 2h     | Phase C      |
| **D** | Integration tests for async flow               | P0       | 8h     | Phase C      |
| **D** | Performance benchmarks                         | P1       | 4h     | Phase D      |
| **D** | Documentation update                           | P1       | 4h     | Phase D      |

### 9.2 Dependencies to Add

```toml
# pyproject.toml additions

[project]
dependencies = [
    # ... existing deps ...
  
    # Async SQLAlchemy - REQUIRED
    "aiosqlite>=0.19.0",       # SQLite async driver (development)
  
    # Async File I/O - REQUIRED
    "aiofiles>=23.2.1",        # Async file operations
  
    # LangGraph Async Checkpointer - REQUIRED
    "langgraph-checkpoint-sqlite>=1.0.0",  # Includes AsyncSqliteSaver
]

[project.optional-dependencies]
# PostgreSQL is REQUIRED for production deployment
production = [
    "asyncpg>=0.29.0",         # PostgreSQL async driver
    "langgraph-checkpoint-postgres>=1.0.0",  # PostgreSQL checkpointer
]

# All dependencies for development
dev = [
    "aiosqlite>=0.19.0",
    "asyncpg>=0.29.0",  
    "aiofiles>=23.2.1",
    "langgraph-checkpoint-sqlite>=1.0.0",
    "langgraph-checkpoint-postgres>=1.0.0",
]
```

> **Note:** For production deployment, install with: `pip install wtb[production]`

### 9.3 File Structure (New Files)

```
wtb/
├── domain/
│   └── interfaces/
│       ├── async_state_adapter.py       # NEW: IAsyncStateAdapter
│       ├── async_unit_of_work.py        # NEW: IAsyncUnitOfWork
│       ├── async_repositories.py        # NEW: IAsyncRepository
│       └── async_file_tracking.py       # NEW: IAsyncFileTrackingService
│
├── application/
│   └── services/
│       ├── async_execution_controller.py    # NEW: AsyncExecutionController
│       ├── execution_controller_compat.py   # NEW: Compatibility wrapper
│       └── async_batch_runner.py            # NEW: AsyncRayBatchTestRunner
│
└── infrastructure/
    ├── adapters/
    │   └── async_langgraph_state_adapter.py # NEW: AsyncLangGraphStateAdapter
    │
    ├── database/
    │   ├── async_unit_of_work.py            # NEW: AsyncSQLAlchemyUnitOfWork
    │   └── async_repositories/              # NEW: Async repository impls
    │       ├── __init__.py
    │       ├── async_execution_repository.py
    │       └── async_workflow_repository.py
    │
    ├── file_tracking/
    │   └── async_filetracker_service.py     # NEW: AsyncFileTrackerService
    │
    └── outbox/
        └── async_processor.py               # NEW: AsyncOutboxProcessor
```

---

## 10. Appendix: Code Examples

### 10.1 Complete Async Execution Flow

```python
# Example: Full async workflow execution

import asyncio
from wtb.application.services.async_execution_controller import AsyncExecutionController
from wtb.infrastructure.adapters.async_langgraph_state_adapter import AsyncLangGraphStateAdapter
from wtb.infrastructure.database.async_unit_of_work import AsyncSQLAlchemyUnitOfWork
from wtb.infrastructure.file_tracking.async_filetracker_service import AsyncFileTrackerService


async def run_workflow_async():
    """Example of full async workflow execution."""
  
    # Initialize async components
    state_adapter = AsyncLangGraphStateAdapter(
        checkpoint_db_path="./data/checkpoints.db"
    )
  
    file_tracking = AsyncFileTrackerService(
        base_dir=Path("./data/filetrack"),
        uow_factory=lambda: AsyncSQLAlchemyUnitOfWork("sqlite:///./data/wtb.db"),
    )
  
    controller = AsyncExecutionController(
        state_adapter=state_adapter,
        uow_factory=lambda: AsyncSQLAlchemyUnitOfWork("sqlite:///./data/wtb.db"),
        file_tracking_service=file_tracking,
    )
  
    # Create execution
    async with AsyncSQLAlchemyUnitOfWork("sqlite:///./data/wtb.db") as uow:
        workflow = await uow.workflows.aget("my-workflow-id")
        execution = Execution(workflow_id=workflow.id)
        await uow.executions.aadd(execution)
        await uow.acommit()
        execution_id = execution.id
  
    # Run execution asynchronously (non-blocking!)
    result = await controller.arun(execution_id, graph=my_langgraph)
  
    print(f"Execution completed: {result.status}")
    print(f"Final state: {result.state.workflow_variables}")
  
    return result


async def stream_workflow_async():
    """Example of streaming execution events."""
  
    # ... initialize controller ...
  
    # Stream execution events (real-time, non-blocking)
    async for event in controller.astream(execution_id, graph=my_langgraph):
        print(f"Event: {event['event_type']}")
        print(f"Data: {event['data']}")
      
        # Send to WebSocket clients
        await websocket_manager.broadcast(event)


# Run examples
if __name__ == "__main__":
    asyncio.run(run_workflow_async())
```

### 10.2 API Route with Async Streaming

```python
# wtb/api/rest/routes/executions.py (updated)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


@router.post("/{execution_id}/run/stream")
async def stream_execution(
    execution_id: str,
    controller: AsyncExecutionController = Depends(get_async_controller),
):
    """
    Stream execution events via Server-Sent Events.
  
    Non-blocking endpoint that streams state updates in real-time.
    """
    async def event_generator():
        async for event in controller.astream(execution_id):
            yield f"data: {json.dumps(event)}\n\n"
  
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/{execution_id}/ws")
async def websocket_execution(
    websocket: WebSocket,
    execution_id: str,
    controller: AsyncExecutionController = Depends(get_async_controller),
):
    """
    WebSocket endpoint for real-time execution updates.
    """
    await websocket.accept()
  
    try:
        async for event in controller.astream(execution_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
```

---

## References

| Document                                                                       | Description               |
| ------------------------------------------------------------------------------ | ------------------------- |
| [ARCHITECTURE_STRUCTURE.md](./ARCHITECTURE_STRUCTURE.md)                          | Current architecture      |
| [PROGRESS_TRACKER.md](./PROGRESS_TRACKER.md)                                      | Implementation status     |
| [WTB_ARCHITECTURE_DIAGRAMS.md](../WTB_ARCHITECTURE_DIAGRAMS.md)                   | Visual diagrams           |
| [LangGraph Async Docs](https://langchain-ai.github.io/langgraph/)                 | LangGraph async reference |
| [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) | SQLAlchemy 2.0 async      |

---

## Appendix: Code Review Summary (v1.1)

### Issues Fixed

| Issue                                                 | Status   | Fix Applied                                                                  |
| ----------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| **P0: aiofiles.os.path.exists() doesn't exist** | ✅ Fixed | Use `_path_exists()` helper with `aiofiles.os.stat()`                    |
| **P0: run_until_complete() in async context**   | ✅ Fixed | Lazy graph compilation in `_ensure_compiled()` + `aset_workflow_graph()` |
| **P0: __aexit__ missing try/finally**     | ✅ Fixed | Wrapped rollback in try/finally for guaranteed cleanup                       |
| **P1: Streaming error leaves RUNNING state**    | ✅ Fixed | Added try/except with status update in `astream()`                         |
| **P1: Cross-DB checkpoint verification**        | ✅ Fixed | Added `CHECKPOINT_VERIFY` outbox event in `arun()`                       |
| **P1: Saga compensation error handling**        | ✅ Fixed | Track and raise `CompensationError` for partial failures                   |
| **P2: Dual interface violates ISP**             | ✅ Fixed | Separate `IStateAdapter` (sync) and `IAsyncStateAdapter` (async)         |
| **P2: Outbox event ordering**                   | ✅ Fixed | Added `order_by="created_at"` for FIFO guarantee                           |
| **P3: asyncpg for production**                  | ✅ Fixed | Added `[production]` optional dependency group                             |

### Suggestions Implemented

| Suggestion                     | Status   | Implementation                                            |
| ------------------------------ | -------- | --------------------------------------------------------- |
| Connection pool management     | ✅ Added | `AsyncSQLAlchemyUnitOfWork._engine_pool` class variable |
| Async health checks            | ✅ Added | `check_async_health()` function in Section 8.3.2        |
| Structured logging             | ✅ Added | `@log_async_operation` decorator in Section 8.3.3       |
| AsyncContextManager type hints | ✅ Added | `get_async_uow()` factory in Section 8.3.4              |

### SOLID Compliance (Post-Review)

| Principle             | Status  | Notes                                          |
| --------------------- | ------- | ---------------------------------------------- |
| Single Responsibility | ✅ PASS | Clear separation maintained                    |
| Open/Closed           | ✅ PASS | Extensions via interfaces                      |
| Liskov Substitution   | ✅ PASS | Separate sync/async interfaces                 |
| Interface Segregation | ✅ PASS | **Fixed:** No dual sync+async interfaces |
| Dependency Inversion  | ✅ PASS | Application depends on abstractions            |

### ACID Compliance (Post-Review)

| Property    | Status  | Notes                                               |
| ----------- | ------- | --------------------------------------------------- |
| Atomicity   | ✅ PASS | Async UoW + Outbox pattern                          |
| Consistency | ✅ PASS | **Enhanced:** CHECKPOINT_VERIFY outbox events |
| Isolation   | ✅ PASS | Thread-based + Actor isolation                      |
| Durability  | ✅ PASS | SQLite/PostgreSQL persistence                       |

---

*Document Version: 1.1*
*Created: 2026-01-27*
*Last Updated: 2026-01-27 (Code Review)*
*Author: WTB Architecture Team*

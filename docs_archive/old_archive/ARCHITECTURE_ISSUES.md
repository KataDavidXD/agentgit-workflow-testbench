# WTB Architecture Issues Analysis

**Last Updated:** 2026-01-27  
**Status:** ✅ Phase 1 COMPLETED (v1.7)  
**Decision:** Remove AgentGit Implementation, Preserve Session Domain Concept

---

## Executive Summary

**Key Insight:** Session is a **Domain Concept** (scope/context of workflow execution), not just an AgentGit artifact. We preserved the concept while swapping the implementation.

| Concept | Action | Status |
|---------|--------|--------|
| **Session** (Domain) | KEEP - maps to LangGraph `thread_id` | ✅ DONE |
| **AgentGit** (Implementation) | DELETE - replaced by LangGraph | ✅ DONE |
| `initialize_session()` | REFACTOR - returns `str` (thread_id) | ✅ DONE |
| `agentgit_session_id` | RENAME → `session_id` (str) | ✅ DONE |

---

## Issue Summary Matrix

### Resolved Issues (v1.6)

| ID | Title | Resolution |
|----|-------|------------|
| ISS-001 | ID Type Mismatch (int vs str) | ✅ Unified to `str` (UUID) |
| ISS-003 | IStateAdapter ISP Violation | ✅ Refactored interface, removed AgentGit methods |
| ISS-004 | AgentGit Bridge Memory Leak | ✅ Deleted AgentGit bridge |
| ISS-005 | Checkpoint ID Mapping | ✅ Deleted mapping (str IDs native) |
| ARC-001 | Messy Abstraction Hierarchy | ✅ Cleaned IStateAdapter, SDK layer separation |

### Resolved Issues (v1.7)

| ID | Title | Resolution |
|----|-------|------------|
| ARC-002 | Batch vs Non-Batch Execution Divergence | ✅ ExecutionControllerFactory with ACID isolation |
| ISS-006 | Outbox Processor Lifecycle | ✅ OutboxLifecycleManager with auto-start, health, graceful shutdown |
| TODO-011 | UoW Lifecycle in Factories | ✅ ManagedController with proper context management |
| TODO-008 | RayBatchTestRunner ACID isolation | ✅ Implemented via per-actor UoW + ExecutionController |
| TODO-010 | Move _project_to_workflow to ProjectService | ✅ Implemented WorkflowConversionService |

### Remaining Issues

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| TODO-012 | Implement gRPC API | P3 | Planned - Phase 2 |

---

## §1. ARC-001: Messy Abstraction Hierarchy - ✅ RESOLVED

**Status:** Resolved in v1.6

### Resolution Summary

| Change | Before | After |
|--------|--------|-------|
| `IStateAdapter` | 20+ methods (AgentGit-polluted) | ~15 methods (clean, focused) |
| ID Types | Mixed `int` and `str` | All `str` (UUIDs) |
| `initialize_session()` | Returns `int` | Returns `str` (thread_id) |
| SDK layer | Had `state_adapter` dependency | Uses only Application services |
| `branch()` method | BROKEN (metadata not persisted) | DELETED |
| `fork()` method | In SDK (broke encapsulation) | Moved to `ExecutionController` |

### Final Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         v1.6 CLEAN ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   SDK Layer (WTBTestBench)                                                   │
│   ├── Uses Application Services only                                         │
│   ├── NO state_adapter dependency (layer separation)                         │
│   ├── fork() delegates to ExecutionController.fork()                         │
│   └── branch() REMOVED (was broken)                                          │
│                                                                              │
│   Application Layer                                                          │
│   │                                                                          │
│   ├── ExecutionController                                                    │
│   │   ├── Uses IStateAdapter (cleaned, str IDs)                              │
│   │   ├── fork() method (moved from SDK)                                     │
│   │   └── session_id preserved as Domain concept                             │
│   │                                                                          │
│   └── WTBTestBenchFactory (Composition Root)                                 │
│       └── Wires all dependencies                                             │
│                                                                              │
│   Infrastructure Layer                                                       │
│   │                                                                          │
│   ├── LangGraphStateAdapter (PRIMARY)                                        │
│   │   └── All str IDs native (no mapping)                                    │
│   │                                                                          │
│   ├── InMemoryStateAdapter (Testing)                                         │
│   │   └── All str IDs                                                        │
│   │                                                                          │
│   └── AgentGitStateAdapter (DELETED)                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## §2. ARC-002: Batch vs Non-Batch Execution Divergence - ✅ RESOLVED (v1.7)

**Priority:** P0 (Blocker)  
**Status:** ✅ RESOLVED in v1.7  
**Verdict:** Fixed with ExecutionControllerFactory + ManagedController

### Problem (Before v1.7)

| Runner | Uses ExecutionController | Actually Executes |
|--------|-------------------------|-------------------|
| SDK.run() | Yes | Yes |
| ThreadPoolBatchTestRunner | **NO** | **NO (placeholder!)** |
| RayBatchTestRunner | Yes (internal creation) | Yes |

### Solution Implemented (v1.7)

**ManagedController Pattern:** Each thread gets its own isolated controller + UoW.

```python
# v1.7 SOLUTION: ExecutionControllerFactory with ManagedController

@dataclass
class ManagedController:
    """Controller with managed UoW lifecycle."""
    controller: ExecutionController
    uow: IUnitOfWork
    
    def __enter__(self) -> "ManagedController":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.uow.commit()
        else:
            self.uow.rollback()
        self.uow.__exit__(exc_type, exc_val, exc_tb)

class ExecutionControllerFactory:
    def create_isolated(self) -> ManagedController:
        """Create isolated controller with its own UoW."""
        uow = UnitOfWorkFactory.create(...)
        uow.__enter__()
        controller = ExecutionController(...)
        return ManagedController(controller=controller, uow=uow)
    
    @classmethod
    def get_factory_callable(cls, config) -> Callable[[], ManagedController]:
        """Get factory callable for batch runners."""
        factory = cls(config)
        return factory.create_isolated

# ThreadPoolBatchTestRunner now uses this:
class ThreadPoolBatchTestRunner:
    def __init__(self, controller_factory: Callable[[], ManagedController]):
        self._controller_factory = controller_factory
    
    def _execute_variant(self, ...):
        with self._controller_factory() as managed:
            result = managed.controller.run(execution_id, graph)
        # UoW automatically closed and committed/rolled back
```

### Result (After v1.7)

| Runner | Uses ExecutionController | ACID Compliant |
|--------|-------------------------|----------------|
| SDK.run() | ✅ Yes | ✅ Yes |
| ThreadPoolBatchTestRunner | ✅ Yes (via factory) | ✅ Yes (isolated UoW) |
| RayBatchTestRunner | ✅ Yes (via Actor) | ✅ Yes (Actor isolation) |

---

## §3. ISS-006: Outbox Processor Lifecycle - ✅ RESOLVED (v1.7)

**Priority:** P2  
**Status:** ✅ RESOLVED in v1.7  
**Solution:** OutboxLifecycleManager

### Implementation (v1.7)

Created `OutboxLifecycleManager` in `wtb/infrastructure/outbox/lifecycle.py`:

```python
from wtb.infrastructure.outbox import OutboxLifecycleManager, create_managed_processor

# Auto-start with signal handling
manager = create_managed_processor(
    wtb_db_url="sqlite:///data/wtb.db",
    auto_start=True,
    register_signals=True,  # SIGTERM/SIGINT handlers
)

# Health endpoint
health = manager.get_health()
# Returns: {"status": "healthy", "events_processed": 100, ...}

# Graceful shutdown (automatic on SIGTERM)
manager.shutdown()

# Or use as context manager
with OutboxLifecycleManager(wtb_db_url="...") as manager:
    # Processor running
    pass
# Processor stopped
```

### Features

| Feature | Implementation |
|---------|----------------|
| Auto-start | `auto_start=True` on init |
| Health endpoint | `get_health()` returns `HealthStatus` |
| Graceful shutdown | `register_signals=True` + `atexit` hooks |
| Callbacks | `on_start`, `on_stop`, `on_error` |
| Context manager | `__enter__` / `__exit__` protocol |

---

## Completed Cleanup (v1.6)

### Files DELETED (AgentGit Implementation)

| Component | Action | Notes |
|-----------|--------|-------|
| `AgentGitStateAdapter` | ✅ DELETED | Implementation removal |
| AgentGit bridge in `WTBEventBus` | N/A | Not needed |
| ID mapping logic | ✅ DELETED | `_checkpoint_id_map`, `_numeric_to_lg_id` removed |
| `WTBTestBench.branch()` | ✅ DELETED | Broken, duplicate of `fork()` |
| `BranchResult` class | ✅ DELETED | Not needed |
| `IStateAdapter.create_branch()` | ✅ DELETED | AgentGit session concept |
| `IStateAdapter.link_file_commit()` | ✅ DELETED | AgentGit-specific |
| `IStateAdapter` tool-level methods | ✅ DELETED | Not needed for LangGraph |

### Files REFACTORED (Preserved Domain Concepts)

| Component | Change | Status |
|-----------|--------|--------|
| `IStateAdapter` | Removed AgentGit methods, kept session concept | ✅ DONE |
| `IStateAdapter.initialize_session()` | Returns `str` (thread_id) instead of `int` | ✅ DONE |
| `LangGraphStateAdapter` | Removed ID mapping, uses str native | ✅ DONE |
| `InMemoryStateAdapter` | Updated to use str IDs | ✅ DONE |
| `Execution.agentgit_session_id` | RENAMED → `session_id: str` | ✅ DONE |
| `Execution.agentgit_checkpoint_id` | RENAMED → `checkpoint_id: str` | ✅ DONE |
| `ExecutionController` | Updated to use str IDs, added fork() | ✅ DONE |
| `WTBTestBench` | Removed state_adapter, fork() delegates to controller | ✅ DONE |

---

## Design Principles Compliance (Post-v1.6)

### SOLID Analysis

| Principle | Status | Notes |
|-----------|--------|-------|
| **S**ingle Responsibility | ✅ | IStateAdapter focused, SDK uses only App services |
| **O**pen/Closed | ✅ | New adapters via IStateAdapter implementations |
| **L**iskov Substitution | ✅ | Unified str IDs, any adapter works |
| **I**nterface Segregation | ✅ | IStateAdapter cleaned (~15 methods) |
| **D**ependency Inversion | ✅ | SDK uses only Application services |

### ACID Compliance

| Property | Status | Notes |
|----------|--------|-------|
| **A**tomicity | ✅ | UoW pattern |
| **C**onsistency | ✅ | Unified str types |
| **I**solation | ✅ | ManagedController (Threads) & Actor Isolation (Ray) |
| **D**urability | ✅ | SQLite/PostgreSQL |

---

## Session Concept Clarification (Final)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SESSION AS DOMAIN CONCEPT                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   What is a Session?                                                         │
│   ├── Logical container for workflow execution state                        │
│   ├── Scope/context that groups checkpoints together                        │
│   └── Persistent handle to resume execution                                 │
│                                                                              │
│   Implementation (v1.6):                                                     │
│   ├── session_id = thread_id = "wtb-{execution_id}"                         │
│   ├── All IDs are strings (UUIDs)                                           │
│   └── Maps 1:1 to LangGraph thread_id                                       │
│                                                                              │
│   Session Lifecycle:                                                         │
│   1. initialize_session(execution_id) → session_id (str)                    │
│   2. save_checkpoint(state) → checkpoint_id (str UUID)                      │
│   3. load_checkpoint(checkpoint_id) → ExecutionState                        │
│   4. rollback(checkpoint_id) → ExecutionState                               │
│   5. fork(checkpoint_id) → new Execution with new session                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Version Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| **v1.6** | Phase 0: Domain Cleanup | ✅ COMPLETED |
| **v1.7** | Phase 1: Unify Batch Execution, ISS-006 | ✅ COMPLETED |
| v1.8 | Phase 2: gRPC API, Final Polish | Planned |

---

## Related Documents

| Document | Description |
|----------|-------------|
| [INDEX.md](./INDEX.md) | Documentation hub |
| [PROGRESS_TRACKER.md](./PROGRESS_TRACKER.md) | Implementation progress |
| [ARCHITECTURE_STRUCTURE.md](./ARCHITECTURE_STRUCTURE.md) | Codebase structure |

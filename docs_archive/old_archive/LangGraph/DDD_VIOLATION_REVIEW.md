# DDD Violation Review & Fix Plan

**Date:** 2026-01-15  
**Status:** ✅ RESOLVED (Implemented 2026-01-15)

---

## Executive Summary

This document reviews DDD violations across the WTB codebase and documentation, providing a fix plan to align with the domain-centric checkpoint design.

**All violations have been resolved as of 2026-01-15.**

---

## Violations Found (ALL FIXED ✅)

### 1. IStateAdapter Has Infrastructure Concerns in Domain ✅ FIXED

**Location:** `wtb/domain/interfaces/state_adapter.py`

**Violations (RESOLVED):**

| Issue | Was | Now |
|-------|-----|-----|
| `checkpoint_id: int` | AgentGit integer ID | `CheckpointId` value object (string) |
| `session_id: int` | AgentGit session concept | `execution_id: str` (domain concept) |
| `tool_track_position: int` | AgentGit-specific | Removed |
| `CheckpointTrigger` enum | Tool-specific triggers | Removed (LangGraph auto-checkpoints) |
| Business logic in interface | Methods like `get_node_rollback_targets()` | Moved to `ExecutionHistory` domain model |

**Resolution:** Split into:
- `ICheckpointStore` (infrastructure) - persistence only ✅
- `ExecutionHistory` (domain) - business logic ✅

---

### 2. NodeBoundary Has Stale Concepts ✅ FIXED

**Location:** `wtb/domain/models/node_boundary.py`

**Violations (RESOLVED):**

| Field | Was | Now |
|-------|-----|-----|
| `internal_session_id: int` | AgentGit concept | Removed, uses `execution_id` |
| `entry_checkpoint_id: int` | Integer ID | `CheckpointId` (string) |
| `exit_checkpoint_id: int` | Integer ID | `CheckpointId` (string) |
| `tool_count: int` | Not applicable to LangGraph | Removed |
| `checkpoint_count: int` | Not applicable to LangGraph | Removed |

**Resolution:** Updated model to use domain value objects ✅

---

### 3. CheckpointEvents Leak Implementation Details ✅ FIXED

**Location:** `wtb/domain/events/checkpoint_events.py`

**Violations (RESOLVED):**

| Field | Was | Now |
|-------|-------|-----|
| `checkpoint_id: int` | Implementation type | `CheckpointId` value object |
| `session_id: int` | AgentGit concept | `execution_id: str` |
| `tool_track_position: int` | LangGraph doesn't have | Remove |

---

### 4. Missing Domain Models ✅ FIXED

**All models now exist:**

| Model | Purpose | Status |
|-------|---------|--------|
| `Checkpoint` | Domain representation of checkpoint | ✅ Created |
| `CheckpointId` | Value object for ID | ✅ Created |
| `ExecutionHistory` | Aggregate for checkpoint operations | ✅ Created |

**Location:** `wtb/domain/models/checkpoint.py`

---

### 5. Documentation Conflicts ✅ FIXED

**All conflicts resolved:**

| Document | Now Says | Status |
|----------|----------|--------|
| `DATABASE_DESIGN.md` | "All checkpoints atomic at node (super-step) level" | ✅ Correct |
| `state_adapter.py` | Deprecated, replaced by `ICheckpointStore` | ✅ Fixed |
| `node_boundary.py` | Uses CheckpointId (string), no tool references | ✅ Fixed |
| `WORKFLOW_TEST_BENCH_ARCHITECTURE.md` | References updated | ✅ Fixed |
| `WTB_INTEGRATION.md` | Uses LangGraph super-step model | ✅ Correct |

---

## Fix Plan

### Phase 1: Domain Models (P0)

Create missing domain models:

```python
# wtb/domain/models/checkpoint.py (NEW)

@dataclass(frozen=True)
class CheckpointId:
    """Value object for checkpoint identifier."""
    value: str

@dataclass(frozen=True)
class Checkpoint:
    """Domain entity for state checkpoint."""
    id: CheckpointId
    execution_id: str
    step: int
    node_writes: Dict[str, Any]
    next_nodes: List[str]
    state_values: Dict[str, Any]
    created_at: datetime

@dataclass
class ExecutionHistory:
    """Aggregate root for checkpoint management."""
    execution_id: str
    checkpoints: List[Checkpoint]
    
    def get_node_boundary(self, node_id: str) -> NodeBoundary: ...
    def get_rollback_target(self, node_id: str) -> Optional[Checkpoint]: ...
    def get_execution_path(self) -> List[str]: ...
```

### Phase 2: Update Existing Models (P0)

**`wtb/domain/models/node_boundary.py`:**

```diff
- internal_session_id: int = 0
- entry_checkpoint_id: Optional[int] = None
- exit_checkpoint_id: Optional[int] = None
- tool_count: int = 0
- checkpoint_count: int = 0
+ entry_checkpoint_id: Optional[CheckpointId] = None
+ exit_checkpoint_id: Optional[CheckpointId] = None
```

**`wtb/domain/events/checkpoint_events.py`:**

```diff
- checkpoint_id: int = 0
- session_id: int = 0
- tool_track_position: int = 0
+ checkpoint_id: CheckpointId = None
+ execution_id: str = ""
```

### Phase 3: Refactor IStateAdapter (P0)

Split into two interfaces:

```python
# wtb/domain/interfaces/checkpoint_store.py (NEW - Infrastructure Interface)
class ICheckpointStore(ABC):
    """Infrastructure interface - persistence only."""
    
    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None: ...
    
    @abstractmethod
    def load(self, checkpoint_id: CheckpointId) -> Optional[Checkpoint]: ...
    
    @abstractmethod
    def load_history(self, execution_id: str) -> ExecutionHistory: ...


# wtb/domain/interfaces/execution_service.py (Application Service)
class IExecutionService(ABC):
    """Application service using domain concepts."""
    
    @abstractmethod
    def get_history(self, execution_id: str) -> ExecutionHistory: ...
    
    @abstractmethod
    def rollback_to_node(self, execution_id: str, node_id: str) -> Checkpoint: ...
```

### Phase 4: Update Documentation (P1)

**Files to update:**

| File | Changes |
|------|---------|
| `DATABASE_DESIGN.md` | Remove `internal_session_id`, `tool_count` from schema |
| `WORKFLOW_TEST_BENCH_ARCHITECTURE.md` | Remove tool/message level references |
| `AGENTGIT_STATE_ADAPTER_DESIGN.md` | Mark as DEPRECATED (already DEFERRED) |
| `WTB_PERSISTENCE_DESIGN.md` | Update to reference ICheckpointStore |
| `state_adapter.py` docstrings | Update to node-level model |
| `node_boundary.py` docstrings | Remove tool/message level references |

---

## Updated Architecture

### Before (DDD Violations)

```
┌─────────────────────────────────────────────────────────────────┐
│  Domain Layer (ANEMIC)                                          │
│  • IStateAdapter - mixed business logic + persistence          │
│  • NodeBoundary - has AgentGit concepts (session_id)           │
│  • No Checkpoint domain model                                   │
│  • Events leak implementation (tool_track_position)            │
└─────────────────────────────────────────────────────────────────┘
```

### After (DDD Compliant)

```
┌─────────────────────────────────────────────────────────────────┐
│  Domain Layer (RICH)                                            │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Value Objects:                                             │ │
│  │ • CheckpointId - identifier                               │ │
│  │ • Checkpoint - state snapshot                             │ │
│  │                                                           │ │
│  │ Entities:                                                 │ │
│  │ • NodeBoundary - uses CheckpointId, no session_id        │ │
│  │                                                           │ │
│  │ Aggregate Roots:                                          │ │
│  │ • ExecutionHistory - business logic for checkpoints       │ │
│  │                                                           │ │
│  │ Domain Events:                                            │ │
│  │ • CheckpointCreated - uses CheckpointId                  │ │
│  │ • RollbackCompleted - uses CheckpointId                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Application Layer                                               │
│  • ExecutionService - orchestrates domain operations            │
│                                                                  │
│  Infrastructure Layer                                            │
│  • ICheckpointStore - persistence interface                     │
│  • LangGraphCheckpointStore - LangGraph implementation          │
│  • InMemoryCheckpointStore - testing implementation             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Schema Updates Required

### wtb_node_boundaries

```sql
-- BEFORE (with DDD violations)
CREATE TABLE wtb_node_boundaries (
    id INTEGER PRIMARY KEY,
    execution_id TEXT NOT NULL,
    internal_session_id INTEGER NOT NULL,     -- ❌ AgentGit concept
    node_id TEXT NOT NULL,
    entry_checkpoint_id INTEGER,               -- ❌ Wrong type
    exit_checkpoint_id INTEGER,                -- ❌ Wrong type
    node_status TEXT NOT NULL,
    tool_count INTEGER DEFAULT 0,              -- ❌ Not applicable
    checkpoint_count INTEGER DEFAULT 0,        -- ❌ Not applicable
    ...
);

-- AFTER (DDD compliant)
CREATE TABLE wtb_node_boundaries (
    id INTEGER PRIMARY KEY,
    execution_id TEXT NOT NULL,                -- ✅ Domain concept
    node_id TEXT NOT NULL,
    entry_checkpoint_id TEXT,                  -- ✅ LangGraph string ID
    exit_checkpoint_id TEXT,                   -- ✅ LangGraph string ID
    node_status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER,
    error_message TEXT,
    UNIQUE(execution_id, node_id)
);
```

---

## Implementation Priority

| Priority | Task | Files |
|----------|------|-------|
| **P0** | Create domain models | `wtb/domain/models/checkpoint.py` |
| **P0** | Update NodeBoundary | `wtb/domain/models/node_boundary.py` |
| **P0** | Update events | `wtb/domain/events/checkpoint_events.py` |
| **P0** | Create ICheckpointStore | `wtb/domain/interfaces/checkpoint_store.py` |
| **P1** | Deprecate IStateAdapter | `wtb/domain/interfaces/state_adapter.py` |
| **P1** | Update DATABASE_DESIGN.md | `docs/Project_Init/DATABASE_DESIGN.md` |
| **P1** | Update ARCHITECTURE docs | Multiple files |
| **P2** | Implement LangGraphCheckpointStore | `wtb/infrastructure/stores/` |
| **P2** | Migration script | Database migration |

---

## Summary

### DDD Violations to Fix

| Category | Count | Priority |
|----------|-------|----------|
| Missing domain models | 3 | P0 |
| Wrong types in domain | 6 | P0 |
| Business logic in wrong layer | 4 | P0 |
| Infrastructure concepts in domain | 3 | P0 |
| Outdated documentation | 5 | P1 |

### Key Principles

1. **Domain models own business logic** - `ExecutionHistory`, not adapter
2. **Value objects for identifiers** - `CheckpointId`, not `int`
3. **No infrastructure in domain** - No `session_id`, `tool_track_position`
4. **Adapters only map** - No computation, just persistence

# Domain Checkpoint Design

**Date:** 2026-01-15  
**Status:** ✅ IMPLEMENTED  
**Origin:** Colleague Review - "Checkpoint knowledge should be in domain, not adapter"

---

## Executive Summary

This document refactors checkpoint concepts from the infrastructure layer (LangGraphStateAdapter) to the domain layer, following DDD principles.

### Key Principle

> **"The domain should express business concepts. Checkpoint, Rollback, and ExecutionHistory are domain concepts - adapters only handle persistence mechanics."**

---

## Before vs After

### Before (Anemic Domain)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           ANEMIC DOMAIN (WRONG)                                │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Domain Layer                           Infrastructure Layer                   │
│  ═════════════                          ════════════════════                   │
│                                                                                │
│  IStateAdapter:                         LangGraphStateAdapter:                 │
│  • execute()                            • StateSnapshot knowledge              │
│  • rollback(checkpoint_id)              • checkpoint_id logic                  │
│  • get_history()                        • Node boundary computation            │
│                                         • Rollback to node logic               │
│                                                                                │
│  ExecutionState:                        ❌ PROBLEM:                            │
│  • current_node                         Business logic in infrastructure!      │
│  • variables                            Domain doesn't understand checkpoints  │
│  • (no checkpoint concept)                                                     │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

### After (Rich Domain)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           RICH DOMAIN (CORRECT)                                │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Domain Layer                           Infrastructure Layer                   │
│  ═════════════                          ════════════════════                   │
│                                                                                │
│  DOMAIN CONCEPTS:                       LangGraphCheckpointStore:              │
│  ┌─────────────────────┐                • Persistence only                     │
│  │ Checkpoint          │                • Maps domain Checkpoint ↔ LangGraph   │
│  │ • id: CheckpointId  │                • No business logic                    │
│  │ • step: int         │                                                       │
│  │ • node_writes: dict │                                                       │
│  │ • state: dict       │                                                       │
│  │ • created_at: dt    │                                                       │
│  └─────────────────────┘                                                       │
│                                                                                │
│  ┌─────────────────────┐                                                       │
│  │ ExecutionHistory    │                                                       │
│  │ • checkpoints: []   │                                                       │
│  │ • get_by_node()     │                                                       │
│  │ • rollback_target() │  ← Business logic in DOMAIN                          │
│  └─────────────────────┘                                                       │
│                                                                                │
│  ┌─────────────────────┐                                                       │
│  │ NodeBoundary        │                                                       │
│  │ • entry_checkpoint  │                                                       │
│  │ • exit_checkpoint   │                                                       │
│  │ • compute_from()    │  ← Business logic in DOMAIN                          │
│  └─────────────────────┘                                                       │
│                                                                                │
│  ICheckpointStore:                                                             │
│  • save(checkpoint)     → Pure persistence interface                          │
│  • load(checkpoint_id)                                                         │
│  • list(execution_id)                                                          │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Domain Model

### Value Objects

```python
# wtb/domain/models/checkpoint.py

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass(frozen=True)
class CheckpointId:
    """
    Value object for checkpoint identifier.
    
    Immutable, comparable, can be used as dict key.
    """
    value: str
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True)
class Checkpoint:
    """
    Domain entity representing a point-in-time state snapshot.
    
    This is a DOMAIN concept - how checkpoints are stored (LangGraph, 
    AgentGit, etc.) is an infrastructure concern.
    """
    id: CheckpointId
    execution_id: str
    step: int                              # Monotonic step number
    node_writes: Dict[str, Any]            # Which node wrote to this checkpoint
    next_nodes: List[str]                  # Nodes to execute next
    state_values: Dict[str, Any]           # State at this checkpoint
    created_at: datetime
    
    @property
    def completed_node(self) -> Optional[str]:
        """Get the node that completed at this checkpoint (if any)."""
        if self.node_writes:
            return list(self.node_writes.keys())[0]
        return None
    
    @property
    def is_terminal(self) -> bool:
        """Is this a terminal checkpoint (no next nodes)?"""
        return len(self.next_nodes) == 0
    
    def has_node_in_next(self, node_id: str) -> bool:
        """Check if node is about to execute."""
        return node_id in self.next_nodes
    
    def has_node_in_writes(self, node_id: str) -> bool:
        """Check if node completed at this checkpoint."""
        return node_id in self.node_writes


@dataclass
class NodeBoundary:
    """
    Domain entity representing a node's execution boundary.
    
    Computed FROM checkpoints, not stored separately.
    """
    node_id: str
    entry_checkpoint: Optional[Checkpoint]   # Where node appears in next
    exit_checkpoint: Optional[Checkpoint]    # Where node appears in writes
    status: str                              # "pending", "running", "completed", "failed"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration if completed."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None
    
    @classmethod
    def compute_from_checkpoints(
        cls, 
        node_id: str, 
        checkpoints: List[Checkpoint]
    ) -> "NodeBoundary":
        """
        DOMAIN LOGIC: Compute node boundary from checkpoint history.
        
        This logic belongs in the DOMAIN, not in an adapter.
        """
        entry_cp = None
        exit_cp = None
        status = "pending"
        
        for cp in checkpoints:
            # Entry: node appears in next (about to execute)
            if entry_cp is None and cp.has_node_in_next(node_id):
                entry_cp = cp
                status = "running"
            
            # Exit: node appears in writes (completed)
            if cp.has_node_in_writes(node_id):
                exit_cp = cp
                status = "completed"
                break
        
        return cls(
            node_id=node_id,
            entry_checkpoint=entry_cp,
            exit_checkpoint=exit_cp,
            status=status,
            started_at=entry_cp.created_at if entry_cp else None,
            completed_at=exit_cp.created_at if exit_cp else None,
        )
```

### Aggregate Root: ExecutionHistory

```python
# wtb/domain/models/execution_history.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Iterator
from .checkpoint import Checkpoint, CheckpointId, NodeBoundary


@dataclass
class ExecutionHistory:
    """
    Aggregate root for checkpoint management.
    
    Contains all DOMAIN LOGIC for:
    - Querying checkpoints
    - Computing node boundaries  
    - Finding rollback targets
    - Linearizing execution path
    
    This is the "Checkpoint knowledge" that belongs in the domain.
    """
    execution_id: str
    checkpoints: List[Checkpoint] = field(default_factory=list)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Query Operations (Domain Logic)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_checkpoint(self, checkpoint_id: CheckpointId) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        for cp in self.checkpoints:
            if cp.id == checkpoint_id:
                return cp
        return None
    
    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get most recent checkpoint."""
        if not self.checkpoints:
            return None
        return max(self.checkpoints, key=lambda cp: cp.step)
    
    def get_checkpoint_for_node(self, node_id: str) -> Optional[Checkpoint]:
        """Get checkpoint where node completed (exit checkpoint)."""
        for cp in reversed(self.checkpoints):  # Most recent first
            if cp.has_node_in_writes(node_id):
                return cp
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Node Boundary Operations (Domain Logic)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_node_boundary(self, node_id: str) -> NodeBoundary:
        """
        Compute node boundary from checkpoints.
        
        DOMAIN LOGIC: How to derive entry/exit from checkpoint sequence.
        """
        return NodeBoundary.compute_from_checkpoints(
            node_id, 
            sorted(self.checkpoints, key=lambda cp: cp.step)
        )
    
    def get_all_node_boundaries(self) -> List[NodeBoundary]:
        """Get boundaries for all executed nodes."""
        # Collect all unique nodes from checkpoint history
        nodes = set()
        for cp in self.checkpoints:
            nodes.update(cp.next_nodes)
            nodes.update(cp.node_writes.keys())
        
        # Remove special nodes
        nodes.discard("__start__")
        nodes.discard("__end__")
        
        return [self.get_node_boundary(node_id) for node_id in nodes]
    
    def get_completed_nodes(self) -> List[str]:
        """Get list of completed node IDs in execution order."""
        completed = []
        for cp in sorted(self.checkpoints, key=lambda cp: cp.step):
            if cp.completed_node and cp.completed_node not in completed:
                completed.append(cp.completed_node)
        return completed
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Rollback Operations (Domain Logic)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_rollback_target(self, to_node_id: str) -> Optional[Checkpoint]:
        """
        Get checkpoint to rollback to for resuming after a node.
        
        DOMAIN LOGIC: Rollback target is the checkpoint where node completed.
        """
        return self.get_checkpoint_for_node(to_node_id)
    
    def get_rollback_targets(self) -> List[Checkpoint]:
        """
        Get all valid rollback targets (completed node exit checkpoints).
        
        DOMAIN LOGIC: Only checkpoints with node_writes are rollback targets.
        """
        targets = []
        for cp in self.checkpoints:
            if cp.node_writes:  # Has completed node
                targets.append(cp)
        return sorted(targets, key=lambda cp: cp.step, reverse=True)
    
    def can_rollback_to(self, checkpoint_id: CheckpointId) -> bool:
        """Check if rollback to checkpoint is valid."""
        cp = self.get_checkpoint(checkpoint_id)
        return cp is not None and cp.node_writes  # Must be a node completion
    
    # ═══════════════════════════════════════════════════════════════════════════
    # History Operations (Domain Logic)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_execution_path(self) -> List[str]:
        """
        Get linearized execution path (node sequence).
        
        DOMAIN LOGIC: Derive execution sequence from checkpoint history.
        """
        path = []
        for cp in sorted(self.checkpoints, key=lambda cp: cp.step):
            if cp.completed_node:
                path.append(cp.completed_node)
        return path
    
    def __iter__(self) -> Iterator[Checkpoint]:
        """Iterate checkpoints in order."""
        return iter(sorted(self.checkpoints, key=lambda cp: cp.step))
    
    def __len__(self) -> int:
        return len(self.checkpoints)
```

### Domain Events

```python
# wtb/domain/events/checkpoint_events.py

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List
from ..models.checkpoint import CheckpointId


@dataclass(frozen=True)
class CheckpointCreated:
    """Domain event: checkpoint was created."""
    execution_id: str
    checkpoint_id: CheckpointId
    step: int
    node_writes: Dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)  
class RollbackRequested:
    """Domain event: rollback was requested."""
    execution_id: str
    target_checkpoint_id: CheckpointId
    target_node_id: str
    requested_at: datetime


@dataclass(frozen=True)
class RollbackCompleted:
    """Domain event: rollback completed successfully."""
    execution_id: str
    from_checkpoint_id: CheckpointId
    to_checkpoint_id: CheckpointId
    rolled_back_nodes: List[str]
    completed_at: datetime


@dataclass(frozen=True)
class NodeBoundaryRecorded:
    """Domain event: node execution boundary was recorded."""
    execution_id: str
    node_id: str
    entry_checkpoint_id: CheckpointId
    exit_checkpoint_id: CheckpointId
    duration_ms: int
```

---

## Infrastructure: Checkpoint Store

The infrastructure layer is now **persistence only** - no business logic:

```python
# wtb/infrastructure/stores/checkpoint_store.py

from abc import ABC, abstractmethod
from typing import List, Optional

from wtb.domain.models.checkpoint import Checkpoint, CheckpointId
from wtb.domain.models.execution_history import ExecutionHistory


class ICheckpointStore(ABC):
    """
    Infrastructure interface for checkpoint persistence.
    
    NO BUSINESS LOGIC HERE - only save/load/list operations.
    All checkpoint reasoning is in the domain (ExecutionHistory).
    """
    
    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint."""
        pass
    
    @abstractmethod
    def load(self, checkpoint_id: CheckpointId) -> Optional[Checkpoint]:
        """Load a checkpoint by ID."""
        pass
    
    @abstractmethod
    def load_history(self, execution_id: str) -> ExecutionHistory:
        """Load all checkpoints for an execution as ExecutionHistory."""
        pass
    
    @abstractmethod
    def delete(self, checkpoint_id: CheckpointId) -> bool:
        """Delete a checkpoint."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# LangGraph Implementation
# ═══════════════════════════════════════════════════════════════════════════════

class LangGraphCheckpointStore(ICheckpointStore):
    """
    LangGraph implementation of checkpoint store.
    
    ONLY handles persistence - maps domain Checkpoint ↔ LangGraph StateSnapshot.
    """
    
    def __init__(self, graph, checkpointer):
        self._graph = graph
        self._checkpointer = checkpointer
    
    def save(self, checkpoint: Checkpoint) -> None:
        """
        Save is implicit in LangGraph - happens during graph.invoke().
        This method is for explicit saves via graph.update_state().
        """
        config = {"configurable": {"thread_id": f"wtb-{checkpoint.execution_id}"}}
        self._graph.update_state(config, checkpoint.state_values)
    
    def load(self, checkpoint_id: CheckpointId) -> Optional[Checkpoint]:
        """Load checkpoint by ID."""
        # Find the checkpoint in history
        # (LangGraph doesn't have direct ID lookup, need to scan history)
        # This is an infrastructure detail hidden from domain
        pass
    
    def load_history(self, execution_id: str) -> ExecutionHistory:
        """
        Load LangGraph history and convert to domain ExecutionHistory.
        
        This is the MAPPING between LangGraph and domain concepts.
        """
        config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
        
        checkpoints = []
        for snapshot in self._graph.get_state_history(config):
            # Map LangGraph StateSnapshot → Domain Checkpoint
            checkpoint = self._to_domain_checkpoint(snapshot, execution_id)
            checkpoints.append(checkpoint)
        
        return ExecutionHistory(
            execution_id=execution_id,
            checkpoints=checkpoints
        )
    
    def _to_domain_checkpoint(self, snapshot, execution_id: str) -> Checkpoint:
        """
        Map LangGraph StateSnapshot to domain Checkpoint.
        
        This mapping is the ONLY place LangGraph-specific knowledge exists.
        """
        return Checkpoint(
            id=CheckpointId(snapshot.config["configurable"]["checkpoint_id"]),
            execution_id=execution_id,
            step=snapshot.metadata.get("step", 0),
            node_writes=snapshot.metadata.get("writes", {}),
            next_nodes=list(snapshot.next) if snapshot.next else [],
            state_values=snapshot.values,
            created_at=snapshot.created_at,
        )
    
    def delete(self, checkpoint_id: CheckpointId) -> bool:
        """LangGraph doesn't support deletion - return False."""
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# In-Memory Implementation (for testing)
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryCheckpointStore(ICheckpointStore):
    """In-memory checkpoint store for testing."""
    
    def __init__(self):
        self._checkpoints: Dict[str, List[Checkpoint]] = {}  # execution_id -> checkpoints
    
    def save(self, checkpoint: Checkpoint) -> None:
        if checkpoint.execution_id not in self._checkpoints:
            self._checkpoints[checkpoint.execution_id] = []
        self._checkpoints[checkpoint.execution_id].append(checkpoint)
    
    def load(self, checkpoint_id: CheckpointId) -> Optional[Checkpoint]:
        for checkpoints in self._checkpoints.values():
            for cp in checkpoints:
                if cp.id == checkpoint_id:
                    return cp
        return None
    
    def load_history(self, execution_id: str) -> ExecutionHistory:
        checkpoints = self._checkpoints.get(execution_id, [])
        return ExecutionHistory(execution_id=execution_id, checkpoints=checkpoints)
    
    def delete(self, checkpoint_id: CheckpointId) -> bool:
        for execution_id, checkpoints in self._checkpoints.items():
            for i, cp in enumerate(checkpoints):
                if cp.id == checkpoint_id:
                    del checkpoints[i]
                    return True
        return False
```

---

## Application Service

The application service uses domain objects, not adapter internals:

```python
# wtb/application/services/execution_service.py

from wtb.domain.models.checkpoint import Checkpoint, CheckpointId, NodeBoundary
from wtb.domain.models.execution_history import ExecutionHistory
from wtb.infrastructure.stores.checkpoint_store import ICheckpointStore


class ExecutionService:
    """
    Application service for workflow execution.
    
    Uses DOMAIN concepts (Checkpoint, ExecutionHistory, NodeBoundary).
    Infrastructure details (LangGraph, AgentGit) are hidden behind ICheckpointStore.
    """
    
    def __init__(self, checkpoint_store: ICheckpointStore):
        self._checkpoint_store = checkpoint_store
    
    def get_execution_history(self, execution_id: str) -> ExecutionHistory:
        """Get execution history with all domain operations available."""
        return self._checkpoint_store.load_history(execution_id)
    
    def get_node_boundaries(self, execution_id: str) -> List[NodeBoundary]:
        """
        Get node boundaries - uses DOMAIN LOGIC in ExecutionHistory.
        """
        history = self._checkpoint_store.load_history(execution_id)
        return history.get_all_node_boundaries()  # Domain logic!
    
    def rollback_to_node(self, execution_id: str, node_id: str) -> Checkpoint:
        """
        Rollback to after a node completed - uses DOMAIN LOGIC.
        """
        history = self._checkpoint_store.load_history(execution_id)
        
        # Domain logic: find rollback target
        target = history.get_rollback_target(node_id)
        
        if not target:
            raise ValueError(f"Cannot rollback to node {node_id} - not found in history")
        
        # Domain validation
        if not history.can_rollback_to(target.id):
            raise ValueError(f"Checkpoint {target.id} is not a valid rollback target")
        
        return target
    
    def get_execution_path(self, execution_id: str) -> List[str]:
        """Get linearized execution path - uses DOMAIN LOGIC."""
        history = self._checkpoint_store.load_history(execution_id)
        return history.get_execution_path()  # Domain logic!
```

---

## Summary: What Changed

### Domain Layer (Rich)

| Before | After |
|--------|-------|
| `IStateAdapter.rollback()` - generic | `ExecutionHistory.get_rollback_target()` - explicit domain logic |
| No checkpoint concept | `Checkpoint`, `CheckpointId` value objects |
| No node boundary logic | `NodeBoundary.compute_from_checkpoints()` - domain logic |
| Hidden history | `ExecutionHistory` aggregate with query methods |

### Infrastructure Layer (Thin)

| Before | After |
|--------|-------|
| `LangGraphStateAdapter` - business logic + persistence | `LangGraphCheckpointStore` - persistence only |
| Maps WTB → LangGraph with logic | Maps domain Checkpoint ↔ LangGraph StateSnapshot |
| Computes node boundaries | Just loads/saves checkpoints |

### Benefits

1. **Testable domain** - can unit test checkpoint logic without LangGraph
2. **Explicit business rules** - rollback, node boundary computation are visible
3. **Swappable infrastructure** - LangGraph, AgentGit, or in-memory all work
4. **Self-documenting** - domain expresses "what is a checkpoint?"
5. **DDD compliant** - domain is the source of truth

---

## Migration Path

1. Create domain models: `Checkpoint`, `CheckpointId`, `NodeBoundary`, `ExecutionHistory`
2. Add domain events: `CheckpointCreated`, `RollbackCompleted`
3. Create `ICheckpointStore` interface (infrastructure)
4. Implement `LangGraphCheckpointStore` (mapping only)
5. Refactor `ExecutionService` to use domain models
6. Deprecate business logic in `LangGraphStateAdapter`

# LangGraph Checkpoint Granularity Design

**Date:** 2026-01-15  
**Status:** PROPOSED  
**Authors:** Architecture Team

---

## Executive Summary

This document resolves the architectural conflict between WTB's original "tool/message level" checkpoint design and LangGraph's native "super-step" checkpoint model.

### Key Decision

> **Colleague 2's position is ADOPTED with modifications:**
> 
> We keep the concept of "node boundaries" for serialization/linearization, but abandon "tool/message level" granularity terminology. Domain language is used to control LangGraph checkpoints.

### Why Not Colleague 1's Position (Full Abandonment)?

While simpler, full abandonment loses:
- Explicit audit trail markers (which node was executing)
- Linearized execution history for debugging
- FileTracker coordination points
- Batch test comparison anchors

---

## The Problem

### Original Design (Tool/Message Level)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ORIGINAL TWO-LAYER CHECKPOINT DESIGN                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  NODE A                                NODE B                                    │
│  ┌─────────────────────────┐          ┌─────────────────────────┐               │
│  │ ┌─────┐ ┌─────┐ ┌─────┐│          │ ┌─────┐ ┌─────┐        │               │
│  │ │CP-1 │ │CP-2 │ │CP-3 ││          │ │CP-4 │ │CP-5 │        │               │
│  │ │tool1│ │tool2│ │tool3││          │ │tool1│ │tool2│        │               │
│  │ └─────┘ └─────┘ └─────┘│          │ └─────┘ └─────┘        │               │
│  └─────────────────────────┘          └─────────────────────────┘               │
│        ▲                 ▲                  ▲           ▲                       │
│        │                 │                  │           │                       │
│  entry_cp_id=1    exit_cp_id=3        entry_cp_id=4  exit_cp_id=5              │
│                                                                                  │
│  PROBLEM: LangGraph doesn't checkpoint within nodes (no tool-level CPs)         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### LangGraph Reality (Super-Step Level)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH CHECKPOINT MODEL                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  START ──► NODE A ──► NODE B ──► END                                            │
│    │          │          │       │                                              │
│    ▼          ▼          ▼       ▼                                              │
│  ┌────┐    ┌────┐     ┌────┐  ┌────┐                                           │
│  │CP-0│    │CP-1│     │CP-2│  │CP-3│                                           │
│  │    │    │    │     │    │  │    │                                           │
│  │next│    │next│     │next│  │next│                                           │
│  │=[A]│    │=[B]│     │=[] │  │=[] │                                           │
│  └────┘    └────┘     └────┘  └────┘                                           │
│                                                                                  │
│  metadata.writes = {} → {A: ...} → {B: ...} → {}                                │
│                                                                                  │
│  REALITY: ONE checkpoint per node (super-step), not per tool call               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architectural Analysis

### SOLID Analysis

| Principle | Impact | Recommendation |
|-----------|--------|----------------|
| **SRP** | Node boundaries should track node lifecycle, not internal tool details | ✅ Keep node boundaries as lifecycle markers |
| **OCP** | IStateAdapter should be extensible for future granularity needs | ✅ Use `SubGraphPattern` for tool-level if needed |
| **LSP** | LangGraphStateAdapter must fulfill IStateAdapter contract | ✅ Adapt interface to super-step model |
| **ISP** | Don't expose LangGraph internals in domain layer | ✅ Use WTB domain language |
| **DIP** | Application depends on IStateAdapter abstraction | ✅ Hide checkpoint_id as implementation detail |

### ACID Analysis

| Property | LangGraph Behavior | WTB Mapping |
|----------|-------------------|-------------|
| **Atomicity** | Each super-step is atomic | Node execution = atomic unit |
| **Consistency** | State consistent at checkpoints | Node boundaries = consistency points |
| **Isolation** | `thread_id` isolates executions | Execution ID → Thread ID |
| **Durability** | PostgresSaver for production | WTB uses PostgresSaver in production |

---

## Proposed Design

### Core Principle

> **"Super-Step = Node Boundary. There is no finer granularity unless explicitly modeled."**

### Design Elements

#### 1. Defer "Tool/Message Level" Implementation 📋

LangGraph does not checkpoint within nodes natively. The "tool/message level checkpoint" feature is **DEFERRED** for future AgentGit adapter implementation.

```diff
- "All checkpoints atomic at tool/message level" (DEFERRED - requires AgentGit)
+ "All checkpoints atomic at node (super-step) level" (CURRENT - LangGraph)
```

#### 2. Redefine Node Boundaries for LangGraph ✅

Node boundaries become **semantic markers** pointing to LangGraph checkpoints:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ADAPTED NODE BOUNDARY DESIGN                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  LangGraph Checkpoints:                                                          │
│  ═════════════════════                                                           │
│                                                                                  │
│  CP-0 (next=[A])  ──►  CP-1 (writes={A:...}, next=[B])  ──►  CP-2 (writes={B:...})│
│       │                        │                                   │             │
│       │                        │                                   │             │
│       ▼                        ▼                                   ▼             │
│  ┌─────────────┐         ┌─────────────┐                    ┌─────────────┐     │
│  │ Node A      │         │ Node A      │                    │ Node B      │     │
│  │ entry_cp=0  │         │ exit_cp=1   │                    │ exit_cp=2   │     │
│  │ (about to   │         │ (completed) │                    │ (completed) │     │
│  │  execute)   │         │             │                    │             │     │
│  └─────────────┘         └─────────────┘                    └─────────────┘     │
│                                                                                  │
│  WTB Node Boundaries Table:                                                      │
│  ══════════════════════════                                                      │
│  | node_id | entry_checkpoint_id | exit_checkpoint_id | status    |             │
│  |---------|--------------------|--------------------|-----------|             │
│  | A       | cp-0               | cp-1               | completed |             │
│  | B       | cp-1               | cp-2               | completed |             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Mapping Rules:**
- `entry_checkpoint_id` = checkpoint where `node_id` appears in `snapshot.next`
- `exit_checkpoint_id` = checkpoint where `node_id` appears in `snapshot.metadata.writes`

#### 3. Domain Language Translation Layer ✅

WTB domain concepts map to LangGraph concepts:

| WTB Domain Language | LangGraph API | Description |
|---------------------|---------------|-------------|
| `execution_id` | `thread_id` | Unique execution isolation |
| `node_boundary` | `checkpoint + metadata.writes` | Node completion marker |
| `rollback_to_node(node_id)` | `get_state(checkpoint_id)` | Restore to node exit state |
| `get_execution_history()` | `get_state_history()` | Linearized audit trail |
| `current_node` | `snapshot.next[0]` | Next node to execute |

#### 4. Optional Tool-Level Granularity via Sub-Graph Pattern 🔧

If tool-level rollback is **explicitly required** for specific nodes, model tools as a sub-graph:

```python
# Instead of:
def node_with_tools(state):
    result1 = tool1(state)  # No checkpoint here
    result2 = tool2(state)  # No checkpoint here
    return combined_result

# Use sub-graph pattern:
def build_tool_subgraph():
    subgraph = StateGraph(ToolState)
    subgraph.add_node("tool1", tool1)
    subgraph.add_node("tool2", tool2)
    subgraph.add_edge("tool1", "tool2")
    return subgraph.compile()

# Main graph includes sub-graph
graph.add_node("node_with_tools", build_tool_subgraph())
# Now each tool is a super-step with its own checkpoint
```

**When to use Sub-Graph Pattern:**
- Long-running tools with side effects
- Tools that require independent rollback
- Expensive tools that shouldn't re-execute on retry

**When NOT to use Sub-Graph Pattern:**
- Simple transformations
- Stateless computations
- Fast tools with no side effects

---

## Updated Schema

### wtb_node_boundaries (Updated)

```sql
-- ═══════════════════════════════════════════════════════════════════════════════
-- WTB NODE BOUNDARIES (Updated for LangGraph)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE wtb_node_boundaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- WTB Execution Context
    execution_id TEXT NOT NULL,          -- WTB execution UUID = LangGraph thread_id
    
    -- Node Identification
    node_id TEXT NOT NULL,               -- Workflow node name
    
    -- LangGraph Checkpoint References (String IDs, not integers)
    entry_checkpoint_id TEXT,            -- CP where node in snapshot.next
    exit_checkpoint_id TEXT,             -- CP where node in snapshot.metadata.writes
    
    -- Node Execution Status
    node_status TEXT NOT NULL CHECK (node_status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    
    -- Metrics (no tool_count - not applicable to super-step model)
    duration_ms INTEGER,
    
    -- Error Info
    error_message TEXT,
    error_details TEXT,                  -- JSON
    
    -- Uniqueness: One boundary per node per execution
    UNIQUE(execution_id, node_id)
);

-- Indexes
CREATE INDEX idx_wtb_node_boundaries_execution ON wtb_node_boundaries(execution_id);
CREATE INDEX idx_wtb_node_boundaries_status ON wtb_node_boundaries(node_status);
```

**Changes from original:**
- Removed `internal_session_id` (LangGraph uses thread_id, not integer session IDs)
- Removed `tool_count`, `checkpoint_count` (not applicable to super-step model)
- Changed `checkpoint_id` type from INTEGER to TEXT (LangGraph uses string UUIDs)

---

## Updated IStateAdapter Interface

```python
# wtb/domain/interfaces/state_adapter.py

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class NodeBoundary:
    """Domain object for node execution boundary."""
    node_id: str
    entry_checkpoint_id: Optional[str]
    exit_checkpoint_id: Optional[str]
    status: str  # "pending", "running", "completed", "failed"
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_ms: Optional[int]
    error_message: Optional[str]

@dataclass
class ExecutionCheckpoint:
    """Domain object for execution checkpoint."""
    checkpoint_id: str
    step: int
    node_writes: Dict[str, Any]  # Which node wrote to this checkpoint
    next_nodes: List[str]
    created_at: str
    values: Dict[str, Any]  # State values at this checkpoint


class IStateAdapter(ABC):
    """
    State adapter interface for workflow execution.
    
    NOTE: This interface is designed around NODE-LEVEL granularity.
    There is no tool-level checkpointing within nodes.
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def initialize_execution(self, execution_id: str) -> str:
        """
        Initialize execution session.
        
        Returns: Session/Thread ID for this execution
        """
        pass
    
    @abstractmethod
    def get_current_execution_id(self) -> Optional[str]:
        """Get current execution ID."""
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Execution (Automatic Node-Level Checkpointing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def execute(self, initial_state: dict) -> dict:
        """
        Execute workflow from initial state.
        
        Checkpoints are created automatically at each node (super-step).
        """
        pass
    
    @abstractmethod
    def resume(self, from_checkpoint_id: Optional[str] = None) -> dict:
        """
        Resume execution from checkpoint.
        
        If checkpoint_id is None, resumes from latest checkpoint.
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # State Access
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def get_current_state(self) -> dict:
        """Get current state values."""
        pass
    
    @abstractmethod
    def get_next_nodes(self) -> List[str]:
        """Get next nodes to execute."""
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Node Boundary Management (Domain Language)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def get_node_boundaries(self, execution_id: str) -> List[NodeBoundary]:
        """
        Get all node boundaries for execution.
        
        Returns linearized list of node entries/exits for audit trail.
        """
        pass
    
    @abstractmethod
    def get_node_boundary(self, execution_id: str, node_id: str) -> Optional[NodeBoundary]:
        """Get specific node boundary."""
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Time Travel (Rollback)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def get_checkpoint_history(self) -> List[ExecutionCheckpoint]:
        """
        Get full checkpoint history for time travel.
        
        Returns list of checkpoints (most recent first).
        """
        pass
    
    @abstractmethod
    def rollback_to_checkpoint(self, checkpoint_id: str) -> dict:
        """
        Rollback to specific checkpoint.
        
        Returns the state values at that checkpoint.
        """
        pass
    
    @abstractmethod
    def rollback_to_node(self, node_id: str) -> dict:
        """
        Rollback to after specific node completed.
        
        Convenience method that finds the exit checkpoint for the node.
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Fork (for Batch Testing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def create_fork(
        self, 
        fork_execution_id: str,
        from_checkpoint_id: Optional[str] = None
    ) -> "IStateAdapter":
        """
        Create a fork from checkpoint for variant testing.
        
        Returns a new adapter instance for the forked execution.
        """
        pass
```

---

## Migration Guide

### Step 1: Update Design Principles

```diff
- "Single Checkpoint Type + Node Boundary Pointers: All checkpoints atomic at tool/message level."
+ "Single Checkpoint Type + Node Boundary Pointers: All checkpoints atomic at node (super-step) level."
```

### Step 2: Update wtb_node_boundaries Schema

```diff
- entry_checkpoint_id INTEGER,  -- First checkpoint when entering node
- exit_checkpoint_id INTEGER,   -- Last checkpoint when exiting node
+ entry_checkpoint_id TEXT,     -- LangGraph checkpoint_id (UUID string)
+ exit_checkpoint_id TEXT,      -- LangGraph checkpoint_id (UUID string)

- tool_count INTEGER DEFAULT 0,
- checkpoint_count INTEGER DEFAULT 0,
```

### Step 3: Update LangGraphStateAdapter

Implement `get_node_boundaries()` by scanning checkpoint history:

```python
def get_node_boundaries(self, execution_id: str) -> List[NodeBoundary]:
    """
    Build node boundaries from LangGraph checkpoint history.
    """
    boundaries = {}  # node_id -> NodeBoundary
    
    config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
    
    # Iterate history (oldest first for correct entry/exit tracking)
    checkpoints = list(reversed(list(self._graph.get_state_history(config))))
    
    for checkpoint in checkpoints:
        cp_id = checkpoint.config["configurable"]["checkpoint_id"]
        writes = checkpoint.metadata.get("writes", {})
        next_nodes = checkpoint.next
        
        # Track entry: node appears in next (about to execute)
        for node_id in next_nodes:
            if node_id not in boundaries:
                boundaries[node_id] = NodeBoundary(
                    node_id=node_id,
                    entry_checkpoint_id=cp_id,
                    exit_checkpoint_id=None,
                    status="running",
                    started_at=checkpoint.created_at,
                    completed_at=None,
                    duration_ms=None,
                    error_message=None
                )
        
        # Track exit: node appears in writes (completed execution)
        for node_id in writes.keys():
            if node_id in boundaries and boundaries[node_id].exit_checkpoint_id is None:
                boundaries[node_id].exit_checkpoint_id = cp_id
                boundaries[node_id].status = "completed"
                boundaries[node_id].completed_at = checkpoint.created_at
    
    return list(boundaries.values())
```

---

## Summary

### What We Keep (Colleague 2) ✅

1. **Node boundary concept** - For linearization, audit trail, and FileTracker coordination
2. **Entry/exit checkpoint pointers** - Adapted to LangGraph checkpoint_ids
3. **Domain language** - WTB speaks "nodes" and "boundaries", not "super-steps"

### What We Defer for Future Implementation 📋

1. **AgentGit "Tool/message level" checkpointing** - DEFERRED (requires AgentGit adapter or sub-graph modeling)
2. **Intra-node checkpointing** - DEFERRED (unless explicitly modeled as sub-graph)
3. **tool_count, checkpoint_count metrics** - DEFERRED (may be added with AgentGit adapter)

### SOLID Compliance ✅

| Principle | How Addressed |
|-----------|---------------|
| SRP | Node boundaries track lifecycle only, not checkpoint internals |
| OCP | Sub-graph pattern allows tool-level granularity when needed |
| LSP | LangGraphStateAdapter is substitutable for IStateAdapter |
| ISP | IStateAdapter exposes domain concepts, not LangGraph internals |
| DIP | Application depends on IStateAdapter abstraction |

### ACID Compliance ✅

| Property | How Addressed |
|----------|---------------|
| Atomicity | Node execution is atomic (super-step) |
| Consistency | Node boundaries mark consistency points |
| Isolation | thread_id isolates parallel executions |
| Durability | PostgresSaver for production persistence |

---

## Decision Record

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-15 | Adopt Colleague 2's position with modifications | Preserves audit trail while aligning with LangGraph model |
| 2026-01-15 | Defer "tool/message level" implementation | LangGraph doesn't support natively; AgentGit deferred |
| 2026-01-15 | Keep node boundaries as semantic markers | Required for linearization, FileTracker, batch testing |
| 2026-01-15 | Introduce Sub-Graph Pattern for tool-level needs | OCP compliance - extend without modifying core |

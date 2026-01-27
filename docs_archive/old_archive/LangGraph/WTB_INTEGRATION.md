# LangGraph WTB Integration Design

**Last Updated:** 2026-01-15

**Sources:**
- [LangGraph Reference](https://reference.langchain.com/python/langgraph/)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

## Overview

This document details how WTB integrates with LangGraph as the PRIMARY state persistence layer.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         WTB + LANGGRAPH INTEGRATION                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  WTB Application Layer                                                           │
│  ════════════════════                                                            │
│       │                                                                          │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         IStateAdapter                                    │   │
│  │                    (Anti-Corruption Layer)                               │   │
│  │                                                                          │   │
│  │   • save_checkpoint()      → graph.invoke() (automatic)                 │   │
│  │   • load_checkpoint()      → graph.get_state(config)                    │   │
│  │   • rollback()             → graph.get_state(config + checkpoint_id)    │   │
│  │   • get_history()          → graph.get_state_history(config)            │   │
│  │   • update_state()         → graph.update_state(config, values)         │   │
│  │                                                                          │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      LangGraphStateAdapter                               │   │
│  │                         (PRIMARY)                                        │   │
│  │                                                                          │   │
│  │   • Thread ID = execution_id                                            │   │
│  │   • Automatic checkpointing at each super-step                          │   │
│  │   • Native time travel via get_state_history()                          │   │
│  │   • Fault tolerance (pending writes preserved)                          │   │
│  │                                                                          │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         LangGraph Core                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │   Graphs    │  │   Pregel    │  │ Checkpoints │  │  Channels   │    │   │
│  │  │  StateGraph │  │ Computation │  │ Persistence │  │  Messages   │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      Checkpointer Storage                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │   │
│  │  │InMemorySaver│  │ SqliteSaver │  │PostgresSaver│                      │   │
│  │  │  (testing)  │  │   (dev)     │  │(production) │                      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## LangGraph Core Components

Based on [LangGraph Reference](https://reference.langchain.com/python/langgraph/):

| Component | Description | WTB Usage |
|-----------|-------------|-----------|
| **Graphs** | Main graph abstraction (`StateGraph`, `MessageGraph`) | Workflow definition |
| **Pregel** | Pregel-inspired computation model for parallel execution | Node execution model |
| **Checkpointing** | Saving and restoring graph state | State persistence |
| **Storage** | Storage backends (Memory, SQLite, PostgreSQL) | Checkpointer selection |
| **Caching** | Caching mechanisms for performance | Optional optimization |
| **Channels** | Message passing between nodes | State channel reducers |
| **Types** | Type definitions for graph components | State schema |
| **Runtime** | Runtime configuration | Execution control |
| **Config** | Configuration options | Thread/checkpoint config |

## LangGraphStateAdapter Implementation

```python
# wtb/infrastructure/adapters/langgraph_state_adapter.py

from abc import ABC
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver

from wtb.domain.interfaces import IStateAdapter
from wtb.domain.models import ExecutionState


@dataclass
class LangGraphConfig:
    """Configuration for LangGraph adapter."""
    checkpointer_type: str = "memory"  # "memory", "sqlite", "postgres"
    connection_string: Optional[str] = None
    
    @classmethod
    def for_testing(cls) -> "LangGraphConfig":
        """InMemorySaver for unit tests."""
        return cls(checkpointer_type="memory")
    
    @classmethod
    def for_development(cls, db_path: str = "data/wtb_checkpoints.db") -> "LangGraphConfig":
        """SqliteSaver for local development."""
        return cls(checkpointer_type="sqlite", connection_string=db_path)
    
    @classmethod
    def for_production(cls, connection_string: str) -> "LangGraphConfig":
        """PostgresSaver for production."""
        return cls(checkpointer_type="postgres", connection_string=connection_string)


class LangGraphStateAdapter(IStateAdapter):
    """
    PRIMARY state adapter using LangGraph checkpointers.
    
    This adapter translates WTB operations to LangGraph APIs:
    
    WTB Operation          → LangGraph API
    ═══════════════════════════════════════════════════════════
    initialize_session()   → Set thread_id, compile graph
    save_checkpoint()      → Automatic via graph.invoke()
    load_checkpoint()      → graph.get_state(config)
    rollback()             → graph.get_state(config + checkpoint_id)
    get_checkpoints()      → graph.get_state_history(config)
    update_state()         → graph.update_state(config, values)
    """
    
    def __init__(self, config: LangGraphConfig):
        self._config = config
        self._checkpointer = self._create_checkpointer()
        self._graph: Optional[CompiledStateGraph] = None
        self._current_thread_id: Optional[str] = None
        self._current_execution_id: Optional[str] = None
    
    def _create_checkpointer(self) -> BaseCheckpointSaver:
        """Factory for checkpointer based on config."""
        if self._config.checkpointer_type == "memory":
            return InMemorySaver()
        
        elif self._config.checkpointer_type == "sqlite":
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3
            conn = sqlite3.connect(self._config.connection_string)
            return SqliteSaver(conn)
        
        elif self._config.checkpointer_type == "postgres":
            from langgraph.checkpoint.postgres import PostgresSaver
            saver = PostgresSaver.from_conn_string(self._config.connection_string)
            saver.setup()  # Create tables if needed
            return saver
        
        else:
            raise ValueError(f"Unknown checkpointer type: {self._config.checkpointer_type}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Graph Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_workflow_graph(self, graph: StateGraph) -> None:
        """Compile workflow graph with checkpointer."""
        self._graph = graph.compile(checkpointer=self._checkpointer)
    
    def get_compiled_graph(self) -> CompiledStateGraph:
        """Get compiled graph."""
        if not self._graph:
            raise RuntimeError("Graph not set. Call set_workflow_graph() first.")
        return self._graph
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management (Thread-based)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def initialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[str]:
        """
        Initialize session using LangGraph thread.
        
        Maps WTB execution_id to LangGraph thread_id.
        """
        self._current_execution_id = execution_id
        self._current_thread_id = f"wtb-{execution_id}"
        return self._current_thread_id
    
    def get_config(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Get LangGraph config for current thread."""
        if not self._current_thread_id:
            raise RuntimeError("No active session. Call initialize_session() first.")
        
        config = {"configurable": {"thread_id": self._current_thread_id}}
        
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        
        return config
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Execution (Automatic Checkpointing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def execute(self, initial_state: dict) -> dict:
        """
        Execute workflow with automatic checkpointing.
        
        LangGraph saves a checkpoint at each super-step automatically.
        """
        if not self._graph:
            raise RuntimeError("Graph not set. Call set_workflow_graph() first.")
        
        config = self.get_config()
        return self._graph.invoke(initial_state, config)
    
    async def aexecute(self, initial_state: dict) -> dict:
        """Async execution."""
        if not self._graph:
            raise RuntimeError("Graph not set. Call set_workflow_graph() first.")
        
        config = self.get_config()
        return await self._graph.ainvoke(initial_state, config)
    
    def stream(self, initial_state: dict, stream_mode: str = "updates"):
        """
        Stream execution events.
        
        stream_mode: "values" | "updates" | "messages"
        """
        if not self._graph:
            raise RuntimeError("Graph not set. Call set_workflow_graph() first.")
        
        config = self.get_config()
        return self._graph.stream(initial_state, config, stream_mode=stream_mode)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # State Access
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_current_state(self) -> dict:
        """Get current state values."""
        config = self.get_config()
        snapshot = self._graph.get_state(config)
        return snapshot.values if snapshot else {}
    
    def get_state_snapshot(self, checkpoint_id: Optional[str] = None):
        """Get full StateSnapshot."""
        config = self.get_config(checkpoint_id)
        return self._graph.get_state(config)
    
    def get_next_nodes(self) -> tuple:
        """Get next nodes to execute."""
        config = self.get_config()
        snapshot = self._graph.get_state(config)
        return snapshot.next if snapshot else ()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Time Travel
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_checkpoint_history(self) -> List[dict]:
        """
        Get full checkpoint history for time travel.
        
        Returns list of checkpoints (most recent first).
        """
        config = self.get_config()
        history = []
        
        for snapshot in self._graph.get_state_history(config):
            history.append({
                "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
                "step": snapshot.metadata.get("step"),
                "source": snapshot.metadata.get("source"),
                "writes": snapshot.metadata.get("writes", {}),
                "values": snapshot.values,
                "next": snapshot.next,
                "created_at": snapshot.created_at,
            })
        
        return history
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> dict:
        """
        Rollback to specific checkpoint.
        
        Returns the state values at that checkpoint.
        """
        config = self.get_config(checkpoint_id)
        snapshot = self._graph.get_state(config)
        
        if not snapshot:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        return snapshot.values
    
    def rollback_to_node(self, node_id: str) -> dict:
        """
        Rollback to after specific node completed.
        
        Finds checkpoint where node_id was in writes.
        """
        config = self.get_config()
        
        for snapshot in self._graph.get_state_history(config):
            writes = snapshot.metadata.get("writes", {})
            if node_id in writes:
                return self.rollback_to_checkpoint(
                    snapshot.config["configurable"]["checkpoint_id"]
                )
        
        raise ValueError(f"Node {node_id} not found in history")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # State Modification
    # ═══════════════════════════════════════════════════════════════════════════
    
    def update_state(
        self, 
        values: dict, 
        as_node: Optional[str] = None
    ) -> None:
        """
        Update state mid-execution.
        
        Useful for human-in-the-loop workflows.
        """
        config = self.get_config()
        self._graph.update_state(config, values, as_node=as_node)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Fork (for batch testing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_fork(
        self, 
        fork_thread_id: str,
        from_checkpoint_id: Optional[str] = None
    ) -> "LangGraphStateAdapter":
        """
        Create a fork for variant execution.
        
        Used by batch test runner to create isolated variant threads.
        """
        fork_adapter = LangGraphStateAdapter(self._config)
        fork_adapter._graph = self._graph
        fork_adapter._current_thread_id = fork_thread_id
        
        # If forking from specific checkpoint, copy state
        if from_checkpoint_id:
            source_config = self.get_config(from_checkpoint_id)
            source_state = self._graph.get_state(source_config)
            
            if source_state:
                fork_config = {"configurable": {"thread_id": fork_thread_id}}
                # Initialize fork with source state
                self._graph.update_state(fork_config, source_state.values)
        
        return fork_adapter
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Cleanup
    # ═══════════════════════════════════════════════════════════════════════════
    
    def cleanup(self, keep_latest: int = 5) -> int:
        """
        Cleanup old checkpoints.
        
        Note: LangGraph handles this internally for most backends.
        This is a no-op for InMemorySaver.
        """
        # LangGraph checkpointers handle their own cleanup
        # This method exists for interface compatibility
        return 0
    
    def get_current_session_id(self) -> Optional[str]:
        """Get current thread ID."""
        return self._current_thread_id


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Integration
# ═══════════════════════════════════════════════════════════════════════════════

class LangGraphStateAdapterFactory:
    """Factory for creating LangGraphStateAdapter instances."""
    
    @staticmethod
    def create_for_testing() -> LangGraphStateAdapter:
        """Create adapter for unit tests."""
        return LangGraphStateAdapter(LangGraphConfig.for_testing())
    
    @staticmethod
    def create_for_development(
        db_path: str = "data/wtb_checkpoints.db"
    ) -> LangGraphStateAdapter:
        """Create adapter for development."""
        return LangGraphStateAdapter(LangGraphConfig.for_development(db_path))
    
    @staticmethod
    def create_for_production(connection_string: str) -> LangGraphStateAdapter:
        """Create adapter for production."""
        return LangGraphStateAdapter(LangGraphConfig.for_production(connection_string))
```

## State Schema Definition

Using LangGraph's type system for WTB workflow state:

```python
# wtb/domain/models/langgraph_state.py

from typing import TypedDict, Annotated, Optional, List, Dict, Any
from operator import add

class WTBWorkflowState(TypedDict):
    """
    State schema for WTB workflows using LangGraph Channels.
    
    Annotated types define reducers for state updates:
    - Annotated[list, add] → Append to list
    - Regular types → Replace value
    """
    
    # Execution tracking
    execution_id: str
    current_node_id: str
    execution_path: Annotated[List[str], add]  # Append nodes as executed
    
    # Workflow state
    workflow_variables: Dict[str, Any]
    
    # Node results (append each node's output)
    node_results: Annotated[List[Dict[str, Any]], add]
    
    # Error tracking
    error_message: Optional[str]
    error_node_id: Optional[str]
    
    # Metrics
    metrics: Dict[str, float]
    
    # Status
    status: str  # "running", "paused", "completed", "failed"
```

## Integration with ExecutionController

```python
# wtb/application/services/execution_controller.py (updated)

from wtb.infrastructure.adapters.langgraph_state_adapter import (
    LangGraphStateAdapter, 
    LangGraphConfig
)

class ExecutionController:
    """
    ExecutionController using LangGraph for state persistence.
    """
    
    def __init__(
        self,
        state_adapter: LangGraphStateAdapter,
        workflow_graph: StateGraph,
        uow: IUnitOfWork
    ):
        self._state_adapter = state_adapter
        self._uow = uow
        
        # Set workflow graph on adapter
        self._state_adapter.set_workflow_graph(workflow_graph)
    
    def run(self, execution_id: str, initial_state: dict) -> dict:
        """Run workflow execution."""
        # Initialize LangGraph thread
        self._state_adapter.initialize_session(execution_id, initial_state)
        
        # Execute with automatic checkpointing
        result = self._state_adapter.execute(initial_state)
        
        return result
    
    def pause(self) -> dict:
        """Pause execution - get current state."""
        return self._state_adapter.get_current_state()
    
    def resume(self, modified_state: Optional[dict] = None) -> dict:
        """Resume execution, optionally with modified state."""
        if modified_state:
            self._state_adapter.update_state(modified_state)
        
        current = self._state_adapter.get_current_state()
        return self._state_adapter.execute(current)
    
    def rollback(self, checkpoint_id: str) -> dict:
        """Rollback to checkpoint."""
        return self._state_adapter.rollback_to_checkpoint(checkpoint_id)
    
    def rollback_to_node(self, node_id: str) -> dict:
        """Rollback to after node completion."""
        return self._state_adapter.rollback_to_node(node_id)
    
    def get_history(self) -> List[dict]:
        """Get checkpoint history."""
        return self._state_adapter.get_checkpoint_history()
```

## Ray Batch Test Integration

```python
# wtb/application/services/ray_batch_runner.py (updated for LangGraph)

import ray
from langgraph.checkpoint.postgres import PostgresSaver

@ray.remote
class VariantExecutionActor:
    """
    Ray Actor using LangGraph for state persistence.
    
    Each actor has its own checkpointer for thread isolation.
    """
    
    def __init__(self, db_url: str, workflow_graph_dict: dict):
        # Create checkpointer per actor (connection reuse)
        self._checkpointer = PostgresSaver.from_conn_string(db_url)
        self._checkpointer.setup()
        
        # Rebuild graph from dict
        self._workflow_graph = self._rebuild_graph(workflow_graph_dict)
        self._compiled_graph = self._workflow_graph.compile(
            checkpointer=self._checkpointer
        )
    
    def execute_variant(
        self,
        variant_id: str,
        batch_test_id: str,
        initial_state: dict,
        variant_config: dict
    ) -> dict:
        """
        Execute single variant with isolated thread.
        
        thread_id provides complete isolation between variants.
        """
        thread_id = f"batch-{batch_test_id}-{variant_id}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Apply variant modifications to initial state
        state = self._apply_variant(initial_state, variant_config)
        
        try:
            result = self._compiled_graph.invoke(state, config)
            return {
                "success": True,
                "variant_id": variant_id,
                "result": result,
                "thread_id": thread_id
            }
        except Exception as e:
            return {
                "success": False,
                "variant_id": variant_id,
                "error": str(e),
                "thread_id": thread_id
            }
    
    def get_variant_history(self, batch_test_id: str, variant_id: str) -> List[dict]:
        """Get checkpoint history for variant."""
        thread_id = f"batch-{batch_test_id}-{variant_id}"
        config = {"configurable": {"thread_id": thread_id}}
        
        return list(self._compiled_graph.get_state_history(config))
```

## Pregel Computation Model

LangGraph uses a [Pregel-inspired computation model](https://reference.langchain.com/python/langgraph/):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PREGEL COMPUTATION MODEL                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Super-Step N                                                                    │
│  ════════════                                                                    │
│                                                                                  │
│  1. READ: Each node reads current state from channels                           │
│  2. COMPUTE: Nodes execute in parallel (if no dependencies)                     │
│  3. WRITE: Nodes write updates to channels                                      │
│  4. CHECKPOINT: State saved automatically                                       │
│                                                                                  │
│       ┌─────────────────────────────────────────────────────┐                   │
│       │                  State Channels                      │                   │
│       │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │                   │
│       │  │ foo     │  │ bar     │  │ baz     │              │                   │
│       │  │ (str)   │  │ (list)  │  │ (dict)  │              │                   │
│       │  └────┬────┘  └────┬────┘  └────┬────┘              │                   │
│       └───────┼────────────┼────────────┼───────────────────┘                   │
│               │            │            │                                        │
│               ▼            ▼            ▼                                        │
│       ┌─────────────────────────────────────────────────────┐                   │
│       │              Node Execution (Parallel)               │                   │
│       │  ┌───────────┐  ┌───────────┐  ┌───────────┐        │                   │
│       │  │  node_a   │  │  node_b   │  │  node_c   │        │                   │
│       │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘        │                   │
│       └────────┼──────────────┼──────────────┼──────────────┘                   │
│                │              │              │                                   │
│                ▼              ▼              ▼                                   │
│       ┌─────────────────────────────────────────────────────┐                   │
│       │              Channel Updates (Reducers)              │                   │
│       │  foo = "new"  │  bar += ["x"]  │  baz.update({})    │                   │
│       └─────────────────────────────────────────────────────┘                   │
│                                │                                                 │
│                                ▼                                                 │
│                       ┌───────────────┐                                         │
│                       │  Checkpoint   │                                         │
│                       │    Saved      │                                         │
│                       └───────────────┘                                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Migration from AgentGit

| AgentGit Concept | LangGraph Equivalent |
|------------------|---------------------|
| `InternalSession` | `thread_id` |
| `Checkpoint` | `StateSnapshot` |
| `checkpoint_id` | `config["configurable"]["checkpoint_id"]` |
| `restore_from_checkpoint()` | `graph.get_state(config)` |
| Manual `save_checkpoint()` | Automatic at each super-step |
| `workflow_variables` | `state.values` |
| `CheckpointManager_mdp` | `BaseCheckpointSaver` |
| `ToolManager.rollback_to_position()` | `graph.get_state_history()` (Node-level; Tool-level via AgentGit - DEFERRED) |

## Dependencies

Add to `pyproject.toml`:

```toml
[project.dependencies]
langgraph = ">=0.2.0"
langgraph-checkpoint = ">=1.0.0"

[project.optional-dependencies]
dev = [
    "langgraph-checkpoint-sqlite>=1.0.0",
]
production = [
    "langgraph-checkpoint-postgres>=1.0.0",
]
```

## Audit & Event System Integration

### Overview

WTB integrates with LangGraph's audit and event system to provide comprehensive observability and traceability. See [AUDIT_EVENT_SYSTEM.md](./AUDIT_EVENT_SYSTEM.md) for full details.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    WTB + LANGGRAPH AUDIT INTEGRATION                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  LangGraph Execution                                                             │
│       │                                                                          │
│       ├─────► Streaming Events ──────► LangGraphEventBridge ──► WTBEventBus     │
│       │        (astream_events)                                                  │
│       │                                                                          │
│       ├─────► Checkpoints ───────────► StateSnapshot ──────────► Audit Trail    │
│       │        (automatic)              (implicit audit)                         │
│       │                                                                          │
│       └─────► Tracing ───────────────► LangSmith / OTEL ───────► Observability  │
│                (callbacks)                                                       │
│                                                                                  │
│  Event Flow:                                                                     │
│  ═══════════                                                                     │
│                                                                                  │
│  1. LangGraph emits events during execution (stream_mode="events")              │
│  2. LangGraphEventBridge transforms to WTB domain events                        │
│  3. WTBEventBus publishes to subscribers (AuditEventListener, etc.)             │
│  4. AuditLogRepository persists audit entries                                   │
│  5. Checkpoints provide additional audit trail via get_state_history()          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### LangGraphEventBridge Implementation

```python
# wtb/infrastructure/events/langgraph_event_bridge.py

from typing import Optional, AsyncIterator
from datetime import datetime
import uuid

from langgraph.graph import CompiledStateGraph

from wtb.infrastructure.events import WTBEventBus
from wtb.domain.events import (
    ExecutionStartedEvent,
    ExecutionCompletedEvent,
    ExecutionFailedEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
    NodeFailedEvent,
    CheckpointCreatedEvent,
)
from wtb.domain.models.checkpoint import CheckpointId


class LangGraphEventBridge:
    """
    Bridge LangGraph streaming events to WTB EventBus.
    
    Responsibilities:
    - Consume LangGraph astream_events()
    - Transform to WTB domain events
    - Publish to WTBEventBus
    - Handle event correlation (run_id → execution_id)
    
    SOLID:
    - SRP: Only handles event transformation and bridging
    - OCP: New event types via subclass or composition
    - DIP: Depends on WTBEventBus abstraction
    """
    
    def __init__(
        self, 
        event_bus: WTBEventBus,
        include_inputs: bool = False,  # Don't log inputs by default (PII)
        include_outputs: bool = True,
    ):
        self._event_bus = event_bus
        self._include_inputs = include_inputs
        self._include_outputs = include_outputs
        self._active_nodes: dict[str, datetime] = {}  # Track node start times
    
    async def bridge_execution(
        self,
        graph: CompiledStateGraph,
        initial_state: dict,
        config: dict,
        execution_id: str,
    ) -> dict:
        """
        Execute graph while bridging events to WTB EventBus.
        
        Returns the final result.
        """
        thread_id = config["configurable"]["thread_id"]
        
        # Publish execution started
        self._event_bus.publish(ExecutionStartedEvent(
            execution_id=execution_id,
            workflow_id=config.get("metadata", {}).get("workflow_id", "unknown"),
        ))
        
        final_result = None
        
        try:
            async for event in graph.astream_events(
                initial_state, config, version="v2"
            ):
                wtb_event = self._transform_event(event, execution_id, thread_id)
                if wtb_event:
                    self._event_bus.publish(wtb_event)
                
                # Capture final result
                if event["event"] == "on_chain_end" and event.get("name") == "LangGraph":
                    final_result = event.get("data", {}).get("output", {})
            
            # Publish execution completed
            self._event_bus.publish(ExecutionCompletedEvent(
                execution_id=execution_id,
                final_state=final_result or {},
            ))
            
            return final_result or {}
            
        except Exception as e:
            # Publish execution failed
            self._event_bus.publish(ExecutionFailedEvent(
                execution_id=execution_id,
                error_message=str(e),
            ))
            raise
    
    def _transform_event(
        self, 
        lg_event: dict, 
        execution_id: str,
        thread_id: str,
    ) -> Optional[object]:
        """Transform LangGraph event to WTB domain event."""
        event_type = lg_event["event"]
        name = lg_event.get("name", "unknown")
        run_id = lg_event.get("run_id", "")
        
        # Skip internal LangGraph events
        if name.startswith("__"):
            return None
        
        # Node start
        if event_type == "on_chain_start" and name != "LangGraph":
            self._active_nodes[run_id] = datetime.utcnow()
            return NodeStartedEvent(
                execution_id=execution_id,
                node_id=name,
                checkpoint_id=None,  # Set by checkpoint event
            )
        
        # Node end
        if event_type == "on_chain_end" and name != "LangGraph":
            start_time = self._active_nodes.pop(run_id, None)
            duration_ms = None
            if start_time:
                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            outputs = None
            if self._include_outputs:
                outputs = lg_event.get("data", {}).get("output")
            
            return NodeCompletedEvent(
                execution_id=execution_id,
                node_id=name,
                checkpoint_id=None,  # Retrieved from checkpoint
                output=outputs,
            )
        
        # Node error
        if event_type == "on_chain_error":
            return NodeFailedEvent(
                execution_id=execution_id,
                node_id=name,
                error_message=str(lg_event.get("data", {}).get("error", "Unknown error")),
            )
        
        # Tool events can be captured similarly
        # ...
        
        return None
    
    def bridge_checkpoint_events(
        self,
        graph: CompiledStateGraph,
        config: dict,
        execution_id: str,
    ):
        """
        Bridge checkpoint history to WTB audit events.
        
        Call after execution to emit checkpoint events.
        """
        for snapshot in graph.get_state_history(config):
            checkpoint_id = CheckpointId(
                snapshot.config["configurable"]["checkpoint_id"]
            )
            
            # Determine which node created this checkpoint
            writes = snapshot.metadata.get("writes", {})
            node_id = list(writes.keys())[0] if writes else None
            
            self._event_bus.publish(CheckpointCreatedEvent(
                execution_id=execution_id,
                checkpoint_id=checkpoint_id,
                node_id=node_id,
                step=snapshot.metadata.get("step"),
            ))
```

### Integration with ExecutionController

```python
# wtb/application/services/execution_controller.py (updated)

from wtb.infrastructure.events.langgraph_event_bridge import LangGraphEventBridge

class ExecutionController:
    """
    ExecutionController with LangGraph event bridging.
    """
    
    def __init__(
        self,
        state_adapter: LangGraphStateAdapter,
        workflow_graph: StateGraph,
        uow: IUnitOfWork,
        event_bus: WTBEventBus,  # NEW
    ):
        self._state_adapter = state_adapter
        self._uow = uow
        self._event_bus = event_bus
        self._event_bridge = LangGraphEventBridge(event_bus)
        
        # Set workflow graph on adapter
        self._state_adapter.set_workflow_graph(workflow_graph)
    
    async def run_async(self, execution_id: str, initial_state: dict) -> dict:
        """Run workflow with event bridging."""
        # Initialize LangGraph thread
        self._state_adapter.initialize_session(execution_id, initial_state)
        config = self._state_adapter.get_config()
        
        # Execute with event bridging
        result = await self._event_bridge.bridge_execution(
            self._state_adapter.get_compiled_graph(),
            initial_state,
            config,
            execution_id,
        )
        
        # Emit checkpoint audit events
        self._event_bridge.bridge_checkpoint_events(
            self._state_adapter.get_compiled_graph(),
            config,
            execution_id,
        )
        
        return result
```

### Audit Event Persistence

```python
# wtb/infrastructure/events/audit_event_listener.py (updated)

from wtb.infrastructure.events import WTBEventBus
from wtb.domain.events import (
    ExecutionStartedEvent,
    ExecutionCompletedEvent,
    NodeCompletedEvent,
    CheckpointCreatedEvent,
)

class AuditEventListener:
    """
    Listens to WTB events and persists to audit log.
    
    Handles both WTB domain events AND LangGraph-bridged events.
    """
    
    def __init__(self, event_bus: WTBEventBus, audit_repo: IAuditLogRepository):
        self._audit_repo = audit_repo
        
        # Subscribe to events
        event_bus.subscribe("execution_started", self._on_execution_started)
        event_bus.subscribe("execution_completed", self._on_execution_completed)
        event_bus.subscribe("node_completed", self._on_node_completed)
        event_bus.subscribe("checkpoint_created", self._on_checkpoint_created)
    
    def _on_checkpoint_created(self, event: CheckpointCreatedEvent):
        """Record checkpoint creation in audit log."""
        entry = AuditLogEntry(
            event_type="checkpoint_created",
            execution_id=event.execution_id,
            node_id=event.node_id,
            checkpoint_id=str(event.checkpoint_id),
            step=event.step,
            timestamp=datetime.utcnow(),
        )
        self._audit_repo.add(entry)
```

### Transaction Consistency

The integration maintains ACID properties across boundaries:

| Boundary | Consistency Mechanism |
|----------|----------------------|
| **LangGraph → WTB EventBus** | Events bridged in-process; failures don't affect checkpoint |
| **EventBus → AuditRepository** | UoW transaction; audit entry committed atomically |
| **Checkpoint → NodeBoundary** | Separate transactions; eventual consistency via checkpoint_id reference |
| **FileTracker → Checkpoint** | Outbox pattern for cross-DB consistency |

### Stream Mode Selection

```python
# Configure stream modes based on use case

class StreamModeConfig:
    """Configuration for LangGraph stream modes."""
    
    @staticmethod
    def for_testing() -> list[str]:
        """Minimal streaming for unit tests."""
        return ["updates"]
    
    @staticmethod
    def for_development() -> list[str]:
        """Detailed streaming for debugging."""
        return ["values", "updates", "debug", "custom"]
    
    @staticmethod
    def for_production() -> list[str]:
        """Balanced streaming for production audit."""
        return ["updates", "custom"]
    
    @staticmethod
    def for_full_audit() -> list[str]:
        """Complete audit trail."""
        return ["values", "updates", "messages", "debug", "events", "custom"]
```

### Observability Integration

```python
# wtb/infrastructure/observability/langgraph_metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Metrics for LangGraph execution
langgraph_executions_total = Counter(
    "wtb_langgraph_executions_total",
    "Total LangGraph executions",
    ["workflow_id", "status"]
)

langgraph_node_duration_seconds = Histogram(
    "wtb_langgraph_node_duration_seconds",
    "Node execution duration",
    ["workflow_id", "node_id"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

langgraph_checkpoints_total = Counter(
    "wtb_langgraph_checkpoints_total",
    "Total checkpoints created",
    ["workflow_id", "thread_id"]
)

langgraph_active_threads = Gauge(
    "wtb_langgraph_active_threads",
    "Currently active threads"
)

# Integration with event bridge
class MetricsEventListener:
    """Capture LangGraph metrics from events."""
    
    def __init__(self, event_bus: WTBEventBus):
        event_bus.subscribe("execution_started", self._on_start)
        event_bus.subscribe("execution_completed", self._on_complete)
        event_bus.subscribe("node_completed", self._on_node)
        event_bus.subscribe("checkpoint_created", self._on_checkpoint)
    
    def _on_start(self, event):
        langgraph_active_threads.inc()
    
    def _on_complete(self, event):
        langgraph_active_threads.dec()
        langgraph_executions_total.labels(
            workflow_id=event.workflow_id,
            status="completed"
        ).inc()
    
    def _on_node(self, event):
        if event.duration_ms:
            langgraph_node_duration_seconds.labels(
                workflow_id=event.workflow_id,
                node_id=event.node_id
            ).observe(event.duration_ms / 1000)
    
    def _on_checkpoint(self, event):
        langgraph_checkpoints_total.labels(
            workflow_id=event.workflow_id,
            thread_id=event.thread_id
        ).inc()
```

## Related Documents

- [PERSISTENCE.md](./PERSISTENCE.md) - Checkpointer details
- [TIME_TRAVEL.md](./TIME_TRAVEL.md) - History and rollback
- [API_DEPLOYMENT.md](./API_DEPLOYMENT.md) - Deployment options
- [AUDIT_EVENT_SYSTEM.md](./AUDIT_EVENT_SYSTEM.md) - **NEW** Audit & event system details
- [../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md §20](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) - Full architecture
- [../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) - WTB EventBus design
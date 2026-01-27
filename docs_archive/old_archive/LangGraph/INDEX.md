# LangGraph Integration Documentation

**Last Updated:** 2026-01-15

## Overview

LangGraph is the **PRIMARY** state persistence layer for WTB, replacing AgentGit adapter for production use.

## Document Index

| Document | Purpose | Read When |
|----------|---------|-----------|
| [PERSISTENCE.md](./PERSISTENCE.md) | Checkpointers, threads, state snapshots | Understanding state management |
| [TIME_TRAVEL.md](./TIME_TRAVEL.md) | History, replay, fork, update state | Implementing rollback/debugging |
| [API_DEPLOYMENT.md](./API_DEPLOYMENT.md) | Agent Server, LangSmith, REST APIs | Production deployment |
| [WTB_INTEGRATION.md](./WTB_INTEGRATION.md) | LangGraphStateAdapter design | WTB integration work |
| [LANGGRAPH_WTB_INTEGRATION_IMPLEMENTATION.md](./LANGGRAPH_WTB_INTEGRATION_IMPLEMENTATION.md) | 🆕 **✅ IMPLEMENTED - Full integration** | Implementation details (2026-01-15) |
| [AUDIT_EVENT_SYSTEM.md](./AUDIT_EVENT_SYSTEM.md) | Streaming events, tracing, custom events | Audit & observability |
| [CHECKPOINT_GRANULARITY_DESIGN.md](./CHECKPOINT_GRANULARITY_DESIGN.md) | Node vs Tool level design | Architecture decision |
| [DOMAIN_CHECKPOINT_DESIGN.md](./DOMAIN_CHECKPOINT_DESIGN.md) | ✅ **Checkpoint in Domain Layer** | DDD refactoring (IMPLEMENTED) |
| [DDD_VIOLATION_REVIEW.md](./DDD_VIOLATION_REVIEW.md) | ✅ **DDD violations & fix plan** | Code review (RESOLVED) |

## LangGraph Core Components

Based on [LangGraph Reference](https://reference.langchain.com/python/langgraph/):

| Component | Description | Package |
|-----------|-------------|---------|
| **Graphs** | Main graph abstraction (`StateGraph`, `MessageGraph`) | `langgraph` |
| **Functional API** | Functional programming interface for graphs | `langgraph` |
| **Pregel** | Pregel-inspired computation model for parallel execution | `langgraph` |
| **Checkpointing** | Saving and restoring graph state | `langgraph-checkpoint-*` |
| **Storage** | Storage backends (Memory, SQLite, PostgreSQL) | `langgraph-checkpoint-*` |
| **Caching** | Caching mechanisms for performance | `langgraph` |
| **Channels** | Message passing and state reducers | `langgraph` |
| **Types** | Type definitions for graph components | `langgraph` |
| **Runtime** | Runtime configuration and execution | `langgraph` |
| **Config** | Configuration options | `langgraph` |
| **Errors** | Error types and handling | `langgraph` |

### Prebuilt Components

| Component | Description |
|-----------|-------------|
| **Agents** | Built-in agent patterns |
| **Supervisor** | Orchestration and delegation |
| **Swarm** | Multi-agent collaboration |

### Audit & Event System (NEW 2026-01-15)

| Feature | Description | WTB Integration |
|---------|-------------|-----------------|
| **Streaming Events** | `astream_events()` emits lifecycle events | LangGraphEventBridge transforms to WTB events |
| **Checkpoint Audit** | StateSnapshot at each super-step | Implicit audit trail via `get_state_history()` |
| **Tracing** | LangSmith, OpenTelemetry integration | Production observability |
| **Custom Events** | `get_stream_writer()` for app-specific events | Tool progress, metrics |

See [AUDIT_EVENT_SYSTEM.md](./AUDIT_EVENT_SYSTEM.md) for full details.

## Quick Reference

### Why LangGraph over AgentGit?

| Aspect | LangGraph | AgentGit | Winner |
|--------|-----------|----------|--------|
| **Battle-tested** | LangSmith production | Custom implementation | LangGraph |
| **Thread isolation** | Native `thread_id` | Manual session management | LangGraph |
| **Time travel** | Built-in APIs | Custom rollback logic | LangGraph |
| **Backends** | Memory, SQLite, PostgreSQL | SQLite only | LangGraph |
| **Serialization** | JsonPlusSerializer + encryption | Custom JSON | LangGraph |
| **Fault tolerance** | Pending writes preserved | Manual recovery | LangGraph |

### Core Concepts

```
Thread (thread_id)
└── Checkpoints (StateSnapshot at each super-step)
     ├── config: {thread_id, checkpoint_id, checkpoint_ns}
     ├── metadata: {source, writes, step}
     ├── values: State channel values
     ├── next: Tuple of next node names
     └── tasks: PregelTask objects
```

### Checkpoint Granularity (Key Decision)

> **"Super-Step = Node Boundary. There is no finer granularity unless explicitly modeled."**

LangGraph checkpoints at **node (super-step) level**, not tool/message level.
See [CHECKPOINT_GRANULARITY_DESIGN.md](./CHECKPOINT_GRANULARITY_DESIGN.md) for details.

### Checkpointer Selection

| Environment | Checkpointer | Package |
|-------------|--------------|---------|
| Unit Tests | `InMemorySaver` | `langgraph-checkpoint` (bundled) |
| Development | `SqliteSaver` | `langgraph-checkpoint-sqlite` |
| Production | `PostgresSaver` | `langgraph-checkpoint-postgres` |

### Key APIs

```python
# Compile with checkpointer
graph = workflow.compile(checkpointer=checkpointer)

# Execute with thread isolation
config = {"configurable": {"thread_id": "execution-001"}}
result = graph.invoke(initial_state, config)

# Get current state
state = graph.get_state(config)

# Time travel - get history
history = list(graph.get_state_history(config))

# Replay from checkpoint
old_config = {"configurable": {"thread_id": "1", "checkpoint_id": "abc123"}}
old_state = graph.get_state(old_config)

# Update state mid-execution
graph.update_state(config, {"modified": True}, as_node="node_name")
```

## Related Documentation

- [Project_Init/INDEX.md](../Project_Init/INDEX.md) - Main project index
- [Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md §20](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) - LangGraph adapter design
- [Project_Init/PROGRESS_TRACKER.md](../Project_Init/PROGRESS_TRACKER.md) - Implementation status

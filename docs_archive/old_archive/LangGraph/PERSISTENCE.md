# LangGraph Persistence

**Source:** [LangGraph Persistence Documentation](https://docs.langchain.com/oss/python/langgraph/persistence)

## Overview

LangGraph has a built-in persistence layer implemented through **checkpointers**. When you compile a graph with a checkpointer, it saves a checkpoint of the graph state at every **super-step**.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH PERSISTENCE MODEL                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Workflow Graph                                                                  │
│       │                                                                          │
│       │ compile(checkpointer=...)                                               │
│       ▼                                                                          │
│  CompiledStateGraph                                                              │
│       │                                                                          │
│       │ invoke(input, config)                                                   │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           EXECUTION                                      │   │
│  │                                                                          │   │
│  │   START ──► node_a ──► node_b ──► node_c ──► END                       │   │
│  │     │         │          │          │                                    │   │
│  │     ▼         ▼          ▼          ▼                                    │   │
│  │   ┌───┐     ┌───┐      ┌───┐      ┌───┐                                 │   │
│  │   │CP1│     │CP2│      │CP3│      │CP4│   Checkpoint at each super-step │   │
│  │   └───┘     └───┘      └───┘      └───┘                                 │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│                              Checkpointer Storage                               │
│                              (Memory/SQLite/PostgreSQL)                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Threads

A **thread** is a unique ID (`thread_id`) assigned to each checkpoint chain. It contains the accumulated state of a sequence of runs.

```python
# Thread ID is REQUIRED for checkpointer operations
config = {"configurable": {"thread_id": "my-unique-thread-id"}}
result = graph.invoke(input, config)
```

**Key Points:**
- Thread ID is the **primary key** for storing and retrieving checkpoints
- Without it, the checkpointer cannot save state or resume execution
- Each thread has independent checkpoint history
- **WTB Use Case:** One thread per batch test variant execution

### 2. Checkpoints (StateSnapshot)

A **checkpoint** is a snapshot of the graph state saved at each super-step. It's represented by a `StateSnapshot` object:

```python
StateSnapshot(
    # Config associated with this checkpoint
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '...'}},
    
    # Metadata about the checkpoint
    metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b'}}, 'step': 2},
    
    # State channel values at this point
    values={'foo': 'b', 'bar': ['a', 'b']},
    
    # Next nodes to execute (empty if complete)
    next=(),
    
    # PregelTask objects with execution info
    tasks=(),
    
    # Timestamp
    created_at='2024-08-29T19:19:38.821749+00:00',
    
    # Parent checkpoint reference
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_id': '...'}}
)
```

### 3. Checkpointers

Checkpointers are pluggable backends that persist checkpoints. They conform to `BaseCheckpointSaver` interface:

| Method | Purpose |
|--------|---------|
| `.put` | Store checkpoint with config and metadata |
| `.put_writes` | Store intermediate writes (pending writes) |
| `.get_tuple` | Fetch checkpoint for given config |
| `.list` | List checkpoints matching filter criteria |

**Async versions:** `.aput`, `.aput_writes`, `.aget_tuple`, `.alist`

## Checkpointer Libraries

| Library | Class | Use Case | Install |
|---------|-------|----------|---------|
| `langgraph-checkpoint` | `InMemorySaver` | Testing, experimentation | Bundled with LangGraph |
| `langgraph-checkpoint-sqlite` | `SqliteSaver` | Local development | `pip install langgraph-checkpoint-sqlite` |
| `langgraph-checkpoint-postgres` | `PostgresSaver` | Production (LangSmith uses this) | `pip install langgraph-checkpoint-postgres` |

## Usage Examples

### InMemorySaver (Testing)

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated, TypedDict
from operator import add

class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]

def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}

def node_b(state: State):
    return {"foo": "b", "bar": ["b"]}

# Build graph
workflow = StateGraph(State)
workflow.add_node(node_a)
workflow.add_node(node_b)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", "node_b")
workflow.add_edge("node_b", END)

# Compile with checkpointer
checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

# Execute
config = {"configurable": {"thread_id": "1"}}
result = graph.invoke({"foo": "", "bar": []}, config)
# Result: {'foo': 'b', 'bar': ['a', 'b']}
```

### SqliteSaver (Development)

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Create connection
conn = sqlite3.connect("checkpoints.db")
checkpointer = SqliteSaver(conn)

graph = workflow.compile(checkpointer=checkpointer)
```

### PostgresSaver (Production)

```python
from langgraph.checkpoint.postgres import PostgresSaver

# From connection string
checkpointer = PostgresSaver.from_conn_string("postgresql://user:pass@host/db")
checkpointer.setup()  # Create tables if needed

graph = workflow.compile(checkpointer=checkpointer)
```

## Serialization

Checkpointers use serializers to encode/decode state. The default `JsonPlusSerializer` handles:
- LangChain and LangGraph primitives
- Datetimes, enums
- Many standard Python types

### Pickle Fallback

For unsupported types (e.g., Pandas DataFrames):

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

checkpointer = InMemorySaver(
    serde=JsonPlusSerializer(pickle_fallback=True)
)
```

### Encryption

Enable encryption for sensitive state:

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.postgres import PostgresSaver

# Reads LANGGRAPH_AES_KEY environment variable
serde = EncryptedSerializer.from_pycryptodome_aes()
checkpointer = PostgresSaver.from_conn_string("postgresql://...", serde=serde)
```

## Checkpoints After Execution

After running the example graph, exactly **4 checkpoints** are saved:

| Step | Values | Next Node | Description |
|------|--------|-----------|-------------|
| 0 | `{}` | `START` | Empty checkpoint before execution |
| 1 | `{'foo': '', 'bar': []}` | `node_a` | After user input |
| 2 | `{'foo': 'a', 'bar': ['a']}` | `node_b` | After node_a |
| 3 | `{'foo': 'b', 'bar': ['a', 'b']}` | `()` | After node_b (complete) |

## WTB Integration Notes

### Thread ID Strategy

```python
# For single execution
thread_id = f"wtb-{execution_id}"

# For batch test variants
thread_id = f"batch-{batch_test_id}-{variant_id}"
```

### Checkpointer Selection by Environment

```python
from wtb.config import WTBConfig

def create_checkpointer(config: WTBConfig):
    if config.mode == "testing":
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
    elif config.mode == "development":
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        return SqliteSaver(sqlite3.connect(config.checkpoint_db_path))
    else:  # production
        from langgraph.checkpoint.postgres import PostgresSaver
        saver = PostgresSaver.from_conn_string(config.checkpoint_db_url)
        saver.setup()
        return saver
```

## Related Documents

- [TIME_TRAVEL.md](./TIME_TRAVEL.md) - Get state history, replay, fork
- [API_DEPLOYMENT.md](./API_DEPLOYMENT.md) - LangSmith deployment
- [WTB_INTEGRATION.md](./WTB_INTEGRATION.md) - WTB adapter design

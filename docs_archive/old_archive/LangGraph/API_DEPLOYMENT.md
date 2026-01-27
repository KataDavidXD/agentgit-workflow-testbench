# LangGraph API & Deployment

**Sources:** 
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)

## Overview

LangGraph provides multiple deployment options from local development to production-scale deployments via LangSmith.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT OPTIONS                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  LOCAL DEVELOPMENT                                                               │
│  ═════════════════                                                               │
│  • Direct Python API                                                             │
│  • InMemorySaver / SqliteSaver                                                  │
│  • graph.invoke(), graph.stream()                                               │
│                                                                                  │
│  LANGGRAPH SERVER (Self-Hosted)                                                 │
│  ═══════════════════════════════                                                │
│  • REST API endpoints                                                            │
│  • Built-in persistence                                                          │
│  • Thread management                                                             │
│  • Human-in-the-loop support                                                     │
│                                                                                  │
│  LANGSMITH (Managed)                                                             │
│  ════════════════════                                                            │
│  • Production deployment                                                         │
│  • Observability & tracing                                                       │
│  • Automatic checkpointing                                                       │
│  • Agent Chat UI                                                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Local Development API

### Core Methods

| Method | Description |
|--------|-------------|
| `graph.invoke(input, config)` | Execute graph synchronously |
| `graph.ainvoke(input, config)` | Execute graph asynchronously |
| `graph.stream(input, config)` | Stream execution events |
| `graph.astream(input, config)` | Stream events asynchronously |
| `graph.get_state(config)` | Get current state |
| `graph.get_state_history(config)` | Get checkpoint history |
| `graph.update_state(config, values)` | Update state |

### Execution Example

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict

class State(TypedDict):
    messages: list
    current_step: str

# Build graph
workflow = StateGraph(State)
workflow.add_node("agent", agent_node)
workflow.add_node("tool", tool_node)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tool", "agent")

# Compile with persistence
checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

# Execute
config = {"configurable": {"thread_id": "user-123"}}
result = graph.invoke({"messages": ["Hello"], "current_step": ""}, config)

# Stream execution
for event in graph.stream({"messages": ["Hello"]}, config, stream_mode="updates"):
    print(event)
```

### Streaming Modes

| Mode | Description |
|------|-------------|
| `"values"` | Full state after each step |
| `"updates"` | Only the updates from each node |
| `"messages"` | LLM message tokens as they're generated |

## LangGraph Server

When using the **Agent Server**, checkpointing is handled automatically.

### Server Configuration (`langgraph.json`)

```json
{
    "dependencies": ["."],
    "graphs": {
        "agent": "./agent.py:graph"
    },
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

### REST API Endpoints

The Agent Server exposes REST endpoints for graph operations:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/threads` | POST | Create a new thread |
| `/threads/{thread_id}` | GET | Get thread state |
| `/threads/{thread_id}/state` | GET | Get current state |
| `/threads/{thread_id}/state` | POST | Update state |
| `/threads/{thread_id}/history` | GET | Get state history |
| `/runs` | POST | Execute graph run |
| `/runs/{run_id}` | GET | Get run status |
| `/runs/{run_id}/stream` | GET | Stream run events |

### Thread Management API

```python
# Using LangGraph SDK
from langgraph_sdk import get_client

client = get_client(url="http://localhost:8000")

# Create thread
thread = await client.threads.create()

# Get thread state
state = await client.threads.get_state(thread["thread_id"])

# Update state
await client.threads.update_state(
    thread["thread_id"],
    values={"messages": [{"role": "user", "content": "modified"}]}
)

# Get history
history = await client.threads.get_history(thread["thread_id"])

# Create run
run = await client.runs.create(
    thread["thread_id"],
    assistant_id="agent",
    input={"messages": [{"role": "user", "content": "Hello"}]}
)

# Stream run
async for event in client.runs.stream(
    thread["thread_id"],
    assistant_id="agent",
    input={"messages": [{"role": "user", "content": "Hello"}]}
):
    print(event)
```

## LangSmith Deployment

### Configuration

```json
{
    "dependencies": ["."],
    "graphs": {
        "agent": "./agent.py:graph"
    },
    "env": ".env",
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

### Automatic Persistence

When deployed to LangSmith:
- Checkpointing is **automatic** - no manual configuration needed
- PostgreSQL backend used automatically
- Encryption available via `LANGGRAPH_AES_KEY` environment variable

### Observability

LangSmith provides:
- Execution traces
- Token usage tracking
- Latency metrics
- Error tracking
- Cost analysis

## Memory Store

LangGraph supports a persistent **Memory Store** for cross-thread data:

### Basic Usage

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# Store data
store.put(("user", "123", "preferences"), "theme", {"value": "dark"})

# Retrieve data
item = store.get(("user", "123", "preferences"), "theme")
print(item.value)  # {"value": "dark"}

# Search
results = store.search(("user", "123", "preferences"))
```

### Semantic Search

```python
# Configure in langgraph.json for semantic search
{
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}

# Search by semantic similarity
memories = store.search(
    ("user_id", "memories"),
    query="What do I like?",
    limit=3
)
```

### Using Store in Nodes

```python
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig

def call_model(state: State, config: RunnableConfig, *, store: BaseStore):
    user_id = config["configurable"]["user_id"]
    namespace = (user_id, "memories")
    
    # Search memories
    memories = store.search(
        namespace,
        query=state["messages"][-1].content,
        limit=3
    )
    
    # Use memories in response
    info = "\n".join([d.value["memory"] for d in memories])
    # ... use info in model call
```

## WTB Deployment Strategy

### Development Mode

```python
# Local development with SQLite
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

conn = sqlite3.connect("data/wtb_checkpoints.db")
checkpointer = SqliteSaver(conn)
graph = workflow.compile(checkpointer=checkpointer)

# Direct API usage
config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
result = graph.invoke(initial_state, config)
```

### Production Mode (Ray + PostgreSQL)

```python
# Production with PostgreSQL + Ray actors
from langgraph.checkpoint.postgres import PostgresSaver

# Each Ray actor creates its own checkpointer
@ray.remote
class VariantExecutionActor:
    def __init__(self, db_url: str):
        self._checkpointer = PostgresSaver.from_conn_string(db_url)
        self._checkpointer.setup()
        self._graph = None
    
    def set_graph(self, graph):
        self._graph = graph.compile(checkpointer=self._checkpointer)
    
    def execute(self, variant_id: str, initial_state: dict):
        config = {"configurable": {"thread_id": f"variant-{variant_id}"}}
        return self._graph.invoke(initial_state, config)
```

### REST API Wrapper (Optional)

If exposing WTB as a service:

```python
from fastapi import FastAPI
from langgraph.checkpoint.postgres import PostgresSaver

app = FastAPI()
checkpointer = PostgresSaver.from_conn_string(DB_URL)
graph = workflow.compile(checkpointer=checkpointer)

@app.post("/executions/{execution_id}/run")
async def run_execution(execution_id: str, initial_state: dict):
    config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
    result = await graph.ainvoke(initial_state, config)
    return {"result": result}

@app.get("/executions/{execution_id}/state")
async def get_state(execution_id: str):
    config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
    state = graph.get_state(config)
    return {"values": state.values, "next": state.next}

@app.get("/executions/{execution_id}/history")
async def get_history(execution_id: str):
    config = {"configurable": {"thread_id": f"wtb-{execution_id}"}}
    history = list(graph.get_state_history(config))
    return {"checkpoints": [
        {"checkpoint_id": s.config["configurable"]["checkpoint_id"],
         "step": s.metadata.get("step"),
         "values": s.values}
        for s in history
    ]}

@app.post("/executions/{execution_id}/rollback")
async def rollback(execution_id: str, checkpoint_id: str):
    config = {
        "configurable": {
            "thread_id": f"wtb-{execution_id}",
            "checkpoint_id": checkpoint_id
        }
    }
    state = graph.get_state(config)
    return {"restored_state": state.values}
```

## Fault Tolerance

### Pending Writes

When a node fails mid-execution, LangGraph preserves **pending writes** from successful nodes:

```
Execution: node_a → node_b → node_c (fails) → node_d
           ✓         ✓         ✗

Pending writes from node_a and node_b are saved.
On resume, only node_c and node_d need to re-run.
```

### Automatic Retry (Ray)

```python
@ray.remote(max_retries=3)
class VariantExecutionActor:
    def execute(self, ...):
        # Automatic retry on failure
        # LangGraph checkpoints preserve progress
        pass
```

## Related Documents

- [PERSISTENCE.md](./PERSISTENCE.md) - Checkpointer setup
- [TIME_TRAVEL.md](./TIME_TRAVEL.md) - History and rollback
- [WTB_INTEGRATION.md](./WTB_INTEGRATION.md) - WTB adapter design

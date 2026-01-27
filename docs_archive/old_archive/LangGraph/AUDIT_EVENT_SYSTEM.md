# LangGraph Audit & Event System

**Last Updated:** 2026-01-15

**Sources:**
- [LangGraph Persistence Documentation](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Observability](https://docs.langchain.com/oss/javascript/langgraph/observability)
- [LangSmith Tracing](https://blog.langchain.com/end-to-end-opentelemetry-langsmith)
- [Judgeval Integration](https://docs.judgmentlabs.ai/documentation/tracing/integrations/langgraph)

## Overview

LangGraph provides comprehensive audit and event system capabilities through multiple mechanisms:

1. **Checkpointing** - State snapshots at each super-step (implicit audit trail)
2. **Streaming Events** - Real-time event emission during execution
3. **Tracing Integration** - LangSmith, OpenTelemetry, Judgeval callbacks
4. **Custom Events** - Application-specific event emission via `get_stream_writer()`

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH AUDIT & EVENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Graph Execution                                                                 │
│       │                                                                          │
│       ├─────────────────────────────────────────────────────────────────────────│
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         EVENT EMISSION LAYER                             │   │
│  │                                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │  Streaming  │  │ Checkpoint  │  │   Tracing   │  │   Custom    │    │   │
│  │  │   Events    │  │   Events    │  │  Callbacks  │  │   Events    │    │   │
│  │  │             │  │             │  │             │  │             │    │   │
│  │  │ • values    │  │ • state     │  │ • LangSmith │  │ • stream_   │    │   │
│  │  │ • updates   │  │ • metadata  │  │ • OTEL      │  │   writer()  │    │   │
│  │  │ • messages  │  │ • writes    │  │ • Judgeval  │  │ • progress  │    │   │
│  │  │ • debug     │  │ • tasks     │  │ • custom    │  │ • custom    │    │   │
│  │  │ • events    │  │             │  │             │  │             │    │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │   │
│  └─────────┼────────────────┼────────────────┼────────────────┼───────────┘   │
│            │                │                │                │                │
│            ▼                ▼                ▼                ▼                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         AUDIT CONSUMERS                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │WTB EventBus │  │ PostgreSQL  │  │  LangSmith  │  │   Grafana   │    │   │
│  │  │(Internal)   │  │ Checkpoints │  │  Platform   │  │   Loki      │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 1. Streaming Events

LangGraph provides multiple streaming modes for real-time event capture during graph execution.

### Stream Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `values` | Full state after each node | State tracking |
| `updates` | Delta changes per node | Efficient audit |
| `messages` | LLM tokens as they stream | UI streaming |
| `debug` | Detailed internal events | Debugging |
| `events` | Lifecycle events (v2 API) | **Audit trails** |
| `custom` | User-defined events | Application-specific |

### Usage: `stream()` and `astream()`

```python
from langgraph.graph import StateGraph

# Synchronous streaming
for event in graph.stream(initial_state, config, stream_mode="updates"):
    print(f"Node: {event}")

# Async streaming
async for event in graph.astream(initial_state, config, stream_mode="events"):
    await process_event(event)

# Multiple stream modes
for event in graph.stream(
    initial_state, 
    config, 
    stream_mode=["values", "updates", "debug"]
):
    # event is a tuple: (mode, data)
    mode, data = event
```

### Event Types in `stream_mode="events"` (astream_events v2)

| Event Type | When Emitted | Data Included |
|------------|--------------|---------------|
| `on_chain_start` | Graph/node execution starts | run_id, name, inputs, metadata |
| `on_chain_end` | Graph/node execution ends | run_id, name, outputs |
| `on_chain_error` | Execution error | run_id, name, error |
| `on_chat_model_start` | LLM invocation starts | run_id, model, messages |
| `on_chat_model_stream` | LLM token generated | run_id, chunk |
| `on_chat_model_end` | LLM invocation ends | run_id, response |
| `on_tool_start` | Tool execution starts | run_id, tool, inputs |
| `on_tool_end` | Tool execution ends | run_id, tool, outputs |
| `on_tool_error` | Tool error | run_id, tool, error |
| `on_retriever_start` | Retriever query starts | run_id, query |
| `on_retriever_end` | Retriever returns | run_id, documents |

### Example: Audit Event Capture

```python
async def capture_audit_events(graph, initial_state, config, audit_store):
    """Capture all lifecycle events for audit trail."""
    async for event in graph.astream_events(initial_state, config, version="v2"):
        audit_entry = {
            "run_id": event.get("run_id"),
            "parent_run_id": event.get("parent_run_id"),
            "event_type": event["event"],
            "name": event.get("name"),
            "timestamp": datetime.utcnow().isoformat(),
            "data": event.get("data"),
            "metadata": event.get("metadata"),
            "tags": event.get("tags", []),
        }
        await audit_store.append(audit_entry)
```

## 2. Checkpoint-Based Audit Trail

LangGraph checkpoints provide an implicit audit trail - every super-step is recorded.

### StateSnapshot as Audit Record

```python
from langgraph.checkpoint.memory import InMemorySaver

# After execution, retrieve full history
config = {"configurable": {"thread_id": "execution-001"}}

# Get complete audit history
for snapshot in graph.get_state_history(config):
    audit_record = {
        "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
        "step": snapshot.metadata.get("step"),
        "source": snapshot.metadata.get("source"),  # "loop" or "input"
        "writes": snapshot.metadata.get("writes", {}),  # Which nodes wrote
        "state_values": snapshot.values,
        "next_nodes": snapshot.next,
        "created_at": snapshot.created_at,
        "parent_checkpoint": snapshot.parent_config,
    }
    print(f"Step {audit_record['step']}: {audit_record['writes'].keys()}")
```

### Checkpoint Metadata Schema

| Field | Type | Description |
|-------|------|-------------|
| `step` | int | Super-step number |
| `source` | str | "input" or "loop" |
| `writes` | dict | `{node_name: output_values}` |
| `checkpoint_ns` | str | Namespace (for subgraphs) |
| `checkpoint_id` | str | Unique checkpoint identifier |
| `parent_checkpoint_id` | str | Chain reference |
| `created_at` | str | ISO timestamp |

### Pending Writes (Fault Tolerance)

```python
# When a node fails mid-super-step, pending writes are preserved
StateSnapshot(
    # ...
    metadata={
        'source': 'loop',
        'writes': {'node_a': {'result': 'ok'}},  # Completed node
        'pending_writes': [  # Failed node's partial writes
            ('node_b', 'channel_name', partial_value),
        ],
    },
    tasks=(
        PregelTask(id='task-123', name='node_b', path=('__pregel_pull', 'node_b')),
    ),
)
```

## 3. Tracing Integration

### LangSmith Tracing

```python
import os

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "lsv2_..."
os.environ["LANGCHAIN_PROJECT"] = "wtb-executions"

# All graph executions are now traced to LangSmith
result = graph.invoke(initial_state, config)
```

### OpenTelemetry Integration

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from langsmith.tracing import otel_exporter

# Configure OpenTelemetry
provider = TracerProvider()
provider.add_span_processor(otel_exporter.LangSmithSpanProcessor())
trace.set_tracer_provider(provider)

# Now traces go to both OTEL backend and LangSmith
```

### Judgeval Callback Handler

```python
from judgeval import JudgevalCallbackHandler

# Create handler for detailed tracing
handler = JudgevalCallbackHandler(
    api_key="...",
    trace_attributes={
        "workflow_id": "wtb-workflow-001",
        "batch_test_id": "batch-123",
    }
)

# Pass to graph execution
config = {
    "configurable": {"thread_id": "1"},
    "callbacks": [handler]
}
result = graph.invoke(initial_state, config)
```

## 4. Custom Events via Stream Writer

For application-specific audit events within nodes or tools:

```python
from langgraph.config import get_stream_writer

def my_node(state):
    """Node with custom event emission."""
    writer = get_stream_writer()
    
    # Emit progress event
    writer({"type": "progress", "percent": 0, "message": "Starting..."})
    
    # Do work
    result = process_data(state["input"])
    
    # Emit completion event with metrics
    writer({
        "type": "node_metrics",
        "node_id": "my_node",
        "duration_ms": 150,
        "tokens_used": 1200,
        "cost": 0.05,
    })
    
    return {"result": result}

# Consume custom events
for mode, data in graph.stream(state, config, stream_mode=["updates", "custom"]):
    if mode == "custom":
        audit_store.record_custom_event(data)
```

## 5. ACID Properties in LangGraph Events

### How LangGraph Upholds ACID

| Property | LangGraph Implementation |
|----------|-------------------------|
| **Atomicity** | Super-step transactions: all nodes in a super-step commit together or none do. Pending writes preserved on failure. |
| **Consistency** | State schema enforced via TypedDict/Pydantic. Reducers ensure valid state transitions. Checkpoint validates schema. |
| **Isolation** | Thread-based isolation: each `thread_id` has independent checkpoint chain. Concurrent executions don't interfere. |
| **Durability** | Checkpoints persisted to PostgreSQL/SQLite. Encryption via `LANGGRAPH_AES_KEY`. WAL mode for concurrent access. |

### Super-Step Atomicity

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SUPER-STEP TRANSACTION BOUNDARY                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Super-Step N                                                                    │
│  ════════════                                                                    │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  PARALLEL NODE EXECUTION                                                   │ │
│  │                                                                             │ │
│  │  node_a ─────────► success ──┐                                             │ │
│  │                              │                                             │ │
│  │  node_b ─────────► success ──┼──► ALL SUCCESS ──► CHECKPOINT COMMITTED    │ │
│  │                              │                                             │ │
│  │  node_c ─────────► success ──┘                                             │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  FAILURE SCENARIO                                                          │ │
│  │                                                                             │ │
│  │  node_a ─────────► success ──┐                                             │ │
│  │                              │                                             │ │
│  │  node_b ─────────► FAILURE ──┼──► ANY FAILURE ──► PENDING WRITES SAVED    │ │
│  │                              │                    (No checkpoint commit)   │ │
│  │  node_c ─────────► success ──┘                                             │ │
│  │                                                                             │ │
│  │  On Resume: Only node_b re-executes; node_a/c outputs restored             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Event Schema for WTB Integration

### Standardized Audit Event Schema

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class AuditEventType(Enum):
    """LangGraph-aligned audit event types."""
    # Execution lifecycle
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    
    # Node lifecycle
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    
    # Checkpoint lifecycle
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    
    # Tool lifecycle
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    
    # LLM lifecycle
    LLM_STARTED = "llm_started"
    LLM_COMPLETED = "llm_completed"
    LLM_STREAMED = "llm_streamed"
    
    # Custom
    CUSTOM_EVENT = "custom_event"
    PROGRESS_UPDATE = "progress_update"


@dataclass
class LangGraphAuditEvent:
    """
    Standardized audit event structure for LangGraph integration.
    
    Maps to both LangGraph streaming events and WTB audit requirements.
    """
    # Identity
    event_id: str                       # Unique event ID
    event_type: AuditEventType          # Event type
    
    # Context
    thread_id: str                      # LangGraph thread_id (= WTB execution_id)
    run_id: str                         # LangGraph run_id
    parent_run_id: Optional[str]        # Parent run for nested calls
    
    # Timing
    timestamp: datetime
    duration_ms: Optional[int] = None
    
    # Location
    node_id: Optional[str] = None       # Node name
    checkpoint_id: Optional[str] = None # Checkpoint ID
    step: Optional[int] = None          # Super-step number
    
    # Content
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    
    # Metrics
    metrics: Optional[Dict[str, float]] = None  # tokens, cost, latency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "node_id": self.node_id,
            "checkpoint_id": self.checkpoint_id,
            "step": self.step,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "error": self.error,
            "metadata": self.metadata,
            "tags": self.tags,
            "metrics": self.metrics,
        }
```

## 7. Best Practices

### SOLID Alignment

| Principle | Application |
|-----------|-------------|
| **SRP** | Separate event emission (streaming) from event storage (audit store). Nodes focus on logic, not logging. |
| **OCP** | Extend via custom events without modifying core graph. Add new event types via stream_writer. |
| **LSP** | Checkpointers are substitutable (InMemory ↔ SQLite ↔ PostgreSQL). Event handlers are swappable. |
| **ISP** | Choose stream modes needed (don't subscribe to all). Callbacks are optional. |
| **DIP** | Depend on `BaseCheckpointSaver` interface, not concrete implementation. Inject tracing handlers. |

### Event Capture Guidelines

1. **Capture at Boundaries**: Record events at node entry/exit, not within business logic
2. **Include Context**: Always include thread_id, checkpoint_id, step number
3. **Separate Concerns**: Don't mix audit logging with business logic
4. **Idempotent Storage**: Handle duplicate events gracefully
5. **Mask Sensitive Data**: Use anonymizers for PII in traces

### Production Considerations

```python
# Production configuration
import os

# Enable encryption for checkpoints
os.environ["LANGGRAPH_AES_KEY"] = "your-32-byte-key-here..."

# Configure LangSmith for production
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "wtb-production"

# Use PostgreSQL checkpointer with connection pooling
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(
    os.getenv("CHECKPOINT_DB_URL"),
    serde=EncryptedSerializer.from_pycryptodome_aes(),
)
checkpointer.setup()
```

## 8. Comparison: LangGraph Events vs WTB EventBus

| Aspect | LangGraph Events | WTB EventBus |
|--------|------------------|--------------|
| **Scope** | Graph execution events | WTB domain events |
| **Transport** | Stream iterator / callbacks | In-process pub-sub |
| **Persistence** | Via checkpointer or tracing | Via AuditLogRepository |
| **Event Types** | Chain, tool, LLM, custom | Execution, node, checkpoint |
| **Integration** | Primary source | Consumer of LangGraph events |

### Bridge Pattern

```python
from wtb.infrastructure.events import WTBEventBus
from wtb.domain.events import NodeCompletedEvent

class LangGraphEventBridge:
    """
    Bridge LangGraph streaming events to WTB EventBus.
    
    Transforms LangGraph events into WTB domain events.
    """
    
    def __init__(self, event_bus: WTBEventBus):
        self._event_bus = event_bus
    
    async def consume_events(self, graph, initial_state, config):
        """Consume LangGraph events and publish to WTB EventBus."""
        async for event in graph.astream_events(initial_state, config, version="v2"):
            wtb_event = self._transform(event)
            if wtb_event:
                self._event_bus.publish(wtb_event)
    
    def _transform(self, lg_event: dict):
        """Transform LangGraph event to WTB event."""
        event_type = lg_event["event"]
        
        if event_type == "on_chain_end":
            # Node completed → NodeCompletedEvent
            return NodeCompletedEvent(
                execution_id=lg_event["metadata"].get("thread_id"),
                node_id=lg_event["name"],
                outputs=lg_event["data"].get("output"),
                duration_ms=lg_event.get("duration_ms"),
            )
        # ... other transformations
        return None
```

## Related Documents

- [PERSISTENCE.md](./PERSISTENCE.md) - Checkpointer details
- [TIME_TRAVEL.md](./TIME_TRAVEL.md) - History and rollback
- [WTB_INTEGRATION.md](./WTB_INTEGRATION.md) - WTB adapter design
- [../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) - WTB EventBus

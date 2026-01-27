# LangGraph Time Travel

**Source:** [LangGraph Persistence Documentation](https://docs.langchain.com/oss/python/langgraph/persistence)

## Overview

Checkpointers enable **time travel** - the ability to replay prior graph executions, review/debug specific steps, and fork the graph state at arbitrary checkpoints.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TIME TRAVEL CAPABILITIES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CHECKPOINT HISTORY                                                              │
│  ══════════════════                                                              │
│                                                                                  │
│  CP1 ──► CP2 ──► CP3 ──► CP4 (current)                                         │
│   │       │       │       │                                                      │
│   │       │       │       └── get_state(config) → Current state                 │
│   │       │       │                                                              │
│   │       │       └── get_state({..., checkpoint_id: "cp3"}) → State at CP3    │
│   │       │                                                                      │
│   │       └── Fork: Create new execution branch from CP2                        │
│   │                                                                              │
│   └── Replay: Re-execute from CP1 with modified input                           │
│                                                                                  │
│  KEY OPERATIONS:                                                                 │
│  • get_state(config) - Get current or specific checkpoint                       │
│  • get_state_history(config) - Get all checkpoints (most recent first)          │
│  • update_state(config, values, as_node) - Modify state mid-execution           │
│  • invoke with checkpoint_id - Replay from checkpoint                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Get State

### Get Latest State

```python
# Get the latest state snapshot
config = {"configurable": {"thread_id": "1"}}
state = graph.get_state(config)

print(state.values)      # Current state values
print(state.next)        # Next nodes to execute (empty if complete)
print(state.metadata)    # Checkpoint metadata
print(state.config)      # Config with checkpoint_id
```

### Get State at Specific Checkpoint

```python
# Get state at a specific checkpoint
config = {
    "configurable": {
        "thread_id": "1",
        "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"
    }
}
state = graph.get_state(config)
```

## Get State History

Retrieve the full history of checkpoints for a thread:

```python
config = {"configurable": {"thread_id": "1"}}
history = list(graph.get_state_history(config))

# History is ordered chronologically (most recent FIRST)
for snapshot in history:
    print(f"Step {snapshot.metadata['step']}: {snapshot.values}")
    print(f"  Next: {snapshot.next}")
    print(f"  Checkpoint ID: {snapshot.config['configurable']['checkpoint_id']}")
```

### Example Output

```python
[
    StateSnapshot(
        values={'foo': 'b', 'bar': ['a', 'b']},
        next=(),
        config={'configurable': {'thread_id': '1', 'checkpoint_id': '...abc'}},
        metadata={'source': 'loop', 'writes': {'node_b': {...}}, 'step': 2},
    ),
    StateSnapshot(
        values={'foo': 'a', 'bar': ['a']},
        next=('node_b',),
        config={'configurable': {'thread_id': '1', 'checkpoint_id': '...def'}},
        metadata={'source': 'loop', 'writes': {'node_a': {...}}, 'step': 1},
    ),
    StateSnapshot(
        values={'foo': '', 'bar': []},
        next=('node_a',),
        config={'configurable': {'thread_id': '1', 'checkpoint_id': '...ghi'}},
        metadata={'source': 'input', 'writes': None, 'step': 0},
    ),
    # ... initial checkpoint
]
```

## Replay from Checkpoint

To replay execution from a prior checkpoint:

```python
# 1. Get historical checkpoint
history = list(graph.get_state_history(config))
target_checkpoint = history[2]  # Pick a checkpoint to replay from

# 2. Get the checkpoint_id
checkpoint_id = target_checkpoint.config["configurable"]["checkpoint_id"]

# 3. Create config with checkpoint_id
replay_config = {
    "configurable": {
        "thread_id": "1",
        "checkpoint_id": checkpoint_id
    }
}

# 4. Resume execution from that checkpoint
result = graph.invoke(None, replay_config)
```

## Update State

Modify state mid-execution (useful for human-in-the-loop workflows):

```python
config = {"configurable": {"thread_id": "1"}}

# Update specific values
graph.update_state(
    config,
    {"foo": "modified_value"},
    as_node="node_name"  # Optional: attribute update to specific node
)
```

### Update State Parameters

| Parameter | Description |
|-----------|-------------|
| `config` | Thread config (required) |
| `values` | New state values to merge |
| `as_node` | Optional: Node to attribute the update to |

### Use Cases

1. **Human-in-the-loop**: User reviews and modifies intermediate results
2. **Debugging**: Fix incorrect state before resuming
3. **Testing**: Inject specific state for testing scenarios

## Fork from Checkpoint

Create a new execution branch from an arbitrary checkpoint:

```python
# 1. Get checkpoint to fork from
config = {"configurable": {"thread_id": "1"}}
history = list(graph.get_state_history(config))
fork_point = history[2]

# 2. Create new thread with forked state
fork_config = {
    "configurable": {
        "thread_id": "forked-thread-123",  # NEW thread ID
        "checkpoint_id": fork_point.config["configurable"]["checkpoint_id"]
    }
}

# 3. Start execution on new thread
# The new thread starts with the forked state
result = graph.invoke(None, fork_config)
```

## WTB Integration: Rollback Implementation

### Node-Level Rollback

```python
class LangGraphStateAdapter:
    def rollback_to_node(self, node_id: str) -> dict:
        """Rollback to completion of specified node."""
        config = self.get_config()
        
        # Find checkpoint where node completed
        for snapshot in self._graph.get_state_history(config):
            # Check if this checkpoint is node exit
            writes = snapshot.metadata.get('writes', {})
            if node_id in writes:
                # Found the checkpoint where node_id completed
                return self._restore_to_checkpoint(
                    snapshot.config["configurable"]["checkpoint_id"]
                )
        
        raise ValueError(f"Node {node_id} not found in history")
    
    def _restore_to_checkpoint(self, checkpoint_id: str) -> dict:
        """Restore state from checkpoint."""
        config = {
            "configurable": {
                "thread_id": self._current_thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
        snapshot = self._graph.get_state(config)
        return snapshot.values
```

### Tool-Level Rollback

```python
def rollback_to_tool(self, tool_name: str) -> dict:
    """Rollback to after specific tool execution."""
    config = self.get_config()
    
    for snapshot in self._graph.get_state_history(config):
        # Check tool invocation in metadata
        writes = snapshot.metadata.get('writes', {})
        for node_writes in writes.values():
            if isinstance(node_writes, dict):
                tool_calls = node_writes.get('tool_calls', [])
                for call in tool_calls:
                    if call.get('name') == tool_name:
                        return self._restore_to_checkpoint(
                            snapshot.config["configurable"]["checkpoint_id"]
                        )
    
    raise ValueError(f"Tool {tool_name} not found in history")
```

## Batch Test: Fork for Variants

```python
class RayBatchTestRunner:
    def _create_variant_fork(
        self, 
        base_thread_id: str,
        variant_id: str,
        checkpoint_id: str
    ) -> str:
        """Create forked thread for variant execution."""
        fork_thread_id = f"{base_thread_id}-variant-{variant_id}"
        
        # Fork config inherits checkpoint state
        fork_config = {
            "configurable": {
                "thread_id": fork_thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
        
        # Initialize fork (this copies the checkpoint to new thread)
        self._graph.get_state(fork_config)
        
        return fork_thread_id
```

## Debugging with Time Travel

### Inspect Execution Path

```python
def debug_execution(graph, thread_id: str):
    """Print execution path with state changes."""
    config = {"configurable": {"thread_id": thread_id}}
    
    print("=== EXECUTION HISTORY (newest first) ===\n")
    
    for i, snapshot in enumerate(graph.get_state_history(config)):
        step = snapshot.metadata.get('step', '?')
        source = snapshot.metadata.get('source', '?')
        writes = snapshot.metadata.get('writes', {})
        
        print(f"--- Step {step} ({source}) ---")
        print(f"Checkpoint ID: {snapshot.config['configurable']['checkpoint_id'][:20]}...")
        print(f"Next nodes: {snapshot.next}")
        print(f"Writes: {list(writes.keys())}")
        print(f"Values: {snapshot.values}")
        print()
```

### Compare States

```python
def compare_states(graph, thread_id: str, cp_id_1: str, cp_id_2: str):
    """Compare state between two checkpoints."""
    config_1 = {"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id_1}}
    config_2 = {"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id_2}}
    
    state_1 = graph.get_state(config_1).values
    state_2 = graph.get_state(config_2).values
    
    all_keys = set(state_1.keys()) | set(state_2.keys())
    
    print("=== STATE COMPARISON ===")
    for key in sorted(all_keys):
        val_1 = state_1.get(key, "<missing>")
        val_2 = state_2.get(key, "<missing>")
        changed = "✓" if val_1 != val_2 else " "
        print(f"[{changed}] {key}: {val_1} → {val_2}")
```

## Related Documents

- [PERSISTENCE.md](./PERSISTENCE.md) - Checkpointer setup
- [API_DEPLOYMENT.md](./API_DEPLOYMENT.md) - Production deployment
- [WTB_INTEGRATION.md](./WTB_INTEGRATION.md) - WTB adapter design

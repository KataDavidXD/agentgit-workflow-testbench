# Infrastructure Test Summary

## Overview

This document summarizes the infrastructure tests for AgentGit v2 and FileTracker, providing verified capabilities and integration patterns for the Workflow Test Bench (WTB).

| Test Suite | Tests | Status | Purpose |
|------------|-------|--------|---------|
| `test_agentgit_v2.py` | 94 | ✅ All Pass | Checkpoint, Session, Audit, Rollback infrastructure |
| `test_file_processing.py` | 40+ | ✅ All Pass | Content-addressable storage, Commit/Memento pattern |

---

## AgentGit v2 Test Coverage

### 1. Checkpoint System
- **Checkpoint model**: creation, serialization (to_dict/from_dict), metadata storage
- **CheckpointRepository**: CRUD operations, get_by_internal_session, update_metadata
- **Dual Granularity**:
  - `node` checkpoints: Created at workflow node boundaries
  - `tool_message` checkpoints: Fine-grained within nodes, linked via `parent_checkpoint_id`

### 2. Session Management
- **InternalSession**: state management, conversation history, is_current tracking
- **InternalSession_mdp**: MDP extensions (current_node_id, workflow_variables, execution_path)
- **Session Hierarchy**: parent_session_id for branching, lineage tracking
- **ExternalSession**: User-facing container, branch counting, internal session management
- **Isolation**: Sessions properly isolated across external sessions

### 3. Branching & Rollback
- `InternalSession_mdp.create_branch_from_checkpoint()` creates new session from any checkpoint
- Rollback preserves: checkpoint state, parent lineage, branch_point_checkpoint_id
- Supports both node-level and tool/message-level rollback

### 4. Tool Management
- **ToolManager**: invocation recording, track position, statistics
- **ToolRollbackRegistry**: 
  - `ToolSpec` with forward + optional reverse functions
  - `rollback()`: Executes reverse functions in LIFO order
  - `redo()`: Re-executes forward functions
  - Checkpoint tools automatically skipped during rollback

### 5. Audit Trail System
- **AuditEvent**: timestamp, event_type, severity, message, details, error, duration_ms
- **EventTypes**: TOOL_START, TOOL_SUCCESS, TOOL_ERROR, AGENT_DECISION, LLM_CALL, CHECKPOINT_CREATED, ROLLBACK
- **AuditTrail**: Event collection, filtering (get_errors, get_tool_events), statistics (get_summary)
- **Integration**: Store in checkpoint.metadata["audit_trail"] for rollback recovery

### 6. Event Bus
- Pub/sub pattern for domain events
- Multiple subscribers per event type
- Event history tracking
- Ready for WTB event extension

### 7. Workflow Graph
- Node/Edge structure with entry_point
- get_outgoing_edges() for traversal
- NodeManager for MDP state orchestration

---

## FileTracker Test Coverage

### 1. Content-Addressable Storage
- SHA-256 hashing with automatic deduplication
- Storage structure: `objects/{hash[:2]}/{hash[2:]}` (Git-like sharding)
- BlobORM: save, get, exists, delete operations

### 2. Commit & FileMemento
- **Commit**: commit_id (UUID), timestamp, message, list of mementos
- **FileMemento**: file_path, file_hash, file_size (immutable snapshot)
- Multiple files per commit supported

### 3. Branching Scenarios
- Same path with different content: Each version stored with unique hash
- Identical content across branches: Deduplicated (same hash)
- All branch states independently restorable

---

## Critical Integration Patterns for WTB

### Database Architecture (Option B - Anti-Corruption Layer)

```
AgentGit Database (UNCHANGED)     WTB Database (NEW)           FileTracker (UNCHANGED)
═══════════════════════════      ═══════════════════          ═════════════════════════
agentgit.db                       wtb.db                       filetracker (PostgreSQL)

users                             wtb_node_boundaries          commits
external_sessions                 wtb_checkpoint_files         file_blobs
internal_sessions     ◄───────────┼───────────────────────────►file_mementos
checkpoints           ◄───────────┘
```

**Key Principle**: AgentGit and FileTracker are UNCHANGED. WTB owns `node_boundaries` and `checkpoint_files` tables.

### Database Initialization Order
```
users → external_sessions → internal_sessions → checkpoints
```
FK constraints require this order. Test fixtures must create base data first.

### Tool Execution Pattern
```python
# Register tool with forward/reverse
tool_manager.register_reversible_tool("create_file", create_file_fn, delete_file_fn)

# Execute via registry (NOT tool_manager.execute_tool)
spec = tool_manager.tool_rollback_registry.get_tool("create_file")
result = spec.forward(args)
```

### MDP State Storage in Checkpoints
```python
# AgentGit stores this in checkpoint.metadata (JSON)
checkpoint.metadata = {
    "trigger_type": "tool_end",  # What triggered: tool_start, tool_end, llm_call, user_request
    "node_id": "current_node",   # Which node this checkpoint belongs to
    "tool_track_position": 42,   # Monotonic counter for ordering
    "mdp_state": {
        "current_node_id": "process",
        "workflow_variables": {"key": "value"},
        "execution_path": ["start", "load"]
    },
    "audit_trail": {...}  # Optional: full audit history
}
```

### Node Boundaries (WTB Concept - NOT a checkpoint!)
```python
# WTB stores node boundaries in its own database
# A boundary POINTS to checkpoints, it's not a duplicate checkpoint
node_boundary = NodeBoundary(
    internal_session_id=session.id,
    node_id="train",
    entry_checkpoint_id=first_cp_in_node,  # → agentgit.checkpoints
    exit_checkpoint_id=last_cp_in_node,    # → agentgit.checkpoints (rollback target)
    node_status="completed"
)
```

### Checkpoint-File Links (WTB Concept)
```python
# WTB links AgentGit checkpoints to FileTracker commits
file_link = CheckpointFile(
    checkpoint_id=checkpoint.id,        # → agentgit.checkpoints
    file_commit_id=commit.commit_id,    # → filetracker.commits
    file_count=3,
    total_size_bytes=1024000
)
```

### Unified Rollback Logic
```python
def rollback(target_checkpoint_id: int):
    """
    UNIFIED rollback - same logic for node-level and tool-level.
    
    "Node rollback" = caller passes node_boundary.exit_checkpoint_id
    "Tool rollback" = caller passes any checkpoint.id
    """
    # 1. Load checkpoint from AgentGit
    checkpoint = checkpoint_repo.get_by_id(target_checkpoint_id)
    
    # 2. Reverse tools after this checkpoint
    tool_manager.rollback_to_position(checkpoint.metadata["tool_track_position"])
    
    # 3. Restore files (via FileTracker if linked)
    file_link = wtb_checkpoint_files_repo.get(checkpoint_id)
    if file_link:
        file_tracker.restore_commit(file_link.file_commit_id)
    
    return checkpoint.session_state
```

### Audit Trail Integration
```python
# Store with checkpoint
checkpoint_repo.update_checkpoint_metadata(cp.id, {
    **cp.metadata,
    "audit_trail": trail.to_dict()
})

# Recover on rollback
restored_trail = AuditTrail.from_dict(checkpoint.metadata["audit_trail"])
```

### WTB Abstraction Layers
| Layer | Responsibility | Key Components |
|-------|---------------|----------------|
| Application | Business logic | ExecutionController, NodeReplacer |
| Domain | Anti-corruption | AgentGitStateAdapter (IStateAdapter) |
| Infrastructure | Persistence | Repository + Unit of Work |
| Data Access | Raw DB | SQLAlchemy (WTB), Raw SQL (AgentGit) |

---

## Run Tests

```bash
# AgentGit v2 tests
uv run pytest tests/test_agentgit_v2.py -v

# FileTracker tests
uv run pytest tests/test_file_processing.py -v

# All infrastructure tests
uv run pytest tests/ -v
```


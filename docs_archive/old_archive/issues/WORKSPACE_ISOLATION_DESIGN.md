# Workspace Isolation Design for Parallel Execution

**Date:** 2026-01-16  
**Status:** ✅ IMPLEMENTED  
**Priority:** P0 (Architectural Gap)

---

## Executive Summary

This document addresses a **critical architectural gap**: WTB currently has no mechanism to isolate file system state when forking for parallel execution (e.g., Ray variant testing). This gap causes race conditions where parallel executions overwrite each other's output files.

### Key Questions Addressed

| Question | Answer |
|----------|--------|
| Does file system auto-copy on fork? | **NO** - Currently missing |
| Same graph or different graph on rollback? | **SAME graph**, different thread_id |
| Workspace needed for rollback/time-travel? | **YES** - For file consistency |
| Workspace needed for fork? | **YES** - For isolation |

---

## Table of Contents

1. [Issue Description](#1-issue-description)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [LangGraph Rollback Behavior](#3-langgraph-rollback-behavior)
4. [Workspace Isolation Design](#4-workspace-isolation-design)
5. [Rollback & Time-Travel Workspace](#5-rollback--time-travel-workspace)
6. [Fork Workspace Strategy](#6-fork-workspace-strategy)
7. [Event & Audit Integration](#7-event--audit-integration)
8. [Implementation Phases](#8-implementation-phases)
9. [Code & Documentation Index](#9-code--documentation-index)

---

## 1. Issue Description

### 1.1 Problem Statement

When WTB executes multiple workflow variants in parallel (via Ray), each variant execution operates on the **shared file system**. This causes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT PROBLEM                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Variant A (Ray Worker 1)          Variant B (Ray Worker 2)               │
│   ┌─────────────────────┐           ┌─────────────────────┐                │
│   │ Node: data_process  │           │ Node: data_process  │                │
│   │ writes:             │   RACE    │ writes:             │                │
│   │   ./output/data.csv │◄─COND!──►│   ./output/data.csv │                │
│   │   ./models/v1.pkl   │           │   ./models/v1.pkl   │                │
│   └─────────────────────┘           └─────────────────────┘                │
│              │                                 │                            │
│              └────────────┬────────────────────┘                            │
│                           ▼                                                 │
│                   SHARED FILE SYSTEM                                        │
│                   ┌───────────────────┐                                     │
│                   │ ./output/data.csv │ ← CORRUPTED (interleaved writes)   │
│                   │ ./models/v1.pkl   │ ← LAST WRITER WINS                 │
│                   └───────────────────┘                                     │
│                                                                             │
│   Problems:                                                                 │
│   1. Output files overwritten by concurrent variants                        │
│   2. No way to restore correct file state on rollback                       │
│   3. Parity comparison invalid (comparing wrong file versions)             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Impact Analysis

| Impact | Severity | Description |
|--------|----------|-------------|
| **Data Corruption** | P0 | Parallel writes corrupt output files |
| **Invalid Testing** | P0 | Variant comparison meaningless if files mixed |
| **Rollback Fails** | P1 | Cannot restore to correct file state |
| **Audit Trail Invalid** | P1 | File commits may link to wrong data |

### 1.3 Related Code

| Component | File | Issue |
|-----------|------|-------|
| Ray Batch Runner | `wtb/application/services/ray_batch_runner.py` | No workspace isolation |
| Variant Execution Actor | Lines 207-660 in `ray_batch_runner.py` | Shares file system |
| FileTracker Service | `wtb/infrastructure/file_tracking/filetracker_service.py` | Tracks AFTER execution only |
| Workflow Project | `wtb/sdk/workflow_project.py` | `FileTrackingConfig` has no isolation config |

---

## 2. Current Architecture Analysis

### 2.1 What EXISTS (FileTracker)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT FILETRACKER ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   WHAT IT DOES:                                                             │
│   ═════════════                                                             │
│   ✅ Content-addressed blob storage (Git-like, SHA-256)                     │
│   ✅ Creates file commits with mementos                                     │
│   ✅ Links checkpoints to file commits                                      │
│   ✅ Restores files from commits on rollback                                │
│   ✅ Ray-compatible via RayFileTrackerService                               │
│                                                                             │
│   WHAT IT DOES NOT:                                                         │
│   ═════════════════                                                         │
│   ❌ Isolate working directories per variant                                │
│   ❌ Snapshot files BEFORE execution                                        │
│   ❌ Create per-variant file namespaces                                     │
│   ❌ Handle concurrent writes to same path                                  │
│                                                                             │
│   TIMING:                                                                   │
│   ════════                                                                  │
│                                                                             │
│   [Execution Start] ──► [Node Runs] ──► [Files Written] ──► [Track Files]  │
│                                              │                    │         │
│                                              │                    ▼         │
│                                         PROBLEM:           FileTracker      │
│                                         By this point,     captures         │
│                                         file may be        corrupted        │
│                                         corrupted by       state            │
│                                         parallel worker                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Code References

**FileTracker tracks files AFTER execution:**

```python
# From: wtb/application/services/ray_batch_runner.py (Lines 470-492)
# VariantExecutionActor._run_workflow_execution()

# Track output files if FileTracker is configured
files_tracked = 0
file_commit_id = None
if self._file_tracking_service:
    try:
        output_files = self._collect_output_files(execution)  # ← AFTER execution
        if output_files:
            checkpoint_id = execution.agentgit_checkpoint_id or 0
            tracking_result = self._file_tracking_service.track_and_link(
                checkpoint_id=checkpoint_id,
                file_paths=output_files,
                message=f"Execution {execution_id} outputs",
            )
```

**No pre-execution snapshot, no workspace isolation.**

---

## 3. LangGraph Rollback Behavior

### 3.1 Key Question: Same Graph or Different Graph?

> **Answer: SAME GRAPH, DIFFERENT THREAD_ID**

LangGraph's time-travel and rollback operate on a **single compiled graph instance**. The isolation comes from `thread_id`, not from separate graph instances.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ROLLBACK ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SAME CompiledStateGraph                                                   │
│   ═══════════════════════                                                   │
│                                                                             │
│   graph = workflow.compile(checkpointer=checkpointer)  ← ONE graph         │
│                                                                             │
│   THREAD ISOLATION                                                          │
│   ════════════════                                                          │
│                                                                             │
│   Thread "exec-001":   CP1 → CP2 → CP3 → CP4 (current)                     │
│   Thread "exec-002":   CP1 → CP2 → CP3                                     │
│   Thread "fork-001":   (forked from exec-001 at CP2) → CP2' → CP3'         │
│                                                                             │
│   ROLLBACK = Same Thread, Earlier Checkpoint                                │
│   ────────────────────────────────────────────                              │
│                                                                             │
│   # Rollback to CP2 on exec-001                                             │
│   config = {                                                                │
│       "configurable": {                                                     │
│           "thread_id": "exec-001",           ← SAME thread                 │
│           "checkpoint_id": "cp2-uuid"        ← EARLIER checkpoint          │
│       }                                                                     │
│   }                                                                         │
│   state = graph.get_state(config)  # Returns state at CP2                  │
│   result = graph.invoke(None, config)  # Resumes from CP2                  │
│                                                                             │
│   FORK = New Thread, Checkpoint as Starting Point                           │
│   ───────────────────────────────────────────────                           │
│                                                                             │
│   # Fork from exec-001 at CP2                                               │
│   fork_config = {                                                           │
│       "configurable": {                                                     │
│           "thread_id": "fork-001",           ← NEW thread                  │
│           "checkpoint_id": "cp2-uuid"        ← START from this state       │
│       }                                                                     │
│   }                                                                         │
│   result = graph.invoke(None, fork_config)  # Creates new branch           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Documentation References

| Document | Key Section |
|----------|-------------|
| `docs/LangGraph/TIME_TRAVEL.md` | Replay from Checkpoint, Fork from Checkpoint |
| `docs/LangGraph/PERSISTENCE.md` | Thread isolation, StateSnapshot |
| `docs/LangGraph/WTB_INTEGRATION.md` | LangGraphStateAdapter design |

### 3.3 Graph State vs File State

**Critical Insight:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GRAPH STATE ≠ FILE STATE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LangGraph Checkpoint                    File System                       │
│   ═══════════════════                    ═══════════                        │
│   ✅ State dict restored                 ❌ Files NOT auto-restored         │
│   ✅ Execution path restored             ❌ Output files may be overwritten │
│   ✅ Next nodes restored                 ❌ Model files may be different    │
│                                                                             │
│   ROLLBACK ONLY RESTORES GRAPH STATE                                        │
│   FILE STATE REQUIRES SEPARATE MECHANISM (FileTracker)                      │
│                                                                             │
│   IMPLICATION:                                                              │
│   ════════════                                                              │
│   1. Rollback MUST also call FileTracker.restore_from_checkpoint()          │
│   2. Fork MUST snapshot files BEFORE branching                              │
│   3. Parallel variants MUST have isolated file workspaces                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Workspace Isolation Design

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: WORKSPACE ISOLATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   WorkspaceManager                                                          │
│   ════════════════                                                          │
│   Central service for creating and managing isolated workspaces             │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────────┐│
│   │                     WorkspaceManager                                   ││
│   │                                                                        ││
│   │  create_workspace(batch_id, variant_id, source_paths) → Workspace     ││
│   │  get_workspace(workspace_id) → Workspace                               ││
│   │  cleanup_workspace(workspace_id)                                       ││
│   │  cleanup_batch(batch_id)                                               ││
│   │                                                                        ││
│   │  Events Published:                                                     ││
│   │  • WorkspaceCreatedEvent                                               ││
│   │  • WorkspaceCleanedUpEvent                                             ││
│   │  • WorkspaceSnapshotEvent                                              ││
│   │                                                                        ││
│   └───────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│   Workspace (Value Object)                                                  │
│   ════════════════════════                                                  │
│   ┌───────────────────────────────────────────────────────────────────────┐│
│   │  workspace_id: str                                                     ││
│   │  batch_test_id: str                                                    ││
│   │  variant_name: str                                                     ││
│   │  execution_id: str                                                     ││
│   │  root_path: Path                                                       ││
│   │  input_dir: Path                                                       ││
│   │  output_dir: Path                                                      ││
│   │  created_at: datetime                                                  ││
│   │  source_snapshot_commit_id: Optional[str]  # FileTracker commit        ││
│   │                                                                        ││
│   │  activate() → Sets CWD                                                 ││
│   │  deactivate() → Restores CWD                                           ││
│   │  get_relative_path(abs_path) → Path                                    ││
│   │                                                                        ││
│   └───────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│   Physical Layout:                                                          │
│   ════════════════                                                          │
│                                                                             │
│   {workspace_base}/                                                         │
│   └── batch_{batch_id}/                                                    │
│       ├── variant_A_{exec_id}/                                              │
│       │   ├── input/           ← Source files copied/linked here           │
│       │   ├── output/          ← Variant writes here (isolated)            │
│       │   └── workspace.json   ← Metadata                                  │
│       ├── variant_B_{exec_id}/                                              │
│       │   ├── input/                                                       │
│       │   ├── output/                                                      │
│       │   └── workspace.json                                               │
│       └── _shared/             ← Optional: Read-only shared resources      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Workspace Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKSPACE LIFECYCLE                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PRE-EXECUTION: Create Workspace                                         │
│  ═══════════════════════════════════                                        │
│                                                                             │
│  BatchTestRunner.run_batch_test()                                           │
│       │                                                                     │
│       ├── For each variant combination:                                     │
│       │       │                                                             │
│       │       ├── workspace = WorkspaceManager.create_workspace(           │
│       │       │       batch_id=batch_test.id,                               │
│       │       │       variant_name=combo.name,                              │
│       │       │       source_paths=tracked_paths,                           │
│       │       │   )                                                         │
│       │       │                                                             │
│       │       ├── Snapshot source files:                                    │
│       │       │   └── FileTracker.track_files(source_paths)                │
│       │       │       → source_snapshot_commit_id                           │
│       │       │                                                             │
│       │       ├── Copy/link source files to workspace.input_dir            │
│       │       │   └── Uses hard links when possible (efficient)            │
│       │       │                                                             │
│       │       └── Publish: WorkspaceCreatedEvent                           │
│       │                                                                     │
│       └── Submit variants to actors with workspace_id                       │
│                                                                             │
│  2. DURING EXECUTION: Activate Workspace                                    │
│  ════════════════════════════════════════                                   │
│                                                                             │
│  VariantExecutionActor.execute_variant()                                    │
│       │                                                                     │
│       ├── workspace = WorkspaceManager.get_workspace(workspace_id)         │
│       │                                                                     │
│       ├── workspace.activate()                                              │
│       │   └── os.chdir(workspace.root_path)                                │
│       │                                                                     │
│       ├── Execute workflow nodes                                            │
│       │   └── All file writes go to isolated workspace                     │
│       │                                                                     │
│       └── workspace.deactivate()                                            │
│           └── os.chdir(original_cwd)                                       │
│                                                                             │
│  3. POST-EXECUTION: Track & Cleanup                                         │
│  ══════════════════════════════════                                         │
│                                                                             │
│  After execution completes:                                                 │
│       │                                                                     │
│       ├── FileTracker.track_and_link(                                       │
│       │       checkpoint_id,                                                │
│       │       workspace.output_dir,                                         │
│       │   )                                                                 │
│       │                                                                     │
│       ├── If success and cleanup_on_complete:                               │
│       │   └── WorkspaceManager.cleanup_workspace(workspace_id)             │
│       │                                                                     │
│       └── If failed and preserve_on_failure:                                │
│           └── Keep workspace for debugging                                  │
│                                                                             │
│  4. BATCH COMPLETION: Cleanup All                                           │
│  ════════════════════════════════                                           │
│                                                                             │
│  BatchTestRunner finishes:                                                  │
│       │                                                                     │
│       └── WorkspaceManager.cleanup_batch(batch_id)                          │
│           └── Remove batch_{batch_id}/ directory                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Configuration Extension

```yaml
# Extend FileTrackingConfig in wtb/sdk/workflow_project.py

FileTrackingConfig:
  # Existing fields...
  enabled: bool = False
  tracked_paths: List[str] = []
  
  # NEW: Workspace Isolation
  workspace_isolation:
    enabled: bool = True  # Enable for parallel execution
    strategy: "workspace" | "snapshot" | "none" = "workspace"
    base_dir: Optional[str] = None  # Default: system temp
    cleanup_on_complete: bool = True
    preserve_on_failure: bool = True  # Keep for debugging
    use_hard_links: bool = True  # Efficient copy
    
  # NEW: Pre-execution snapshot
  pre_execution_snapshot: bool = True  # Snapshot before fork
```

---

## 5. Rollback & Time-Travel Workspace

### 5.1 Why Workspace for Rollback?

When rolling back graph state, we must also restore file state. Without workspace isolation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK WITHOUT WORKSPACE (BROKEN)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Timeline:                                                                 │
│   ─────────                                                                 │
│   T1: Execution at Node A writes ./output/model.pkl (v1)                   │
│   T2: Checkpoint CP1 created, linked to FileCommit FC1 (contains v1)       │
│   T3: Node B modifies ./output/model.pkl (v2)                              │
│   T4: Checkpoint CP2 created, linked to FileCommit FC2 (contains v2)       │
│   T5: Node C crashes                                                        │
│                                                                             │
│   User wants to rollback to CP1:                                            │
│   ──────────────────────────────                                            │
│   1. graph.get_state(config_cp1) → State dict restored ✅                  │
│   2. FileTracker.restore_from_checkpoint(CP1) → Restores v1 ✅             │
│                                                                             │
│   BUT: If another parallel execution wrote ./output/model.pkl (v3)         │
│   between T4 and T5, the file on disk may be v3, not v2!                   │
│                                                                             │
│   RESULT: Rollback restores wrong file version                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Rollback with Workspace Isolation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK WITH WORKSPACE (CORRECT)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Each execution has isolated workspace:                                    │
│   ──────────────────────────────────────                                    │
│                                                                             │
│   exec-001/                                                                 │
│   ├── input/model.pkl (source snapshot)                                     │
│   └── output/model.pkl (exec-001's version)                                │
│                                                                             │
│   exec-002/                                                                 │
│   ├── input/model.pkl (source snapshot)                                     │
│   └── output/model.pkl (exec-002's version)                                │
│                                                                             │
│   Rollback to CP1 for exec-001:                                             │
│   ─────────────────────────────                                             │
│   1. graph.get_state(config_cp1) → Restore graph state                     │
│   2. FileTracker.restore_to_workspace(CP1, workspace="exec-001/")          │
│      → Restores exec-001/output/model.pkl to v1                            │
│                                                                             │
│   exec-002's files are UNAFFECTED ✅                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Time-Travel Workspace Requirements

| Operation | Workspace Needed | Reason |
|-----------|-----------------|--------|
| **View history** | No | Only reading graph state |
| **Rollback (same execution)** | Yes | Must restore files to workspace |
| **Rollback + Resume** | Yes | Resumed execution writes to workspace |
| **Compare states** | Optional | Only if comparing file contents |

### 5.4 Rollback Event Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK EVENT SEQUENCE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User requests rollback to checkpoint_id:                                  │
│                                                                             │
│   1. RollbackRequestedEvent                                                 │
│      ├── execution_id                                                       │
│      ├── target_checkpoint_id                                               │
│      └── workspace_id                                                       │
│                                                                             │
│   2. StateAdapter.rollback(checkpoint_id)                                   │
│      ├── LangGraph: graph.get_state(config_with_checkpoint)                │
│      └── Publishes: RollbackPerformedEvent (graph state)                   │
│                                                                             │
│   3. FileTracker.restore_from_checkpoint(checkpoint_id)                     │
│      ├── Gets file_commit_id from checkpoint_files table                   │
│      ├── Restores files to workspace.output_dir                            │
│      └── Publishes: FileRestoreEvent                                       │
│                                                                             │
│   4. WorkspaceManager.verify_workspace_integrity(workspace_id)              │
│      └── Validates restored files match commit                             │
│                                                                             │
│   5. RollbackCompletedEvent                                                 │
│      ├── execution_id                                                       │
│      ├── checkpoint_id                                                      │
│      ├── graph_state_restored: True                                        │
│      ├── files_restored: count                                             │
│      └── workspace_path                                                    │
│                                                                             │
│   Audit Entry:                                                              │
│   ────────────                                                              │
│   [14:30:45] ↩️  Rollback to checkpoint #42                                 │
│              ├── Graph state: restored                                      │
│              ├── Files restored: 3 (256KB)                                  │
│              └── Workspace: exec-001/                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Fork Workspace Strategy

### 6.1 Fork Types in WTB

| Fork Type | Purpose | Workspace Strategy |
|-----------|---------|-------------------|
| **Variant Testing** | A/B test node implementations | New workspace per variant |
| **Rollback Branch** | Create branch from checkpoint | Clone parent workspace |
| **Manual Fork** | User-initiated branch | Clone or new workspace |

### 6.2 Variant Fork (Parallel Execution)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VARIANT FORK WORKSPACE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   BatchTest starts with 3 variants:                                         │
│   ════════════════════════════════                                          │
│                                                                             │
│   Source state:                                                             │
│   ├── ./data/input.csv                                                      │
│   └── ./config/settings.json                                                │
│                                                                             │
│   1. Pre-fork Snapshot:                                                     │
│      ─────────────────                                                      │
│      FileTracker.track_files([source files])                               │
│      → source_commit_id = "abc123"                                         │
│                                                                             │
│   2. Create Workspaces:                                                     │
│      ──────────────────                                                     │
│                                                                             │
│      batch_{id}/                                                            │
│      ├── variant_bm25_{exec1}/                                              │
│      │   ├── input/                                                         │
│      │   │   ├── input.csv → (hard link to source)                         │
│      │   │   └── settings.json → (hard link)                               │
│      │   ├── output/                                                        │
│      │   └── workspace.json                                                │
│      │       └── source_snapshot_commit_id: "abc123"                       │
│      │                                                                      │
│      ├── variant_dense_{exec2}/                                             │
│      │   ├── input/ ...                                                     │
│      │   ├── output/                                                        │
│      │   └── workspace.json                                                │
│      │                                                                      │
│      └── variant_hybrid_{exec3}/                                            │
│          ├── input/ ...                                                     │
│          ├── output/                                                        │
│          └── workspace.json                                                │
│                                                                             │
│   3. LangGraph Thread IDs:                                                  │
│      ─────────────────────                                                  │
│      • variant_bm25: thread_id = "batch-001-bm25"                          │
│      • variant_dense: thread_id = "batch-001-dense"                        │
│      • variant_hybrid: thread_id = "batch-001-hybrid"                      │
│                                                                             │
│   4. Each variant executes in isolation:                                    │
│      ────────────────────────────────                                       │
│      variant_bm25 writes → batch_{id}/variant_bm25_{exec1}/output/         │
│      variant_dense writes → batch_{id}/variant_dense_{exec2}/output/       │
│      variant_hybrid writes → batch_{id}/variant_hybrid_{exec3}/output/     │
│                                                                             │
│   5. Post-execution tracking:                                               │
│      ───────────────────────                                                │
│      Each variant's outputs tracked to its own FileCommit                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Rollback Branch Fork

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK BRANCH FORK                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User rolls back exec-001 to CP2 and continues as new branch:              │
│   ═══════════════════════════════════════════════════════════               │
│                                                                             │
│   1. Get parent workspace state at CP2:                                     │
│      ─────────────────────────────────                                      │
│      • Graph state: graph.get_state(config_cp2)                            │
│      • File commit: checkpoint_files[CP2].file_commit_id                   │
│                                                                             │
│   2. Create branch workspace:                                               │
│      ─────────────────────────                                              │
│      branch_workspace = WorkspaceManager.create_branch_workspace(          │
│          parent_workspace_id="exec-001",                                    │
│          branch_checkpoint_id=CP2,                                          │
│          new_execution_id="branch-001",                                     │
│      )                                                                      │
│                                                                             │
│   3. Restore files to branch workspace:                                     │
│      ──────────────────────────────────                                     │
│      FileTracker.restore_commit(                                            │
│          commit_id=cp2_file_commit_id,                                      │
│          target_dir=branch_workspace.root_path,                            │
│      )                                                                      │
│                                                                             │
│   4. Create new LangGraph thread:                                           │
│      ─────────────────────────────                                          │
│      fork_config = {                                                        │
│          "configurable": {                                                  │
│              "thread_id": "branch-001",  # NEW thread                      │
│              "checkpoint_id": CP2,        # START from CP2 state           │
│          }                                                                  │
│      }                                                                      │
│      graph.invoke(None, fork_config)                                        │
│                                                                             │
│   Result:                                                                   │
│   ═══════                                                                   │
│   • exec-001 workspace: preserved, unchanged                               │
│   • branch-001 workspace: new, initialized from CP2 file state             │
│   • LangGraph: branch-001 thread starts from CP2 graph state               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Fork Event Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FORK EVENT SEQUENCE                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. ForkRequestedEvent                                                     │
│      ├── parent_execution_id                                                │
│      ├── fork_checkpoint_id                                                 │
│      ├── new_execution_id                                                   │
│      └── fork_type: "variant" | "rollback_branch" | "manual"               │
│                                                                             │
│   2. WorkspaceCreatedEvent                                                  │
│      ├── workspace_id                                                       │
│      ├── parent_workspace_id (if branch)                                    │
│      ├── source_snapshot_commit_id                                          │
│      └── file_count, total_size                                            │
│                                                                             │
│   3. LangGraph BranchCreatedEvent                                           │
│      ├── parent_thread_id                                                   │
│      ├── new_thread_id                                                      │
│      ├── fork_checkpoint_id                                                 │
│      └── graph_state_copied: True                                          │
│                                                                             │
│   4. ForkCompletedEvent                                                     │
│      ├── new_execution_id                                                   │
│      ├── workspace_id                                                       │
│      ├── thread_id                                                          │
│      └── ready_to_execute: True                                            │
│                                                                             │
│   Audit Trail Entry:                                                        │
│   ─────────────────                                                         │
│   [14:35:22] 🔀 Fork created                                                │
│              ├── Type: variant_test                                         │
│              ├── Parent: exec-001 @ CP2                                     │
│              ├── New execution: variant-bm25                                │
│              ├── Workspace: batch-001/variant_bm25/                         │
│              ├── Files copied: 5 (1.2MB)                                    │
│              └── Thread: batch-001-bm25                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Event & Audit Integration

### 7.1 New Domain Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKSPACE DOMAIN EVENTS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Add to: wtb/domain/events/workspace_events.py                             │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  WorkspaceCreatedEvent(WTBEvent)                                     │  │
│   │  ──────────────────────────────                                      │  │
│   │  • workspace_id: str                                                 │  │
│   │  • batch_test_id: str                                                │  │
│   │  • execution_id: str                                                 │  │
│   │  • variant_name: str                                                 │  │
│   │  • workspace_path: str                                               │  │
│   │  • source_snapshot_commit_id: Optional[str]                          │  │
│   │  • file_count: int                                                   │  │
│   │  • total_size_bytes: int                                             │  │
│   │  • strategy: str  # "workspace" | "snapshot" | "clone"              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  WorkspaceActivatedEvent(WTBEvent)                                   │  │
│   │  ──────────────────────────────────                                  │  │
│   │  • workspace_id: str                                                 │  │
│   │  • execution_id: str                                                 │  │
│   │  • previous_cwd: str                                                 │  │
│   │  • new_cwd: str                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  WorkspaceDeactivatedEvent(WTBEvent)                                 │  │
│   │  ────────────────────────────────────                                │  │
│   │  • workspace_id: str                                                 │  │
│   │  • execution_id: str                                                 │  │
│   │  • files_written: int                                                │  │
│   │  • output_size_bytes: int                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  WorkspaceCleanedUpEvent(WTBEvent)                                   │  │
│   │  ──────────────────────────────────                                  │  │
│   │  • workspace_id: str                                                 │  │
│   │  • reason: str  # "completed" | "failed_preserved" | "batch_cleanup"│  │
│   │  • files_removed: int                                                │  │
│   │  • space_freed_bytes: int                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  FileRestoreEvent(WTBEvent)                                          │  │
│   │  ────────────────────────────                                        │  │
│   │  • execution_id: str                                                 │  │
│   │  • checkpoint_id: int                                                │  │
│   │  • file_commit_id: str                                               │  │
│   │  • workspace_id: str                                                 │  │
│   │  • files_restored: int                                               │  │
│   │  • total_size_bytes: int                                             │  │
│   │  • restore_target: str  # workspace path                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Audit Trail Extension

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUDIT EVENT TYPES (EXTENSION)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Add to: WTBAuditEventType enum                                            │
│                                                                             │
│   class WTBAuditEventType(Enum):                                            │
│       # ... existing ...                                                    │
│                                                                             │
│       # Workspace events                                                    │
│       WORKSPACE_CREATED = "workspace_created"                               │
│       WORKSPACE_ACTIVATED = "workspace_activated"                           │
│       WORKSPACE_DEACTIVATED = "workspace_deactivated"                       │
│       WORKSPACE_CLEANED_UP = "workspace_cleaned_up"                         │
│                                                                             │
│       # Fork events                                                         │
│       FORK_REQUESTED = "fork_requested"                                     │
│       FORK_COMPLETED = "fork_completed"                                     │
│                                                                             │
│       # File restore events                                                 │
│       FILE_SNAPSHOT_CREATED = "file_snapshot_created"                       │
│       FILE_RESTORE_STARTED = "file_restore_started"                         │
│       FILE_RESTORE_COMPLETED = "file_restore_completed"                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE EVENT FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   BATCH TEST START                                                          │
│   ════════════════                                                          │
│                                                                             │
│   BatchTestStartedEvent                                                     │
│       │                                                                     │
│       ├── For each variant:                                                 │
│       │       │                                                             │
│       │       ├── WorkspaceCreatedEvent                                     │
│       │       │                                                             │
│       │       ├── ForkRequestedEvent (if from checkpoint)                   │
│       │       │       └── BranchCreatedEvent (LangGraph)                   │
│       │       │                                                             │
│       │       └── ForkCompletedEvent                                        │
│       │                                                                     │
│       └── BatchTestVariantsReadyEvent                                       │
│                                                                             │
│   VARIANT EXECUTION (per actor)                                             │
│   ════════════════════════════                                              │
│                                                                             │
│   WorkspaceActivatedEvent                                                   │
│       │                                                                     │
│       ├── ExecutionStartedEvent                                             │
│       │       │                                                             │
│       │       ├── NodeStartedEvent                                          │
│       │       │   └── CheckpointCreatedEvent                               │
│       │       │                                                             │
│       │       ├── NodeCompletedEvent                                        │
│       │       │   └── CheckpointCreatedEvent                               │
│       │       │                                                             │
│       │       └── (repeat for each node)                                    │
│       │                                                                     │
│       ├── ExecutionCompletedEvent / ExecutionFailedEvent                    │
│       │                                                                     │
│       ├── FileTrackingEvent (outputs tracked)                               │
│       │                                                                     │
│       └── WorkspaceDeactivatedEvent                                         │
│                                                                             │
│   BATCH TEST COMPLETE                                                       │
│   ═══════════════════                                                       │
│                                                                             │
│   VariantExecutionCompletedEvent (per variant)                              │
│       │                                                                     │
│       └── WorkspaceCleanedUpEvent (if cleanup_on_complete)                  │
│                                                                             │
│   BatchTestCompletedEvent                                                   │
│       │                                                                     │
│       └── BatchWorkspacesCleanedUpEvent                                     │
│                                                                             │
│   ROLLBACK (if requested)                                                   │
│   ═══════════════════════                                                   │
│                                                                             │
│   RollbackRequestedEvent                                                    │
│       │                                                                     │
│       ├── RollbackPerformedEvent (graph state)                              │
│       │                                                                     │
│       ├── FileRestoreEvent (file state)                                     │
│       │                                                                     │
│       └── RollbackCompletedEvent                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Audit Trail Display Example

```
═══════════════════════════════════════════════════════
                  WTB AUDIT TRAIL                       
═══════════════════════════════════════════════════════

Batch Test: batch-001
Workflow:   rag_pipeline
Duration:   45,230ms

Variants: ✅ 2 succeeded | ❌ 1 failed
Checkpoints: 12 | Rollbacks: 1

───────────────────────────────────────────────────────
                     TIMELINE                           
───────────────────────────────────────────────────────

[14:30:00.123] 🚀 Batch test started
               ├── Workflow: rag_pipeline
               ├── Variants: 3 (bm25, dense, hybrid)
               └── Parallel workers: 3

[14:30:00.234] 📁 Workspace created: variant_bm25
               ├── Path: /tmp/wtb_batch-001/variant_bm25_exec-001/
               ├── Source snapshot: abc123
               └── Files: 5 (2.3MB)

[14:30:00.256] 📁 Workspace created: variant_dense
               └── Path: /tmp/wtb_batch-001/variant_dense_exec-002/

[14:30:00.278] 📁 Workspace created: variant_hybrid
               └── Path: /tmp/wtb_batch-001/variant_hybrid_exec-003/

[14:30:00.312] 🔀 Fork completed: variant_bm25
               ├── Thread: batch-001-bm25
               └── Starting from source state

[14:30:00.512] ▶️  Workspace activated: variant_bm25
               └── CWD: /tmp/wtb_batch-001/variant_bm25_exec-001/

[14:30:01.123] ℹ️  Execution started: variant_bm25
[14:30:01.234] ✅ Node 'retriever' completed [523ms]
               └── Checkpoint #1 created

... (more entries) ...

[14:30:25.456] ❌ Node 'generator' failed: variant_hybrid
               └── Error: TokenLimitExceeded

[14:30:25.567] ↩️  Rollback requested: variant_hybrid → CP2
               ├── Target checkpoint: #2
               └── Workspace: variant_hybrid_exec-003

[14:30:25.678] ✅ Files restored from commit def456
               ├── Files: 3
               ├── Size: 1.2MB
               └── Target: variant_hybrid_exec-003/output/

[14:30:45.123] ✅ Batch test completed
               ├── variant_bm25: SUCCESS (score: 0.87)
               ├── variant_dense: SUCCESS (score: 0.91)
               └── variant_hybrid: FAILED

[14:30:45.234] 🗑️  Workspaces cleaned up: 2
               └── Preserved: variant_hybrid (failure debug)
```

---

## 8. Implementation Phases

### Phase 1: Core Workspace Manager (P0)

| Task | File | Description |
|------|------|-------------|
| Define Workspace value object | `wtb/domain/models/workspace.py` | Immutable workspace configuration |
| Define Workspace events | `wtb/domain/events/workspace_events.py` | Domain events for workspace lifecycle |
| Implement WorkspaceManager | `wtb/infrastructure/workspace/manager.py` | Create, activate, cleanup workspaces |
| Unit tests | `tests/test_wtb/test_workspace_manager.py` | Full coverage |

### Phase 2: Integration with Ray Batch Runner (P0)

| Task | File | Description |
|------|------|-------------|
| Update VariantExecutionActor | `wtb/application/services/ray_batch_runner.py` | Use workspace during execution |
| Update RayBatchTestRunner | Same file | Create workspaces before fork |
| Update FileTracker integration | `wtb/infrastructure/file_tracking/` | Restore to workspace |
| Integration tests | `tests/test_wtb/test_ray_workspace_integration.py` | E2E tests |

### Phase 3: Configuration & SDK (P1)

| Task | File | Description |
|------|------|-------------|
| Extend FileTrackingConfig | `wtb/sdk/workflow_project.py` | Add workspace_isolation config |
| Update TestBench | `wtb/sdk/test_bench.py` | Support workspace config |
| Documentation | `docs/` | User guide |

### Phase 4: Event & Audit Integration (P1)

| Task | File | Description |
|------|------|-------------|
| Add workspace audit types | `wtb/infrastructure/events/wtb_audit_trail.py` | New audit event types |
| Update audit listener | `wtb/infrastructure/events/audit_listener.py` | Subscribe to workspace events |
| Update RayEventBridge | `wtb/infrastructure/events/ray_event_bridge.py` | Emit workspace events |

---

## 9. Code & Documentation Index

### 9.1 Existing Code References

| Component | Location | Lines | Relevance |
|-----------|----------|-------|-----------|
| VariantExecutionActor | `wtb/application/services/ray_batch_runner.py` | 207-660 | Needs workspace integration |
| RayBatchTestRunner | Same file | 689-1425 | Needs pre-fork workspace creation |
| FileTrackerService | `wtb/infrastructure/file_tracking/filetracker_service.py` | All | Restore to workspace |
| RayFileTrackerService | `wtb/infrastructure/file_tracking/ray_filetracker_service.py` | All | Actor-compatible |
| FileTrackingConfig | `wtb/sdk/workflow_project.py` | 29-55 | Extend with workspace config |
| WTBEventBus | `wtb/infrastructure/events/wtb_event_bus.py` | All | Publish workspace events |
| WTBAuditTrail | `wtb/infrastructure/events/wtb_audit_trail.py` | All | Record workspace audit |
| RayEventBridge | `wtb/infrastructure/events/ray_event_bridge.py` | All | Emit from actors |

### 9.2 Documentation References

| Document | Location | Section |
|----------|----------|---------|
| LangGraph Time Travel | `docs/LangGraph/TIME_TRAVEL.md` | Fork from Checkpoint |
| LangGraph Persistence | `docs/LangGraph/PERSISTENCE.md` | Thread isolation |
| Ray FileTracker Integration | `docs/Ray/RAY_FILETRACKER_INTEGRATION_DESIGN.md` | Full design |
| EventBus & Audit Design | `docs/EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md` | Event system |
| File Processing Architecture | `docs/file_processing/ARCHITECTURE.md` | ACID compliance |

### 9.3 New Files to Create

| File | Purpose |
|------|---------|
| `wtb/domain/models/workspace.py` | Workspace value object |
| `wtb/domain/events/workspace_events.py` | Workspace domain events |
| `wtb/infrastructure/workspace/__init__.py` | Package init |
| `wtb/infrastructure/workspace/manager.py` | WorkspaceManager implementation |
| `tests/test_wtb/test_workspace_manager.py` | Unit tests |
| `tests/test_wtb/test_workspace_integration.py` | Integration tests |

---

---

## 10. Virtual Environment (Venv) Management for Fork/Rollback/Parallel

### 10.1 Current State Analysis

**What EXISTS:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT VENV ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SDK Configuration:                                                         │
│  ══════════════════                                                         │
│                                                                             │
│  EnvironmentConfig:                                                         │
│  ├── granularity: "workflow" | "node" | "variant"                          │
│  ├── node_environments: Dict[node_id, EnvSpec]                             │
│  ├── variant_environments: Dict["node:variant", EnvSpec]                   │
│  └── uv_manager_url: Optional[str]  # gRPC service                         │
│                                                                             │
│  EnvSpec:                                                                   │
│  ├── python_version: str                                                   │
│  ├── dependencies: List[str]                                               │
│  ├── requirements_file: Optional[str]                                      │
│  └── env_vars: Dict[str, str]                                              │
│                                                                             │
│  Providers:                                                                 │
│  ═══════════                                                                │
│  ├── InProcessEnvironmentProvider (no isolation)                           │
│  ├── RayEnvironmentProvider (runtime_env based)                            │
│  └── GrpcEnvironmentProvider (UV Venv Manager service)                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**What is MISSING:**

| Gap | Current Behavior | Required Behavior |
|-----|------------------|-------------------|
| **Fork venv isolation** | All variants share same venv | Each variant gets isolated venv |
| **Rollback venv restore** | Venv state NOT tracked | Restore exact venv at checkpoint |
| **Node update venv invalidation** | Venv NOT invalidated | Recreate venv when node changes |
| **Venv-checkpoint linkage** | No linkage | Track venv version per checkpoint |

### 10.2 Venv Lifecycle During Operations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VENV LIFECYCLE GAPS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PARALLEL EXECUTION (Current - BROKEN)                                      │
│  ══════════════════════════════════════                                     │
│                                                                             │
│  BatchTest with 3 variants:                                                 │
│                                                                             │
│  variant_bm25   variant_dense   variant_hybrid                              │
│       │              │               │                                      │
│       └──────────────┴───────────────┘                                      │
│                      ▼                                                      │
│              SHARED VENV? ← Problem: Ray runtime_env installs packages     │
│                             on-demand, may conflict between variants        │
│                                                                             │
│  If variant_bm25 needs faiss-cpu==1.7.0                                    │
│  And variant_dense needs faiss-cpu==1.8.0                                   │
│  → CONFLICT during parallel execution                                       │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  FORK (Current - BROKEN)                                                    │
│  ═══════════════════════                                                    │
│                                                                             │
│  Execution A at Node 2:                                                     │
│       │                                                                     │
│       ├── Uses venv with packages: [langchain==0.1.0, chromadb==0.4.0]    │
│       │                                                                     │
│       └── Fork to Branch B                                                  │
│               │                                                             │
│               └── Branch B starts with... WHICH venv?                       │
│                   • Same venv as A? (shared, may conflict)                 │
│                   • Copy of venv? (expensive, not implemented)             │
│                   • No venv tracking! (current state)                       │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  ROLLBACK (Current - BROKEN)                                                │
│  ═══════════════════════════                                                │
│                                                                             │
│  Timeline:                                                                  │
│  T1: Node A runs with venv V1 (langchain==0.1.0)                           │
│  T2: Checkpoint CP1 created                                                │
│  T3: User updates langchain to 0.2.0 → venv becomes V2                     │
│  T4: Checkpoint CP2 created                                                │
│  T5: User rolls back to CP1                                                 │
│                                                                             │
│  Question: Which venv is used after rollback?                               │
│  • Graph state: restored to CP1 ✅                                         │
│  • File state: restored (if FileTracker used) ✅                           │
│  • Venv state: V2 still active! ❌ Should be V1                            │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  NODE UPDATE (Current - BROKEN)                                             │
│  ══════════════════════════════                                             │
│                                                                             │
│  User updates node "retriever":                                             │
│  • Changes implementation (code)                                            │
│  • Changes dependencies (adds faiss-gpu)                                    │
│                                                                             │
│  Current behavior:                                                          │
│  • Code update: triggers variant version change                            │
│  • Venv update: NOT invalidated                                            │
│  • Old venv may be reused with stale packages                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Proposed Venv Management Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: VENV-WORKSPACE INTEGRATION                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  KEY PRINCIPLE: Venv is part of Workspace                                   │
│  ════════════════════════════════════════                                   │
│                                                                             │
│  Workspace (Extended):                                                      │
│  ├── workspace_id: str                                                      │
│  ├── root_path: Path                                                        │
│  ├── input_dir: Path                                                        │
│  ├── output_dir: Path                                                       │
│  ├── venv_dir: Path                 ← NEW: Isolated venv per workspace     │
│  ├── venv_spec_hash: str            ← NEW: Hash of EnvSpec for invalidation│
│  └── venv_commit_id: Optional[str]  ← NEW: UV Venv Manager commit          │
│                                                                             │
│  Physical Layout (Updated):                                                 │
│  ══════════════════════════                                                 │
│                                                                             │
│  {workspace_base}/                                                          │
│  └── batch_{batch_id}/                                                     │
│      ├── variant_bm25_{exec_id}/                                            │
│      │   ├── input/                                                         │
│      │   ├── output/                                                        │
│      │   ├── .venv/                 ← Isolated venv for this variant       │
│      │   │   ├── bin/python                                                │
│      │   │   └── lib/python3.11/                                           │
│      │   ├── pyproject.toml         ← UV project file                      │
│      │   ├── uv.lock                ← Lock file for reproducibility        │
│      │   └── workspace.json                                                │
│      │       ├── source_snapshot_commit_id                                 │
│      │       └── venv_spec_hash     ← For invalidation check              │
│      │                                                                      │
│      └── variant_dense_{exec_id}/                                           │
│          ├── .venv/                 ← Different venv, different packages   │
│          └── ...                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 Venv Operations by Scenario

#### 10.4.1 Parallel Execution (Fork for Variants)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARALLEL: VENV PER VARIANT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BatchTest Start:                                                           │
│  ═══════════════                                                            │
│                                                                             │
│  1. Get variant-specific EnvSpecs from EnvironmentConfig                    │
│                                                                             │
│     variant_bm25:                                                           │
│       EnvSpec(python="3.11", deps=["faiss-cpu==1.7.0", "langchain"])       │
│                                                                             │
│     variant_dense:                                                          │
│       EnvSpec(python="3.11", deps=["faiss-gpu==1.8.0", "langchain"])       │
│                                                                             │
│  2. Create workspace WITH venv:                                             │
│                                                                             │
│     workspace = WorkspaceManager.create_workspace(                          │
│         batch_id=...,                                                       │
│         variant_name="bm25",                                                │
│         env_spec=bm25_env_spec,    ← NEW: Pass EnvSpec                     │
│     )                                                                       │
│                                                                             │
│  3. WorkspaceManager provisions venv:                                       │
│                                                                             │
│     a. Calculate venv_spec_hash = hash(env_spec)                           │
│     b. Check if cached venv with same hash exists (reuse_existing=True)    │
│     c. If not, call UV Venv Manager:                                        │
│        GrpcEnvironmentProvider.create_environment(                          │
│            variant_id=workspace_id,                                         │
│            config={                                                         │
│                "packages": env_spec.dependencies,                           │
│                "python_version": env_spec.python_version,                   │
│                "target_dir": workspace.venv_dir,                           │
│            }                                                                │
│        )                                                                    │
│     d. Store venv_spec_hash in workspace.json                              │
│                                                                             │
│  4. Ray actor uses workspace venv:                                          │
│                                                                             │
│     actor = VariantExecutionActor.options(                                  │
│         runtime_env={                                                       │
│             "py_executable": f"{workspace.venv_dir}/bin/python",           │
│             "env_vars": {"VIRTUAL_ENV": workspace.venv_dir},               │
│         }                                                                   │
│     ).remote(...)                                                           │
│                                                                             │
│  Result: Each variant has ISOLATED venv, no conflicts                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 10.4.2 Rollback with Venv Restore

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK: VENV STATE TRACKING                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Checkpoint Creation (Extended):                                            │
│  ════════════════════════════════                                           │
│                                                                             │
│  When creating checkpoint:                                                  │
│  1. Save graph state (LangGraph checkpointer)                              │
│  2. Save file state (FileTracker.track_and_link)                           │
│  3. NEW: Save venv spec hash                                                │
│                                                                             │
│     checkpoint_metadata = {                                                 │
│         "graph_state": {...},                                               │
│         "file_commit_id": "abc123",                                        │
│         "venv_spec_hash": workspace.venv_spec_hash,    ← NEW               │
│         "venv_lock_snapshot": read_file("uv.lock"),    ← NEW (optional)    │
│     }                                                                       │
│                                                                             │
│  Rollback (Extended):                                                       │
│  ═════════════════════                                                      │
│                                                                             │
│  1. Restore graph state (existing)                                          │
│  2. Restore file state (existing)                                           │
│  3. NEW: Check venv compatibility:                                          │
│                                                                             │
│     current_hash = workspace.venv_spec_hash                                 │
│     target_hash = checkpoint_metadata["venv_spec_hash"]                    │
│                                                                             │
│     if current_hash != target_hash:                                         │
│         # Venv has changed since checkpoint!                               │
│         # Option A: Warn user (default)                                     │
│         # Option B: Recreate venv from uv.lock snapshot                    │
│                                                                             │
│         if rollback_options.restore_venv:                                   │
│             UV_Manager.sync_from_lock(                                      │
│                 workspace.venv_dir,                                         │
│                 checkpoint_metadata["venv_lock_snapshot"]                  │
│             )                                                               │
│         else:                                                               │
│             emit VenvMismatchWarningEvent(                                  │
│                 current=current_hash,                                       │
│                 expected=target_hash,                                       │
│             )                                                               │
│                                                                             │
│  Event Sequence:                                                            │
│  ════════════════                                                           │
│  1. RollbackRequestedEvent                                                  │
│  2. GraphStateRestoredEvent                                                 │
│  3. FileStateRestoredEvent                                                  │
│  4. VenvCompatibilityCheckedEvent (hash match / mismatch)                  │
│  5. VenvRestoredEvent (if restore_venv=True and mismatch)                  │
│  6. RollbackCompletedEvent                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 10.4.3 Node Update with Venv Invalidation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NODE UPDATE: VENV INVALIDATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  When Node is Updated:                                                      │
│  ═════════════════════                                                      │
│                                                                             │
│  project.update_node("retriever", new_impl, reason="upgrade deps")          │
│                                                                             │
│  OR                                                                         │
│                                                                             │
│  project.register_variant(                                                  │
│      node="retriever",                                                      │
│      name="v2_with_gpu",                                                    │
│      implementation=gpu_retriever,                                          │
│      environment=EnvSpec(deps=["faiss-gpu"]),  ← New dependencies          │
│  )                                                                          │
│                                                                             │
│  Invalidation Flow:                                                         │
│  ══════════════════                                                         │
│                                                                             │
│  1. Detect EnvSpec change:                                                  │
│     old_hash = hash(old_env_spec)                                          │
│     new_hash = hash(new_env_spec)                                          │
│                                                                             │
│  2. If hashes differ:                                                       │
│     a. Mark existing venvs for node as "stale"                             │
│     b. Emit VenvInvalidatedEvent                                           │
│     c. On next execution, recreate venv                                     │
│                                                                             │
│  3. If reuse_existing=True and hash matches:                                │
│     a. Reuse existing venv (no change)                                     │
│                                                                             │
│  Stale Venv Detection:                                                      │
│  ═════════════════════                                                      │
│                                                                             │
│  Before execution:                                                          │
│                                                                             │
│  def get_or_create_venv(workspace, env_spec):                               │
│      expected_hash = hash(env_spec)                                         │
│      current_hash = workspace.venv_spec_hash                               │
│                                                                             │
│      if current_hash is None or current_hash != expected_hash:             │
│          # Venv doesn't exist or is stale                                  │
│          create_venv(workspace, env_spec)                                   │
│          workspace.venv_spec_hash = expected_hash                          │
│          emit VenvCreatedEvent(...)                                        │
│      else:                                                                  │
│          # Reuse existing venv                                              │
│          emit VenvReusedEvent(...)                                         │
│                                                                             │
│      return workspace.venv_dir                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.5 Venv Domain Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VENV DOMAIN EVENTS                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Add to: wtb/domain/events/environment_events.py                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  VenvCreatedEvent(WTBEvent)                                          │   │
│  │  ──────────────────────────                                          │   │
│  │  • workspace_id: str                                                 │   │
│  │  • execution_id: str                                                 │   │
│  │  • venv_path: str                                                    │   │
│  │  • python_version: str                                               │   │
│  │  • packages: List[str]                                               │   │
│  │  • venv_spec_hash: str                                               │   │
│  │  • creation_time_ms: float                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  VenvReusedEvent(WTBEvent)                                           │   │
│  │  ─────────────────────────                                           │   │
│  │  • workspace_id: str                                                 │   │
│  │  • venv_path: str                                                    │   │
│  │  • venv_spec_hash: str                                               │   │
│  │  • original_creation_time: datetime                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  VenvInvalidatedEvent(WTBEvent)                                      │   │
│  │  ──────────────────────────────                                      │   │
│  │  • node_id: str                                                      │   │
│  │  • old_spec_hash: str                                                │   │
│  │  • new_spec_hash: str                                                │   │
│  │  • reason: str  # "dependency_change" | "python_version_change"     │   │
│  │  • affected_workspaces: List[str]                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  VenvMismatchWarningEvent(WTBEvent)                                  │   │
│  │  ──────────────────────────────────                                  │   │
│  │  • checkpoint_id: int                                                │   │
│  │  • expected_venv_hash: str                                           │   │
│  │  • current_venv_hash: str                                            │   │
│  │  • expected_packages: List[str]                                      │   │
│  │  • current_packages: List[str]                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  VenvRestoredEvent(WTBEvent)                                         │   │
│  │  ───────────────────────────                                         │   │
│  │  • workspace_id: str                                                 │   │
│  │  • checkpoint_id: int                                                │   │
│  │  • venv_path: str                                                    │   │
│  │  • restored_from: str  # "lock_snapshot" | "spec_recreation"        │   │
│  │  • restore_time_ms: float                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.6 Integration with Ray Runtime Environment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAY RUNTIME_ENV INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Current Ray Options (Limited):                                             │
│  ══════════════════════════════                                             │
│                                                                             │
│  actor = VariantExecutionActor.options(                                     │
│      num_cpus=1.0,                                                          │
│      memory=2GB,                                                            │
│  ).remote(...)                                                              │
│                                                                             │
│  ← No per-variant venv specification!                                       │
│                                                                             │
│  Proposed Ray Options (With Workspace Venv):                                │
│  ═══════════════════════════════════════════                                │
│                                                                             │
│  workspace = WorkspaceManager.get_workspace(workspace_id)                   │
│                                                                             │
│  actor = VariantExecutionActor.options(                                     │
│      num_cpus=1.0,                                                          │
│      memory=2GB,                                                            │
│      runtime_env={                                                          │
│          # Use workspace-isolated Python                                    │
│          "py_executable": workspace.python_path,                            │
│                                                                             │
│          # Set environment variables                                        │
│          "env_vars": {                                                      │
│              "VIRTUAL_ENV": str(workspace.venv_dir),                        │
│              "WTB_WORKSPACE_ID": workspace_id,                              │
│              "WTB_EXECUTION_ID": execution_id,                              │
│          },                                                                 │
│                                                                             │
│          # Working directory is workspace root                              │
│          "working_dir": str(workspace.root_path),                           │
│      },                                                                     │
│  ).remote(                                                                  │
│      workspace_id=workspace_id,                                             │
│      # ... other args                                                       │
│  )                                                                          │
│                                                                             │
│  Result:                                                                    │
│  • Each Ray actor uses workspace-specific Python interpreter                │
│  • Packages are isolated per workspace                                      │
│  • Working directory is isolated                                            │
│  • Environment variables scoped to workspace                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.7 Venv Management Implementation Phases

| Phase | Task | Files | Priority |
|-------|------|-------|----------|
| **V1** | Add venv_dir to Workspace | `wtb/domain/models/workspace.py` | P0 |
| **V1** | Add venv_spec_hash tracking | `wtb/infrastructure/workspace/manager.py` | P0 |
| **V1** | Integrate UV Venv Manager in workspace creation | Same | P0 |
| **V2** | Ray runtime_env with workspace venv | `ray_batch_runner.py` | P0 |
| **V2** | Venv domain events | `wtb/domain/events/environment_events.py` | P1 |
| **V3** | Venv hash in checkpoint metadata | State adapters | P1 |
| **V3** | Rollback venv mismatch detection | `wtb/application/services/` | P1 |
| **V4** | Node update venv invalidation | `wtb/sdk/workflow_project.py` | P2 |
| **V4** | Venv lock snapshot for rollback | FileTracker integration | P2 |

---

## Summary

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Workspace per variant | Complete isolation, no race conditions |
| Hard links for efficiency | Avoid copying large files |
| Pre-fork snapshot | Capture source state before branching |
| Same graph, different threads | LangGraph native design |
| Workspace for rollback | Consistent file restore |
| **Venv per workspace** | **Dependency isolation between variants** |
| **Venv spec hash tracking** | **Invalidation detection, rollback compatibility** |
| Event-driven lifecycle | Audit trail, debugging |

### Critical Requirements

1. **Workspace MUST be created before fork** - Source snapshot ensures consistency
2. **Workspace MUST be activated during execution** - CWD isolation
3. **FileTracker MUST restore to workspace** - Not to shared filesystem
4. **Venv MUST be created per workspace** - No package conflicts between variants
5. **Venv spec hash MUST be tracked** - Enable invalidation and rollback detection
6. **Events MUST be emitted** - Audit trail completeness
7. **Failed workspaces SHOULD be preserved** - Debugging capability

### Complete Isolation Checklist

| Resource | Parallel Execution | Fork | Rollback | Node Update |
|----------|-------------------|------|----------|-------------|
| **Graph State** | ✅ Thread ID | ✅ Thread ID | ✅ Checkpoint | ✅ Version |
| **File System** | 🆕 Workspace | 🆕 Clone | 🆕 Restore | N/A |
| **Venv/Packages** | 🆕 Per-workspace | 🆕 Clone | 🆕 Hash check | 🆕 Invalidate |
| **Environment Vars** | 🆕 Workspace scoped | 🆕 Clone | N/A | N/A |

Legend: ✅ = Existing, 🆕 = New in this design

---

## 11. Ray Thread/Process Lifecycle for Rollback, Fork, Parallel, and Pause/Resume

### 11.1 Current Ray Architecture Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT RAY ACTOR ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  RayBatchTestRunner (Main Process)                                          │
│  ══════════════════════════════════                                         │
│  • Orchestrates batch tests                                                 │
│  • Manages ActorPool                                                        │
│  • Tracks ObjectRefs for cancellation                                       │
│                                                                             │
│  VariantExecutionActor (Ray Actor Process)                                  │
│  ══════════════════════════════════════════                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  @ray.remote(num_cpus=1.0, memory=2GB, max_restarts=3)              │   │
│  │                                                                      │   │
│  │  Internal State (Per Actor):                                         │   │
│  │  ├── _uow (UnitOfWork)           ← DB connection                    │   │
│  │  ├── _state_adapter              ← AgentGit/LangGraph adapter       │   │
│  │  ├── _execution_controller       ← Workflow orchestration           │   │
│  │  ├── _file_tracking_service      ← FileTracker connection           │   │
│  │  └── _initialized (bool)         ← Lazy init flag                   │   │
│  │                                                                      │   │
│  │  Resources Held:                                                     │   │
│  │  ├── PostgreSQL connections (pooled)                                │   │
│  │  ├── GPU memory (if num_gpus > 0)                                   │   │
│  │  ├── File handles                                                   │   │
│  │  └── Network sockets (gRPC to UV Venv Manager)                      │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Lifecycle Events:                                                          │
│  ═════════════════                                                          │
│  ✅ Actor Created    → Ray allocates resources                             │
│  ✅ Actor Executes   → execute_variant() called                            │
│  ✅ Actor Killed     → shutdown() calls ray.kill()                         │
│  ❌ Actor Paused     → NOT SUPPORTED in Ray                                │
│  ❌ Actor Resumed    → NOT SUPPORTED in Ray                                │
│  ❌ Actor Rollback   → State restored, but resources NOT released          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Gaps by Operation

#### 11.2.1 Parallel Execution (Current - Partial)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARALLEL: RAY ACTOR ISOLATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHAT WORKS:                                                                │
│  ════════════                                                               │
│  • Each variant gets separate Ray actor                                     │
│  • CPU/Memory isolation via Ray scheduler                                   │
│  • Database connections are per-actor                                       │
│  • LangGraph thread_id provides state isolation                            │
│                                                                             │
│  WHAT'S MISSING:                                                            │
│  ═══════════════                                                            │
│  • File system isolation (addressed in §4)                                  │
│  • Venv isolation (addressed in §10)                                        │
│  • Resource cleanup on variant completion                                   │
│                                                                             │
│  Actor Pool Reuse Issue:                                                    │
│  ═══════════════════════                                                    │
│                                                                             │
│  Current:                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ActorPool(5 actors)                                                 │   │
│  │  ├── Actor 1: executes variant_A → KEEPS state → executes variant_F│   │
│  │  ├── Actor 2: executes variant_B → KEEPS state → executes variant_G│   │
│  │  └── ...                                                            │   │
│  │                                                                      │   │
│  │  Problem: Actor state from variant_A may leak to variant_F          │   │
│  │  • _checkpoint_links_cache not cleared                              │   │
│  │  • _initialized stays True (stale connections possible)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Proposed:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Actor reset between variants:                                       │   │
│  │  def reset_for_new_variant(self):                                    │   │
│  │      self._checkpoint_links_cache.clear()                           │   │
│  │      self._execution_controller = None  # Force recreation          │   │
│  │      if self._file_tracking_service:                                │   │
│  │          self._file_tracking_service.close()                        │   │
│  │      # Re-initialize on next execution                              │   │
│  │      self._initialized = False                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.2.2 Rollback (Current - BROKEN)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROLLBACK: RAY ACTOR STATE GAP                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Current Rollback Flow:                                                     │
│  ═══════════════════════                                                    │
│                                                                             │
│  User: "Rollback execution exec-001 to checkpoint CP3"                      │
│                                                                             │
│  1. ExecutionController.rollback(exec-001, CP3)                             │
│     ├── _state_adapter.rollback(CP3)                                       │
│     │   ├── LangGraph: graph.get_state(config_cp3) ✅ Graph state restored│
│     │   └── ToolManager.rollback_to_position() ✅ Tool track restored      │
│     │                                                                       │
│     └── execution.state = restored_state ✅ Domain model updated           │
│                                                                             │
│  WHAT'S NOT RESTORED:                                                       │
│  ════════════════════                                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Ray Actor State (STILL AT POST-CP3):                                │   │
│  │                                                                      │   │
│  │  • Database connections: Still open, may have uncommitted txns      │   │
│  │  • GPU memory: Models loaded after CP3 still resident               │   │
│  │  • File handles: Files opened after CP3 still open                  │   │
│  │  • Network sockets: Connections made after CP3 still active         │   │
│  │  • Process state: Thread-local storage, caches, etc.                │   │
│  │                                                                      │   │
│  │  Result: "Restored" execution continues with CONTAMINATED state     │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Example Failure Scenario:                                                  │
│  ═════════════════════════                                                  │
│                                                                             │
│  Timeline:                                                                  │
│  T1: CP1 created (GPU: empty)                                              │
│  T2: Node loads 10GB model to GPU                                          │
│  T3: CP2 created (GPU: 10GB used)                                          │
│  T4: Node loads another 5GB model                                          │
│  T5: OOM error                                                              │
│  T6: User rolls back to CP1                                                 │
│                                                                             │
│  Expected: GPU memory cleared to CP1 state (empty)                         │
│  Actual: GPU still has 10GB model (from T2) + possibly 5GB fragments       │
│                                                                             │
│  → OOM persists even after rollback!                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.2.3 Fork (Current - NO IMPLEMENTATION)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FORK: NEW ACTOR REQUIRED                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Fork Scenarios:                                                            │
│  ════════════════                                                           │
│                                                                             │
│  1. Variant Fork (Batch Testing):                                           │
│     • From initial state → Multiple parallel variants                       │
│     • Each needs separate actor (CURRENT: ✅ works)                        │
│                                                                             │
│  2. Rollback Branch Fork:                                                   │
│     • From checkpoint → Create new execution branch                         │
│     • Needs new actor OR actor reset (CURRENT: ❌ NOT IMPLEMENTED)         │
│                                                                             │
│  3. Manual Fork:                                                            │
│     • User explicitly creates branch mid-execution                          │
│     • CURRENT: ❌ NOT IMPLEMENTED                                          │
│                                                                             │
│  Problem: Fork from Running Actor                                           │
│  ═════════════════════════════════                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Actor running exec-001:                                             │   │
│  │  ├── CP1 → CP2 → CP3 (current)                                      │   │
│  │  │                                                                   │   │
│  │  User: "Fork from CP2 to new execution branch-001"                  │   │
│  │  │                                                                   │   │
│  │  Options:                                                            │   │
│  │  ├── A. Reuse same actor (BROKEN - contaminated state)              │   │
│  │  ├── B. Create new actor (CORRECT - clean state)                    │   │
│  │  └── C. Clone actor state (IMPOSSIBLE - Ray doesn't support)        │   │
│  │                                                                      │   │
│  │  Only Option B is viable!                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Proposed Fork Flow:                                                        │
│  ═══════════════════                                                        │
│                                                                             │
│  1. Create new workspace for branch (files + venv)                          │
│  2. Create NEW Ray actor for branch                                         │
│  3. Initialize actor with:                                                  │
│     ├── workspace_id = branch workspace                                     │
│     ├── thread_id = new thread (LangGraph fork)                            │
│     ├── checkpoint_id = fork point (for state restoration)                 │
│     └── runtime_env = branch workspace venv                                │
│  4. Actor loads state from fork point checkpoint                           │
│  5. Branch execution proceeds independently                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.2.4 Pause/Resume (Current - PARTIAL)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PAUSE/RESUME: RESOURCE INHERITANCE GAPS                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Current Pause Implementation:                                              │
│  ═════════════════════════════                                              │
│                                                                             │
│  ExecutionController.pause():                                               │
│  ├── Creates checkpoint (state saved) ✅                                   │
│  ├── execution.pause() (status changed) ✅                                 │
│  └── Actor continues running (resources HELD) ⚠️                           │
│                                                                             │
│  Resource Inheritance During Pause:                                         │
│  ════════════════════════════════════                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PAUSED Actor State:                                                 │   │
│  │                                                                      │   │
│  │  Resource          │ During Pause   │ After Resume   │ Problem      │   │
│  │  ──────────────────┼────────────────┼────────────────┼─────────────│   │
│  │  DB Connection     │ HELD (idle)    │ Reused         │ Timeout?    │   │
│  │  GPU Memory        │ HELD (wasted)  │ Reused         │ $$$ cost    │   │
│  │  File Handles      │ HELD           │ Reused         │ Lock issues │   │
│  │  Network Sockets   │ HELD           │ May be stale   │ Reconnect?  │   │
│  │  Thread-local      │ PRESERVED      │ PRESERVED      │ Leaky state │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Long Pause Scenario:                                                       │
│  ════════════════════                                                       │
│                                                                             │
│  T1: User pauses execution (going to lunch)                                │
│  T2: Actor holds GPU memory for 2 hours                                    │
│  T3: DB connection times out (server-side)                                 │
│  T4: User resumes                                                          │
│  T5: Actor tries to use stale DB connection → ERROR                        │
│                                                                             │
│  Pause Strategy Options:                                                    │
│  ═══════════════════════                                                    │
│                                                                             │
│  Option A: "Hot Pause" (Current)                                            │
│  ├── Actor stays alive, resources held                                     │
│  ├── Fast resume                                                           │
│  └── Expensive, connections may go stale                                   │
│                                                                             │
│  Option B: "Cold Pause" (Proposed for long pause)                          │
│  ├── Save full state to checkpoint                                         │
│  ├── Kill actor, release all resources                                     │
│  ├── On resume: create new actor, restore from checkpoint                  │
│  └── Slower resume, but no resource waste                                  │
│                                                                             │
│  Option C: "Warm Pause" (Hybrid)                                            │
│  ├── Release expensive resources (GPU, large models)                       │
│  ├── Keep actor alive with minimal state                                   │
│  ├── Reconnect/reload on resume                                            │
│  └── Balance between speed and cost                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Proposed Ray Lifecycle Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: RAY ACTOR LIFECYCLE MANAGER                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  New Component: ActorLifecycleManager                                       │
│  ════════════════════════════════════                                       │
│                                                                             │
│  class ActorLifecycleManager:                                               │
│      """                                                                    │
│      Manages Ray actor lifecycle for WTB operations.                       │
│                                                                             │
│      Responsibilities:                                                      │
│      - Actor creation with workspace/venv binding                          │
│      - Resource cleanup between variant executions                         │
│      - Pause strategies (hot/cold/warm)                                    │
│      - Rollback handling (actor reset or recreation)                       │
│      - Fork handling (new actor creation)                                  │
│      """                                                                    │
│                                                                             │
│      def create_actor(                                                      │
│          self,                                                              │
│          execution_id: str,                                                 │
│          workspace_id: str,                                                 │
│          config: ActorConfig,                                               │
│      ) -> ActorHandle:                                                      │
│          """Create actor bound to workspace."""                             │
│                                                                             │
│      def reset_actor(self, actor: ActorHandle) -> None:                     │
│          """Reset actor state for new variant (pool reuse)."""              │
│                                                                             │
│      def pause_actor(                                                       │
│          self,                                                              │
│          actor: ActorHandle,                                                │
│          strategy: PauseStrategy,  # HOT, COLD, WARM                       │
│      ) -> PausedActorState:                                                 │
│          """Pause actor with resource management."""                        │
│                                                                             │
│      def resume_actor(                                                      │
│          self,                                                              │
│          paused_state: PausedActorState,                                    │
│      ) -> ActorHandle:                                                      │
│          """Resume actor, recreating if cold pause."""                      │
│                                                                             │
│      def handle_rollback(                                                   │
│          self,                                                              │
│          actor: ActorHandle,                                                │
│          checkpoint_id: int,                                                │
│          strategy: RollbackStrategy,  # RESET, RECREATE                    │
│      ) -> ActorHandle:                                                      │
│          """Handle rollback with proper resource cleanup."""                │
│                                                                             │
│      def fork_actor(                                                        │
│          self,                                                              │
│          source_checkpoint_id: int,                                         │
│          new_workspace_id: str,                                             │
│          new_execution_id: str,                                             │
│      ) -> ActorHandle:                                                      │
│          """Create new actor for fork operation."""                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.4 Operation Flows (Proposed)

#### 11.4.1 Rollback Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: ROLLBACK FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User: "Rollback exec-001 to CP3"                                           │
│                                                                             │
│  1. RollbackRequestedEvent                                                  │
│                                                                             │
│  2. Determine rollback strategy:                                            │
│     IF checkpoint is "recent" (within same node):                          │
│         strategy = RESET (fast, reset actor state)                         │
│     ELSE:                                                                   │
│         strategy = RECREATE (clean, new actor)                             │
│                                                                             │
│  3. If RESET strategy:                                                      │
│     ┌───────────────────────────────────────────────────────────────────┐  │
│     │  actor.reset_state()                                               │  │
│     │  ├── Clear in-memory caches                                       │  │
│     │  ├── Rollback DB transaction if any                               │  │
│     │  ├── Release GPU memory (torch.cuda.empty_cache())                │  │
│     │  └── Close file handles opened after checkpoint                   │  │
│     │                                                                    │  │
│     │  _state_adapter.rollback(checkpoint_id)                           │  │
│     │  _file_tracking.restore_from_checkpoint(checkpoint_id)            │  │
│     │                                                                    │  │
│     │  ActorResetEvent                                                   │  │
│     └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  4. If RECREATE strategy:                                                   │
│     ┌───────────────────────────────────────────────────────────────────┐  │
│     │  ray.kill(current_actor)                                          │  │
│     │  ActorKilledEvent                                                  │  │
│     │                                                                    │  │
│     │  new_actor = create_actor(                                         │  │
│     │      execution_id=exec_id,                                         │  │
│     │      workspace_id=existing_workspace,                              │  │
│     │      from_checkpoint=checkpoint_id,                                │  │
│     │  )                                                                 │  │
│     │  ActorCreatedEvent                                                 │  │
│     │                                                                    │  │
│     │  _file_tracking.restore_from_checkpoint(checkpoint_id)            │  │
│     │  _venv_manager.verify_venv_hash(checkpoint_metadata.venv_hash)    │  │
│     └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  5. RollbackCompletedEvent                                                  │
│     ├── strategy_used                                                       │
│     ├── actor_recreated: bool                                               │
│     ├── resources_released: List[str]                                       │
│     └── state_restored: True                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.4.2 Fork Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: FORK FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User: "Fork exec-001 from CP2 to new branch"                               │
│                                                                             │
│  1. ForkRequestedEvent                                                      │
│                                                                             │
│  2. Create branch workspace:                                                │
│     ┌───────────────────────────────────────────────────────────────────┐  │
│     │  branch_workspace = WorkspaceManager.create_branch_workspace(      │  │
│     │      source_workspace_id="exec-001",                               │  │
│     │      fork_checkpoint_id=CP2,                                       │  │
│     │      new_execution_id="branch-001",                                │  │
│     │  )                                                                 │  │
│     │                                                                    │  │
│     │  # Copies:                                                         │  │
│     │  # - File state from CP2's FileCommit                             │  │
│     │  # - Venv (if compatible) or creates new                          │  │
│     │                                                                    │  │
│     │  WorkspaceCreatedEvent                                             │  │
│     └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  3. Create new LangGraph thread:                                            │
│     ┌───────────────────────────────────────────────────────────────────┐  │
│     │  fork_config = {                                                   │  │
│     │      "configurable": {                                             │  │
│     │          "thread_id": "branch-001",   # NEW thread                │  │
│     │          "checkpoint_id": CP2,         # Fork point               │  │
│     │      }                                                             │  │
│     │  }                                                                 │  │
│     │  graph.get_state(fork_config)  # Initialize new thread            │  │
│     │                                                                    │  │
│     │  BranchCreatedEvent                                                │  │
│     └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  4. Create NEW actor for branch:                                            │
│     ┌───────────────────────────────────────────────────────────────────┐  │
│     │  branch_actor = VariantExecutionActor.options(                     │  │
│     │      runtime_env={                                                 │  │
│     │          "py_executable": branch_workspace.python_path,            │  │
│     │          "working_dir": branch_workspace.root_path,                │  │
│     │      },                                                            │  │
│     │  ).remote(                                                         │  │
│     │      workspace_id=branch_workspace.id,                             │  │
│     │      thread_id="branch-001",                                       │  │
│     │      from_checkpoint=CP2,                                          │  │
│     │  )                                                                 │  │
│     │                                                                    │  │
│     │  ActorCreatedEvent(for_fork=True)                                  │  │
│     └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  5. ForkCompletedEvent                                                      │
│     ├── new_execution_id: "branch-001"                                      │
│     ├── new_workspace_id                                                    │
│     ├── new_thread_id                                                       │
│     └── actor_created: True                                                 │
│                                                                             │
│  Note: Source execution (exec-001) continues UNAFFECTED on original actor  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.4.3 Pause/Resume Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED: PAUSE/RESUME FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Pause Strategies:                                                          │
│  ═════════════════                                                          │
│                                                                             │
│  class PauseStrategy(Enum):                                                 │
│      HOT = "hot"      # Keep actor alive, fast resume, expensive           │
│      WARM = "warm"    # Release GPU/large resources, keep actor            │
│      COLD = "cold"    # Kill actor, release all, slow resume               │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  HOT PAUSE (Default for short pause < 5 min):                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  pause(strategy=HOT):                                                  │ │
│  │  ├── Create checkpoint ✅                                             │ │
│  │  ├── execution.pause() ✅                                             │ │
│  │  └── Actor keeps running (all resources held)                         │ │
│  │                                                                        │ │
│  │  resume():                                                             │ │
│  │  ├── Verify actor health (connections alive?)                         │ │
│  │  │   ├── If healthy: continue immediately                            │ │
│  │  │   └── If stale: reconnect or switch to COLD resume                │ │
│  │  └── execution.resume()                                               │ │
│  │                                                                        │ │
│  │  Resources inherited: ALL (DB, GPU, Files, Network)                   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  WARM PAUSE (For medium pause 5-60 min):                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  pause(strategy=WARM):                                                 │ │
│  │  ├── Create checkpoint                                                │ │
│  │  ├── Release expensive resources:                                     │ │
│  │  │   ├── torch.cuda.empty_cache()                                    │ │
│  │  │   ├── Unload large models                                         │ │
│  │  │   └── Close idle DB connections                                   │ │
│  │  ├── Keep actor alive (minimal memory)                                │ │
│  │  └── ResourcesReleasedEvent                                           │ │
│  │                                                                        │ │
│  │  resume():                                                             │ │
│  │  ├── Reconnect DB connections                                         │ │
│  │  ├── Reload models (if needed by next node)                          │ │
│  │  ├── ResourcesReacquiredEvent                                         │ │
│  │  └── execution.resume()                                               │ │
│  │                                                                        │ │
│  │  Resources inherited: Code state, workspace binding                   │ │
│  │  Resources reacquired: GPU, large models, DB connections              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  COLD PAUSE (For long pause > 60 min, or explicit):                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  pause(strategy=COLD):                                                 │ │
│  │  ├── Create checkpoint (full state snapshot)                          │ │
│  │  ├── Save actor metadata:                                             │ │
│  │  │   ├── workspace_id                                                │ │
│  │  │   ├── venv_spec_hash                                              │ │
│  │  │   ├── execution_id                                                │ │
│  │  │   └── actor_config (resources)                                    │ │
│  │  ├── ray.kill(actor)                                                  │ │
│  │  └── ActorKilledEvent(reason="cold_pause")                            │ │
│  │                                                                        │ │
│  │  resume():                                                             │ │
│  │  ├── new_actor = create_actor(from saved metadata)                   │ │
│  │  ├── ActorCreatedEvent(for_resume=True)                               │ │
│  │  ├── Restore checkpoint state                                         │ │
│  │  ├── Verify workspace and venv                                        │ │
│  │  └── execution.resume()                                               │ │
│  │                                                                        │ │
│  │  Resources inherited: NONE (all recreated)                            │ │
│  │  Cost: Zero during pause, full recreation on resume                   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  Automatic Strategy Selection:                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  def select_pause_strategy(                                            │ │
│  │      expected_pause_duration: Optional[timedelta],                     │ │
│  │      actor_resources: ActorResources,                                  │ │
│  │  ) -> PauseStrategy:                                                   │ │
│  │      if expected_pause_duration is None:                              │ │
│  │          # User didn't specify, use WARM as default                   │ │
│  │          return PauseStrategy.WARM                                    │ │
│  │                                                                        │ │
│  │      if expected_pause_duration < timedelta(minutes=5):               │ │
│  │          return PauseStrategy.HOT                                     │ │
│  │                                                                        │ │
│  │      if actor_resources.gpu_memory_gb > 4:                            │ │
│  │          # Expensive GPU resources, release them                      │ │
│  │          if expected_pause_duration > timedelta(hours=1):             │ │
│  │              return PauseStrategy.COLD                                │ │
│  │          return PauseStrategy.WARM                                    │ │
│  │                                                                        │ │
│  │      if expected_pause_duration > timedelta(hours=1):                 │ │
│  │          return PauseStrategy.COLD                                    │ │
│  │                                                                        │ │
│  │      return PauseStrategy.WARM                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.5 New Domain Events

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAY LIFECYCLE EVENTS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Add to: wtb/domain/events/ray_lifecycle_events.py                          │
│                                                                             │
│  # Actor Events                                                             │
│  ActorCreatedEvent                                                          │
│  ├── actor_id: str                                                          │
│  ├── execution_id: str                                                      │
│  ├── workspace_id: str                                                      │
│  ├── for_fork: bool                                                         │
│  ├── for_resume: bool                                                       │
│  └── resources: {num_cpus, num_gpus, memory}                               │
│                                                                             │
│  ActorResetEvent                                                            │
│  ├── actor_id: str                                                          │
│  ├── reason: str  # "variant_switch" | "rollback"                          │
│  └── resources_cleared: List[str]                                          │
│                                                                             │
│  ActorKilledEvent                                                           │
│  ├── actor_id: str                                                          │
│  ├── reason: str  # "cold_pause" | "rollback_recreate" | "shutdown"        │
│  └── resources_released: List[str]                                         │
│                                                                             │
│  # Resource Events                                                          │
│  ResourcesReleasedEvent                                                     │
│  ├── actor_id: str                                                          │
│  ├── reason: str  # "warm_pause" | "memory_pressure"                       │
│  ├── gpu_memory_freed_mb: float                                            │
│  └── resources_list: List[str]                                             │
│                                                                             │
│  ResourcesReacquiredEvent                                                   │
│  ├── actor_id: str                                                          │
│  ├── gpu_memory_allocated_mb: float                                        │
│  └── reacquisition_time_ms: float                                          │
│                                                                             │
│  # Connection Events                                                        │
│  ConnectionStaleEvent                                                       │
│  ├── actor_id: str                                                          │
│  ├── connection_type: str  # "database" | "grpc" | "network"               │
│  └── stale_duration_seconds: float                                         │
│                                                                             │
│  ConnectionReconnectedEvent                                                 │
│  ├── actor_id: str                                                          │
│  ├── connection_type: str                                                   │
│  └── reconnection_time_ms: float                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.6 Implementation Phases

| Phase | Task | Files | Priority |
|-------|------|-------|----------|
| **R1** | Add ActorLifecycleManager | `wtb/application/services/actor_lifecycle.py` | P0 |
| **R1** | Add reset_for_new_variant() to actor | `ray_batch_runner.py` | P0 |
| **R2** | Implement HOT pause | `execution_controller.py`, `actor_lifecycle.py` | P1 |
| **R2** | Implement COLD pause | Same | P1 |
| **R3** | Implement WARM pause | Same | P2 |
| **R3** | Add automatic strategy selection | Same | P2 |
| **R4** | Implement fork with new actor | `actor_lifecycle.py` | P1 |
| **R4** | Implement rollback strategies | Same | P1 |
| **R5** | Ray lifecycle events | `wtb/domain/events/ray_lifecycle_events.py` | P1 |

---

## 12. Production Risks & Mitigations

### 12.1 Windows Hard Links (NTFS Cross-Partition Limitation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WINDOWS HARD LINK RISK                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Problem:                                                                   │
│  ════════                                                                   │
│  Hard links on NTFS CANNOT cross drive partitions.                         │
│                                                                             │
│  ✅ Works:    D:\source\file.txt → D:\workspaces\exec-001\file.txt         │
│  ❌ Fails:    C:\source\file.txt → D:\workspaces\exec-001\file.txt         │
│                                                                             │
│  Current Environment:                                                       │
│  ════════════════════                                                       │
│  • OS: Windows 10.0.26200                                                   │
│  • Workspace Path: D:\12-22                                                 │
│  • Risk: Source files on different drive than workspace base_dir           │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  RULE: base_dir for workspaces MUST be on same volume as source_paths      │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  Mitigation Strategy:                                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  def create_file_link(source: Path, target: Path) -> LinkResult:       │ │
│  │      """                                                               │ │
│  │      Create hard link with cross-partition fallback.                   │ │
│  │      """                                                               │ │
│  │      # Check if same volume (Windows: same drive letter)               │ │
│  │      if source.drive != target.drive:                                  │ │
│  │          logger.warning(                                               │ │
│  │              f"Cross-partition link {source.drive} → {target.drive}, " │ │
│  │              f"falling back to copy"                                   │ │
│  │          )                                                             │ │
│  │          shutil.copy2(source, target)  # Preserve metadata            │ │
│  │          return LinkResult(method="copy", size=target.stat().st_size)  │ │
│  │                                                                        │ │
│  │      try:                                                              │ │
│  │          target.hardlink_to(source)  # Python 3.10+                   │ │
│  │          return LinkResult(method="hardlink", size=0)  # No new space │ │
│  │      except OSError as e:                                              │ │
│  │          # Fallback reasons: permissions, max links, filesystem       │ │
│  │          logger.warning(f"Hard link failed: {e}, falling back to copy")│ │
│  │          shutil.copy2(source, target)                                  │ │
│  │          return LinkResult(method="copy", size=target.stat().st_size)  │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Configuration Validation:                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  @dataclass                                                            │ │
│  │  class WorkspaceConfig:                                                │ │
│  │      base_dir: Path                                                    │ │
│  │      source_paths: List[Path]                                          │ │
│  │                                                                        │ │
│  │      def __post_init__(self):                                          │ │
│  │          if sys.platform == "win32":                                   │ │
│  │              base_drive = self.base_dir.drive.upper()                  │ │
│  │              cross_partition = [                                       │ │
│  │                  p for p in self.source_paths                          │ │
│  │                  if p.drive.upper() != base_drive                      │ │
│  │              ]                                                         │ │
│  │              if cross_partition:                                       │ │
│  │                  logger.warning(                                       │ │
│  │                      f"Cross-partition sources detected: "             │ │
│  │                      f"{[str(p) for p in cross_partition]}. "          │ │
│  │                      f"Hard links will fallback to file copy."         │ │
│  │                  )                                                     │ │
│  │                  self._cross_partition_warning_emitted = True          │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Performance Impact:                                                        │
│  ══════════════════                                                         │
│  • Hard link: ~0ms (just creates directory entry)                          │
│  • shutil.copy2: ~10ms per MB (full data copy)                             │
│  • 100 variants × 500MB data = 50GB disk I/O if copying!                   │
│                                                                             │
│  Recommendation: Configure base_dir on SAME drive as source repository     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Orphan Workspace Cleanup (Zombie Problem)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORPHAN WORKSPACE PROBLEM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Problem:                                                                   │
│  ════════                                                                   │
│  If main process (RayBatchRunner) crashes hard (SIGKILL, power loss),      │
│  temporary workspace folders remain on disk indefinitely.                   │
│                                                                             │
│  Scenario:                                                                  │
│  ─────────                                                                  │
│  1. Batch test creates 100 workspaces                                       │
│  2. Process killed (OOM, user kill, system crash)                          │
│  3. Workspaces remain: D:\workspaces\exec-001\, exec-002\, ...             │
│  4. Next run creates MORE workspaces                                        │
│  5. Disk fills up over time                                                 │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  Solution: Startup Cleanup with Lock Files                                  │
│                                                                             │
│  Workspace Structure (with lock file):                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  D:\workspaces\                                                        │ │
│  │  ├── .wtb_workspace_registry.json   # Central registry                │ │
│  │  ├── exec-001\                                                         │ │
│  │  │   ├── .workspace_lock            # Lock file with PID              │ │
│  │  │   ├── .workspace_meta.json       # Creation time, session ID       │ │
│  │  │   └── ... (workspace files)                                        │ │
│  │  └── exec-002\                                                         │ │
│  │      └── ...                                                           │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Lock File Content:                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  {                                                                     │ │
│  │    "pid": 12345,                                                       │ │
│  │    "hostname": "WORKSTATION-01",                                       │ │
│  │    "created_at": "2026-01-16T10:30:00Z",                              │ │
│  │    "session_id": "sess-abc123",                                        │ │
│  │    "batch_test_id": "batch-001"                                        │ │
│  │  }                                                                     │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Startup Cleanup Logic:                                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  class WorkspaceManager:                                               │ │
│  │      def __init__(self, base_dir: Path, ...):                          │ │
│  │          self._base_dir = base_dir                                     │ │
│  │          self._cleanup_orphans()  # Run on startup                    │ │
│  │                                                                        │ │
│  │      def _cleanup_orphans(self) -> CleanupReport:                      │ │
│  │          """                                                           │ │
│  │          Clean up zombie workspaces from dead sessions.                │ │
│  │          """                                                           │ │
│  │          orphans = []                                                  │ │
│  │          for ws_dir in self._base_dir.iterdir():                       │ │
│  │              if not ws_dir.is_dir():                                   │ │
│  │                  continue                                              │ │
│  │                                                                        │ │
│  │              lock_file = ws_dir / ".workspace_lock"                    │ │
│  │              if not lock_file.exists():                                │ │
│  │                  continue  # Not a managed workspace                   │ │
│  │                                                                        │ │
│  │              lock_data = json.loads(lock_file.read_text())             │ │
│  │              pid = lock_data["pid"]                                    │ │
│  │                                                                        │ │
│  │              if not self._is_process_alive(pid):                       │ │
│  │                  orphans.append(OrphanWorkspace(                       │ │
│  │                      path=ws_dir,                                      │ │
│  │                      pid=pid,                                          │ │
│  │                      created_at=lock_data["created_at"],               │ │
│  │                      age=datetime.now() - parse(lock_data["created_at"])│ │
│  │                  ))                                                    │ │
│  │                                                                        │ │
│  │          # Clean up orphans                                            │ │
│  │          for orphan in orphans:                                        │ │
│  │              if orphan.age > timedelta(hours=1):  # Grace period      │ │
│  │                  logger.info(f"Cleaning orphan workspace: {orphan.path}")│ │
│  │                  shutil.rmtree(orphan.path)                            │ │
│  │                  OrphanWorkspaceCleanedEvent(...)                      │ │
│  │              else:                                                     │ │
│  │                  logger.debug(f"Recent orphan, keeping: {orphan.path}")│ │
│  │                                                                        │ │
│  │          return CleanupReport(                                         │ │
│  │              orphans_found=len(orphans),                               │ │
│  │              orphans_cleaned=cleaned_count,                            │ │
│  │              space_freed_mb=space_freed,                               │ │
│  │          )                                                             │ │
│  │                                                                        │ │
│  │      def _is_process_alive(self, pid: int) -> bool:                    │ │
│  │          """Check if process with given PID is still running."""       │ │
│  │          try:                                                          │ │
│  │              import psutil                                             │ │
│  │              return psutil.pid_exists(pid)                             │ │
│  │          except ImportError:                                           │ │
│  │              # Fallback without psutil                                 │ │
│  │              if sys.platform == "win32":                               │ │
│  │                  import ctypes                                         │ │
│  │                  kernel32 = ctypes.windll.kernel32                     │ │
│  │                  handle = kernel32.OpenProcess(0x1000, False, pid)     │ │
│  │                  if handle:                                            │ │
│  │                      kernel32.CloseHandle(handle)                      │ │
│  │                      return True                                       │ │
│  │                  return False                                          │ │
│  │              else:                                                     │ │
│  │                  try:                                                  │ │
│  │                      os.kill(pid, 0)  # Signal 0 = check existence    │ │
│  │                      return True                                       │ │
│  │                  except OSError:                                       │ │
│  │                      return False                                      │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  New Events:                                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  OrphanWorkspaceDetectedEvent                                          │ │
│  │  ├── workspace_path: str                                               │ │
│  │  ├── original_pid: int                                                 │ │
│  │  ├── age_hours: float                                                  │ │
│  │  └── action: "cleaned" | "preserved"                                   │ │
│  │                                                                        │ │
│  │  OrphanCleanupCompletedEvent                                           │ │
│  │  ├── orphans_found: int                                                │ │
│  │  ├── orphans_cleaned: int                                              │ │
│  │  └── space_freed_mb: float                                             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Venv I/O Performance on Windows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VENV CREATION PERFORMANCE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Problem:                                                                   │
│  ════════                                                                   │
│  While uv is significantly faster than pip/venv, creating full virtual     │
│  environments for every variant fork can still be I/O heavy on Windows.    │
│                                                                             │
│  Benchmark (typical project with ~50 dependencies):                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Tool          │ Cold Create  │ Cached Create │ Notes                  │ │
│  │  ──────────────┼──────────────┼───────────────┼───────────────────────│ │
│  │  venv + pip    │ 45-90s       │ 15-30s        │ Slow, network bound   │ │
│  │  uv            │ 3-8s         │ 0.5-2s        │ Fast, local cache     │ │
│  │  uv (same spec)│ N/A          │ 0.1-0.3s      │ Hash match = skip     │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  100 variants × 3s = 300s (5 min) just for venv creation!                  │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  Solution: Venv Spec Hash Caching (Already Proposed in §10.3)              │
│                                                                             │
│  Strategy:                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  1. Compute venv_spec_hash from:                                       │ │
│  │     ├── pyproject.toml content hash                                   │ │
│  │     ├── requirements.txt hash (if exists)                             │ │
│  │     ├── uv.lock hash (if exists)                                      │ │
│  │     └── Python version                                                │ │
│  │                                                                        │ │
│  │  2. Check if venv with matching hash exists in cache:                  │ │
│  │     ├── Cache location: D:\workspaces\.venv_cache\{hash}\             │ │
│  │     └── Contains: complete venv ready to copy/link                    │ │
│  │                                                                        │ │
│  │  3. If cache hit:                                                      │ │
│  │     ├── Copy/link cached venv to workspace (~0.1-0.5s)                │ │
│  │     └── Skip uv create entirely                                       │ │
│  │                                                                        │ │
│  │  4. If cache miss:                                                     │ │
│  │     ├── Create venv with uv (~3-8s)                                   │ │
│  │     ├── Copy to cache for future reuse                                │ │
│  │     └── VenvCachePopulatedEvent                                       │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Cache Structure:                                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  D:\workspaces\                                                        │ │
│  │  ├── .venv_cache\                                                      │ │
│  │  │   ├── a1b2c3d4.../    # Hash of spec                               │ │
│  │  │   │   ├── .venv_meta.json  # Python version, creation time        │ │
│  │  │   │   ├── Lib\                                                     │ │
│  │  │   │   ├── Scripts\                                                 │ │
│  │  │   │   └── pyvenv.cfg                                               │ │
│  │  │   └── e5f6g7h8.../                                                 │ │
│  │  └── exec-001\                                                         │ │
│  │      └── .venv → (copied from cache or created fresh)                 │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Cache Eviction:                                                            │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  class VenvCache:                                                      │ │
│  │      max_size_gb: float = 10.0  # Maximum cache size                  │ │
│  │      max_age_days: int = 30     # Maximum entry age                   │ │
│  │                                                                        │ │
│  │      def evict_if_needed(self):                                        │ │
│  │          # LRU eviction when over size limit                          │ │
│  │          # Time-based eviction for stale entries                      │ │
│  │          ...                                                           │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Performance Impact with Caching:                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Scenario: 100 variants, all same dependencies                        │ │
│  │                                                                        │ │
│  │  Without cache: 100 × 3s = 300s (5 min)                               │ │
│  │  With cache:    1 × 3s + 99 × 0.3s = 33s (94% faster)                │ │
│  │                                                                        │ │
│  │  Scenario: 100 variants, 5 different dependency specs                 │ │
│  │                                                                        │ │
│  │  Without cache: 100 × 3s = 300s                                       │ │
│  │  With cache:    5 × 3s + 95 × 0.3s = 43.5s (85% faster)              │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Pause Strategy Default (Interactive Sessions)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PAUSE STRATEGY FOR INTERACTIVE SESSIONS                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Colleague's Insight:                                                       │
│  ════════════════════                                                       │
│  "Loading large LLM contexts into GPU memory takes time; discarding them   │
│   aggressively (COLD) will degrade UX."                                    │
│                                                                             │
│  Problem with COLD as Default:                                              │
│  ─────────────────────────────                                              │
│  1. User pauses to review output                                            │
│  2. COLD pause kills actor, releases GPU                                    │
│  3. User resumes after 2 minutes                                            │
│  4. New actor must reload 13B LLM model (~30-60s)                          │
│  5. Poor UX: "Why is resume so slow?"                                       │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  UPDATED: Default to WARM for Interactive Sessions                          │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  class PauseStrategySelector:                                          │ │
│  │      """                                                               │ │
│  │      Intelligent pause strategy selection.                             │ │
│  │      """                                                               │ │
│  │                                                                        │ │
│  │      def select(                                                       │ │
│  │          self,                                                         │ │
│  │          session_type: SessionType,     # INTERACTIVE | BATCH         │ │
│  │          expected_duration: Optional[timedelta],                       │ │
│  │          actor_resources: ActorResources,                              │ │
│  │          explicit_strategy: Optional[PauseStrategy],                   │ │
│  │      ) -> PauseStrategy:                                               │ │
│  │                                                                        │ │
│  │          # User explicitly requested a strategy                        │ │
│  │          if explicit_strategy:                                         │ │
│  │              return explicit_strategy                                  │ │
│  │                                                                        │ │
│  │          # Interactive sessions: Prioritize UX                         │ │
│  │          if session_type == SessionType.INTERACTIVE:                   │ │
│  │              if expected_duration and expected_duration > hours(2):    │ │
│  │                  return PauseStrategy.COLD  # Long break               │ │
│  │              return PauseStrategy.WARM  # Keep models ready           │ │
│  │                                                                        │ │
│  │          # Batch sessions: Prioritize cost                             │ │
│  │          if session_type == SessionType.BATCH:                         │ │
│  │              if actor_resources.gpu_memory_gb > 8:                     │ │
│  │                  return PauseStrategy.COLD  # Expensive GPU           │ │
│  │              return PauseStrategy.WARM                                │ │
│  │                                                                        │ │
│  │          # Unknown duration: WARM is safest default                    │ │
│  │          return PauseStrategy.WARM                                    │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  WARM Pause Behavior for LLM Workloads:                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  def warm_pause_llm_aware(actor: ActorHandle):                         │ │
│  │      """                                                               │ │
│  │      WARM pause that preserves expensive-to-load resources.            │ │
│  │      """                                                               │ │
│  │      # KEEP these (expensive to reload):                               │ │
│  │      # ├── LLM model weights in GPU memory                            │ │
│  │      # ├── Embedding model                                            │ │
│  │      # └── KV cache (if within size limit)                            │ │
│  │                                                                        │ │
│  │      # RELEASE these (cheap to recreate):                              │ │
│  │      # ├── Intermediate computation tensors                           │ │
│  │      # ├── Attention matrices (can recompute)                         │ │
│  │      # └── Temporary buffers                                          │ │
│  │                                                                        │ │
│  │      # REFRESH these (may go stale):                                   │ │
│  │      # ├── Database connections (with health check on resume)         │ │
│  │      # └── gRPC channels (lazy reconnect)                             │ │
│  │                                                                        │ │
│  │      torch.cuda.empty_cache()  # Release fragmented memory            │ │
│  │      # But DO NOT unload model weights!                                │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Resume Time Comparison:                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Resource              │ WARM Resume │ COLD Resume │ Delta            │ │
│  │  ──────────────────────┼─────────────┼─────────────┼─────────────────│ │
│  │  13B LLM model         │ 0s (cached) │ 30-60s      │ User-facing!    │ │
│  │  Embedding model       │ 0s (cached) │ 5-10s       │ Noticeable      │ │
│  │  DB connection pool    │ ~100ms      │ ~500ms      │ Minor           │ │
│  │  gRPC channel          │ ~50ms       │ ~200ms      │ Negligible      │ │
│  │  ──────────────────────┼─────────────┼─────────────┼─────────────────│ │
│  │  TOTAL                 │ ~150ms      │ 35-70s      │ 200-400x faster │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Configuration:                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  # In WorkflowProject config                                           │ │
│  │  execution:                                                            │ │
│  │    pause_strategy:                                                     │ │
│  │      default: "warm"              # Changed from previous "auto"      │ │
│  │      interactive_default: "warm"  # Always WARM for interactive       │ │
│  │      batch_default: "warm"        # WARM unless GPU > 8GB             │ │
│  │      cold_threshold_hours: 2      # Switch to COLD after 2 hours      │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.5 Risk Summary Matrix

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| **Windows Hard Links Cross-Partition** | HIGH | Drive validation + `shutil.copy2` fallback | 🆕 Designed |
| **Orphan Workspace Accumulation** | MEDIUM | Lock file + startup PID check cleanup | 🆕 Designed |
| **Venv I/O Overhead** | MEDIUM | Spec hash caching with LRU eviction | 🆕 Designed |
| **COLD Pause UX Degradation** | HIGH | Default to WARM for interactive sessions | 🆕 Designed |
| **GPU Memory Fragmentation** | LOW | `torch.cuda.empty_cache()` in WARM pause | 🆕 Designed |
| **Connection Staleness** | MEDIUM | Health check on resume, lazy reconnect | 🆕 Designed |

### 12.6 Additional Implementation Phases

| Phase | Task | Files | Priority |
|-------|------|-------|----------|
| **P1** | Hard link fallback with drive validation | `workspace_manager.py` | P0 |
| **P1** | Lock file creation/cleanup | `workspace_manager.py` | P0 |
| **P2** | Orphan cleanup on startup | `workspace_manager.py` | P1 |
| **P2** | Venv spec hash caching | `venv_manager.py` | P1 |
| **P3** | LRU cache eviction | `venv_cache.py` | P2 |
| **P3** | LLM-aware WARM pause | `actor_lifecycle.py` | P1 |

---

## Summary (Updated)

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Workspace per variant | Complete isolation, no race conditions |
| Hard links for efficiency | Avoid copying large files |
| Pre-fork snapshot | Capture source state before branching |
| Same graph, different threads | LangGraph native design |
| Workspace for rollback | Consistent file restore |
| **Venv per workspace** | **Dependency isolation between variants** |
| **Venv spec hash tracking** | **Invalidation detection, rollback compatibility** |
| **New actor for fork** | **Clean resource state, no contamination** |
| **Pause strategies (HOT/WARM/COLD)** | **Balance speed vs cost for different durations** |
| **Actor reset between variants** | **Prevent state leakage in actor pool** |
| Event-driven lifecycle | Audit trail, debugging |

### Critical Requirements

1. **Workspace MUST be created before fork** - Source snapshot ensures consistency
2. **Workspace MUST be activated during execution** - CWD isolation
3. **FileTracker MUST restore to workspace** - Not to shared filesystem
4. **Venv MUST be created per workspace** - No package conflicts between variants
5. **Venv spec hash MUST be tracked** - Enable invalidation and rollback detection
6. **Fork MUST create new actor** - Clean resource state
7. **Rollback MUST handle resource cleanup** - GPU memory, connections
8. **Pause strategy MUST match expected duration** - Cost optimization
9. **Events MUST be emitted** - Audit trail completeness
10. **Failed workspaces SHOULD be preserved** - Debugging capability

### Complete Isolation Matrix (Updated)

| Resource | Parallel | Fork | Rollback | Pause/Resume | Node Update |
|----------|----------|------|----------|--------------|-------------|
| **Graph State** | ✅ Thread ID | ✅ Thread ID | ✅ Checkpoint | ✅ Checkpoint | ✅ Version |
| **File System** | 🆕 Workspace | 🆕 Clone | 🆕 Restore | ✅ Preserved | N/A |
| **Venv** | 🆕 Per-workspace | 🆕 Clone | 🆕 Hash check | ✅ Preserved | 🆕 Invalidate |
| **Ray Actor** | ✅ Separate | 🆕 New actor | 🆕 Reset/Recreate | 🆕 Strategy | N/A |
| **DB Connections** | ✅ Per-actor | 🆕 New conn | 🆕 Reconnect | 🆕 Health check | N/A |
| **GPU Memory** | ✅ Per-actor | 🆕 Fresh | 🆕 Clear | 🆕 Release (WARM) | N/A |

Legend: ✅ = Existing, 🆕 = New in this design

---

## 13. Implementation Status (2026-01-16)

### 13.1 Completed Implementation

| Component | File | Status | Description |
|-----------|------|--------|-------------|
| **Workspace Domain Model** | `wtb/domain/models/workspace.py` | ✅ Complete | Value objects: Workspace, WorkspaceConfig, LinkResult, OrphanWorkspace, CleanupReport |
| **Workspace Events** | `wtb/domain/events/workspace_events.py` | ✅ Complete | 20+ domain events for lifecycle, fork, venv, actor operations |
| **WorkspaceManager** | `wtb/infrastructure/workspace/manager.py` | ✅ Complete | Central service with create, cleanup, orphan detection |
| **SDK Configuration** | `wtb/sdk/workflow_project.py` | ✅ Complete | WorkspaceIsolationConfig, PauseStrategyConfig |
| **Unit Tests** | `tests/test_wtb/test_workspace_manager.py` | ✅ Complete | 38 tests covering all components |
| **Integration Tests** | `tests/test_wtb/test_workspace_integration.py` | ✅ Complete | 13 tests for E2E scenarios |
| **Ray-Workspace Integration** | `wtb/application/services/ray_batch_runner.py` | ✅ Complete | WorkspaceManager integrated with RayBatchTestRunner and VariantExecutionActor |
| **Ray Integration Tests** | `tests/test_wtb/test_ray_workspace_integration.py` | ✅ Complete | 10 tests for Ray-workspace scenarios |

### 13.2 Code Structure

```
wtb/
├── domain/
│   ├── models/
│   │   └── workspace.py          # Workspace, WorkspaceConfig, LinkResult
│   └── events/
│       └── workspace_events.py   # WorkspaceCreatedEvent, ForkCompletedEvent, etc.
├── infrastructure/
│   └── workspace/
│       ├── __init__.py
│       └── manager.py            # WorkspaceManager, create_file_link
└── sdk/
    └── workflow_project.py       # WorkspaceIsolationConfig, PauseStrategyConfig

tests/test_wtb/
├── test_workspace_manager.py     # Unit tests (38 tests)
└── test_workspace_integration.py # Integration tests (13 tests)
```

### 13.3 Key Design Decisions Implemented

| Decision | Implementation | Rationale |
|----------|---------------|-----------|
| **Workspace per variant** | `WorkspaceManager.create_workspace()` | Complete file system isolation |
| **Hard links with fallback** | `create_file_link()` | Efficient on same partition, copy fallback for cross-partition |
| **Lock files for orphan detection** | `Workspace.create_lock_file()` | PID-based orphan detection on startup |
| **Venv spec hash tracking** | `compute_venv_spec_hash()` | Dependency change detection for invalidation |
| **Event-driven lifecycle** | `WorkspaceCreatedEvent`, etc. | Full audit trail via WTBEventBus |
| **Thread-safe operations** | RLock in WorkspaceManager | Safe for parallel batch testing |

### 13.4 Test Coverage

```
tests/test_wtb/test_workspace_manager.py::TestWorkspaceModel (7 tests)
tests/test_wtb/test_workspace_manager.py::TestWorkspaceConfig (3 tests)
tests/test_wtb/test_workspace_manager.py::TestVenvSpecHash (3 tests)
tests/test_wtb/test_workspace_manager.py::TestCreateFileLink (4 tests)
tests/test_wtb/test_workspace_manager.py::TestWorkspaceManager (14 tests)
tests/test_wtb/test_workspace_manager.py::TestOrphanCleanup (2 tests)
tests/test_wtb/test_workspace_manager.py::TestThreadSafety (2 tests)
tests/test_wtb/test_workspace_manager.py::TestWorkspaceEvents (3 tests)

tests/test_wtb/test_workspace_integration.py::TestParallelExecutionIsolation (2 tests)
tests/test_wtb/test_workspace_integration.py::TestEventBusIntegration (2 tests)
tests/test_wtb/test_workspace_integration.py::TestWorkspaceActivation (2 tests)
tests/test_wtb/test_workspace_integration.py::TestBranchWorkspace (2 tests)
tests/test_wtb/test_workspace_integration.py::TestBatchCleanup (2 tests)
tests/test_wtb/test_workspace_integration.py::TestVenvSpecHashIntegration (2 tests)
tests/test_wtb/test_workspace_integration.py::TestStatistics (1 test)

Total: 51 tests, all passing
```

### 13.5 Remaining Work (Future Phases)

| Phase | Task | Priority | Status |
|-------|------|----------|--------|
| **P2** | Integrate WorkspaceManager with RayBatchTestRunner | P0 | ✅ Complete |
| **P2** | Add workspace activation in VariantExecutionActor | P0 | ✅ Complete |
| **P3** | Implement ActorLifecycleManager for pause/resume | P1 | ✅ Complete (2026-01-16) |
| **P3** | Integrate UV Venv Manager for per-workspace venv | P1 | ✅ Complete (2026-01-16) |
| **P4** | FileTracker restore to workspace | P1 | ✅ Complete (2026-01-16) |
| **P4** | Venv cache with LRU eviction | P2 | ✅ Complete (2026-01-16) |
| **P5** | Add Ray E2E integration tests with real cluster | P2 | 🔜 Pending |

### 13.6 Ray-Workspace Integration Details (2026-01-16)

The following changes were made to `ray_batch_runner.py` to integrate workspace isolation:

**VariantExecutionActor changes:**
- `__init__` accepts `workspace_config` and `workspace_id` arguments
- `_ensure_initialized` initializes WorkspaceManager if workspace config provided
- `execute_variant` activates workspace before execution, deactivates in finally block
- File tracking service uses workspace output directory

**RayBatchTestRunner changes:**
- `__init__` accepts `workspace_config`, initializes WorkspaceManager
- `_create_actor_pool` passes workspace config to actors
- `run_batch_test` creates workspace per variant, passes workspace_id to actors
- `finally` block calls `cleanup_batch()` to remove all workspaces

**Test Coverage:**
```
tests/test_wtb/test_ray_workspace_integration.py::TestWorkspaceConfigSerialization (2 tests)
tests/test_wtb/test_ray_workspace_integration.py::TestWorkspaceManagerForRay (3 tests)
tests/test_wtb/test_ray_workspace_integration.py::TestWorkspaceActivation (2 tests)
tests/test_wtb/test_ray_workspace_integration.py::TestWorkspaceForVariantExecution (2 tests)
tests/test_wtb/test_ray_workspace_integration.py::TestRayWorkspaceIntegrationMock (1 test)
```

---

**Related Issues:**
- [GAP-001: State Adapter ID Mismatch](./GAP_ANALYSIS_2026_01_15_STATE_ADAPTER_ID_MISMATCH.md)

**Completed Steps:**
1. ✅ Design reviewed and approved
2. ✅ Phase 1 implemented (Core WorkspaceManager)
3. ✅ SDK configuration extended
4. ✅ Unit and integration tests created (51 tests passing)

### 13.7 Implementation Details (2026-01-16 Update)

**New Components Implemented:**

| Component | File | Description |
|-----------|------|-------------|
| **ActorLifecycleManager** | `wtb/application/services/actor_lifecycle.py` | Manages Ray actor lifecycle with pause strategies (HOT/WARM/COLD), rollback handling, and fork operations |
| **VenvCacheManager** | `wtb/infrastructure/environment/venv_cache.py` | LRU cache for virtual environments with spec hash tracking and age-based eviction |
| **GrpcEnvironmentProvider (Enhanced)** | `wtb/infrastructure/environment/providers.py` | Enhanced with workspace-bound venv creation and cache integration |
| **FileTrackerService (Enhanced)** | `wtb/infrastructure/file_tracking/filetracker_service.py` | Added `restore_to_workspace()` and `restore_checkpoint_to_workspace()` methods |

**ActorLifecycleManager Features:**
- Pause strategies: HOT (keep all), WARM (release GPU), COLD (kill actor)
- Automatic strategy selection based on session type and resources
- Rollback strategies: RESET (fast, same actor), RECREATE (clean, new actor)
- Fork operations with new actor creation
- Full event publishing for audit trail

**VenvCacheManager Features:**
- Content-addressed caching using VenvSpec hash
- LRU eviction when cache exceeds size limit
- Age-based eviction for stale entries
- Thread-safe operations via RLock
- Persistent index for cache recovery

**Test Coverage:**
```
tests/test_wtb/test_actor_lifecycle.py - 32 tests (100% passing)
tests/test_wtb/test_venv_cache.py - 20 tests (100% passing)
```

**Next Steps:**
1. Add Ray E2E integration tests with real cluster
2. Performance benchmarking for venv cache hit rates
3. Full E2E testing with real workflow execution

# WTB Documentation Index

**Last Updated:** 2026-01-17

## Quick Navigation

| Document | Purpose | Read When |
|----------|---------|-----------|
| [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) | **High-Level Project Overview** | Key features, core components, and value proposition | **Start here** for concepts |
| [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | Executive summary, data flows, user flows, **data characteristics** | Architecture overview |
| [WORKFLOW_TEST_BENCH_ARCHITECTURE.md](./WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Complete architecture, **Ray BatchTestRunner design**, detailed decisions | Deep technical understanding |
| [WTB_ARCHITECTURE_DIAGRAMS.md](./WTB_ARCHITECTURE_DIAGRAMS.md) | 🆕 **Visual diagrams** for execution, checkpointing, rollback, fork, file tracking, Ray batch | Understanding workflows visually |
| [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | Three-database schema, **indexing strategy**, Repository + UoW patterns | Database work |
| [PROGRESS_TRACKER.md](./PROGRESS_TRACKER.md) | Implementation status, **Ray migration plan** | Check what's done/pending |

## Detailed Design Documents

### LangGraph Integration (PRIMARY)

| Document | Purpose |
|----------|---------|
| [../LangGraph/INDEX.md](../LangGraph/INDEX.md) | 🆕 **LangGraph integration overview** |
| [../LangGraph/PERSISTENCE.md](../LangGraph/PERSISTENCE.md) | Checkpointers, threads, state snapshots |
| [../LangGraph/TIME_TRAVEL.md](../LangGraph/TIME_TRAVEL.md) | History, replay, fork, update state |
| [../LangGraph/API_DEPLOYMENT.md](../LangGraph/API_DEPLOYMENT.md) | Agent Server, LangSmith, REST APIs |
| [../LangGraph/WTB_INTEGRATION.md](../LangGraph/WTB_INTEGRATION.md) | LangGraphStateAdapter design |
| [../LangGraph/AUDIT_EVENT_SYSTEM.md](../LangGraph/AUDIT_EVENT_SYSTEM.md) | 🆕 **Streaming events, tracing, ACID** |
| [../LangGraph/CHECKPOINT_GRANULARITY_DESIGN.md](../LangGraph/CHECKPOINT_GRANULARITY_DESIGN.md) | 🆕 **Node vs Tool level decision** |
| [../LangGraph/DOMAIN_CHECKPOINT_DESIGN.md](../LangGraph/DOMAIN_CHECKPOINT_DESIGN.md) | ✅ **Checkpoint in Domain Layer (DDD)** - IMPLEMENTED |
| [../LangGraph/DDD_VIOLATION_REVIEW.md](../LangGraph/DDD_VIOLATION_REVIEW.md) | ✅ **DDD violations & fix plan** - RESOLVED |

### Environment Management (NEW 2026-01-15)

| Document | Purpose |
|----------|---------|
| [../venv_management/INDEX.md](../venv_management/INDEX.md) | 🆕 **UV Venv Manager integration overview** |
| [../venv_management/ARCHITECTURE_REVIEW.md](../venv_management/ARCHITECTURE_REVIEW.md) | SOLID/ACID analysis, refactoring requirements |
| [../venv_management/SYSTEM_OVERVIEW.md](../venv_management/SYSTEM_OVERVIEW.md) | High-level architecture, IEnvironmentProvider mapping |
| [../venv_management/VENV_LIFECYCLE_DESIGN.md](../venv_management/VENV_LIFECYCLE_DESIGN.md) | State machine, transactional operations |
| [../venv_management/INTEGRATION_POINTS.md](../venv_management/INTEGRATION_POINTS.md) | WTB integration, Ray/Local providers |
| [../venv_management/MIGRATION_PLAN.md](../venv_management/MIGRATION_PLAN.md) | Phased migration plan |

### External API & Observability (NEW 2026-01-15)

| Document | Purpose |
|----------|---------|
| [../external_api/INDEX.md](../external_api/INDEX.md) | 🆕 **External API & Observability overview** |
| [../external_api/EXTERNAL_API_AND_OBSERVABILITY_DESIGN.md](../external_api/EXTERNAL_API_AND_OBSERVABILITY_DESIGN.md) | REST + gRPC + WebSocket API design, OpenTelemetry/Prometheus/Grafana |

### Other Design Documents

| Document | Purpose |
|----------|---------|
| [../Adapter_and_WTB-Storage/AGENTGIT_STATE_ADAPTER_DESIGN.md](../Adapter_and_WTB-Storage/AGENTGIT_STATE_ADAPTER_DESIGN.md) | ⏸️ AgentGitStateAdapter (DEFERRED) |
| [../Adapter_and_WTB-Storage/WTB_PERSISTENCE_DESIGN.md](../Adapter_and_WTB-Storage/WTB_PERSISTENCE_DESIGN.md) | WTB storage (InMemory + SQLAlchemy UoW) |
| [../Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md](../Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md) | Outbox Pattern, IntegrityChecker, cross-DB consistency |
| [../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) | Event Bus & Audit Trail integration |
| [../thread_and_process/INDEX.md](../thread_and_process/INDEX.md) | **Thread/Ray parallel execution design index** |

## Meeting Reports

| Date | Report | Summary |
|------|--------|---------|
| 2025-12-27 | [Design_Summary_2025_12_27.md](../Metting_Report/2025_12_27/Design_Summary_2025_12_27.md) | Core architecture patterns, cross-system consistency |
| **2025-01-10** | [Implementation_Summary_2025_01_10.md](../Metting_Report/2025-1-10/Implementation_Summary_2025_01_10.md) | **Event Bus, Audit Trail, Batch Runners implemented** |

## Issue Tracking

| Document | Purpose |
|----------|---------|
| [../issues/INDEX.md](../issues/INDEX.md) | 🆕 **Issues & Gap Analysis Index** |

### Active Issues

| Date | Document | Priority | Status |
|------|----------|----------|--------|
| **2026-01-15** | [GAP_ANALYSIS_2026_01_15_STATE_ADAPTER_ID_MISMATCH.md](../issues/GAP_ANALYSIS_2026_01_15_STATE_ADAPTER_ID_MISMATCH.md) | **P0** | ⚠️ Open - IStateAdapter int→str migration required |

### Resolved Issues

| Date | Document | Status |
|------|----------|--------|
| 2026-01-14 | [RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md](../issues/RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md) | ✅ Resolved - RayBatchTestRunner fully implemented |
| 2026-01-14 | [WTB_Architecture_Audit_2026_01_14.md](../issues/WTB_Architecture_Audit_2026_01_14.md) | ⚠️ GAP-1 resolved, GAP-2/3/4 pending |

## Section Quick Reference

### Architecture Deep Dive (`WORKFLOW_TEST_BENCH_ARCHITECTURE.md`)

This document is the technical source of truth (4000+ lines). Use this map to navigate the key components:

| Section | Topic | Why Read It |
|---------|-------|-------------|
| **§0** | **Validated Infrastructure** | Understand the foundation (AgentGit v2, FileTracker) verified by tests. |
| **§3** | **Database Architecture** | Learn about the **Repository + Unit of Work** pattern and Dual-Database strategy. |
| **§4** | **Domain Models** | Definitions of core entities: `TestWorkflow`, `Execution`, `NodeVariant`. |
| **§5** | **Execution Controller** | Design of the core orchestration engine (Run/Pause/Resume/Rollback). |
| **§7** | **State Adapter** | How WTB integrates with AgentGit without tight coupling (**Anti-Corruption Layer**). |
| **§9** | **Project Structure** | Where files should go (Directory Layout). |
| **§13** | **Critical Decisions** | **Must Read**. DB choice, Checkpoint Granularity, Event Bus, Storage patterns. |
| **§15** | **Validation Status** | Checklist of implemented vs. pending components. |
| **§16** | **Parallel Sessions (ThreadPool)** | Original design for concurrent execution isolation. |
| **§17** | **Architecture Critique** | **NEW** Gap analysis, risks, implicit assumptions. |
| **§18** | **Ray BatchTestRunner** | **NEW** Ray-based batch testing, ActorPool, environment isolation. |
| **§19** | **Migration Path** | **NEW** ThreadPool → Ray migration strategy. |

### Other Key References

| Topic | Document | Section |
|-------|----------|---------|
| **Executive Summary** | [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | All |
| **User Flows** | [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | §4 |
| **Data Characteristics** | [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | **§7 (NEW)** |
| **Ray Batch Testing** | [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | **§8 (NEW)** |
| **Indexing Strategy** | [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | **Indexing Strategy (NEW)** |
| **Batch Test Schema** | [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | **Batch Test Storage Schema (NEW)** |
| **Event Bus & Audit** | [../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) | All |

## Environment Requirements

> **Python Version: 3.12** (pinned 2026-01-15)
> 
> Ray does not support Python 3.13 on Windows yet. Use Python 3.12 for full compatibility with Ray distributed computing.

## Key Design Principles

### DDD Principles (2026-01-15)

1. **Checkpoint is a Domain Concept**: `Checkpoint`, `CheckpointId`, `ExecutionHistory` belong in domain layer
2. **Domain owns business logic**: Rollback targets, node boundaries computed in `ExecutionHistory`, not adapters
3. **Infrastructure = persistence only**: `ICheckpointStore` saves/loads; no business logic
4. **Node-level granularity**: LangGraph checkpoints at super-step (node), not tool/message level

### Architecture Principles

1. **LangGraph-First Persistence**: Use LangGraph checkpointers (`PostgresSaver`, `SqliteSaver`) for robust checkpoint/rollback
2. **Single Checkpoint Type**: All checkpoints atomic at node level; node boundaries are POINTERS
3. **Interface Abstraction**: ICheckpointStore, IUnitOfWork, **IBatchTestRunner**, **IEnvironmentProvider** enable swappable implementations
4. **Anti-Corruption Layer**: Adapters bridge WTB ↔ LangGraph ↔ FileTracker boundaries
5. **Ray for Batch Testing**: Distributed parallelism, resource management, fault tolerance
6. **Data Lifecycle Aware**: Ephemeral data → Ray ObjectRef; Persistent data → PostgreSQL
7. **Environment Isolation via Interface**: IEnvironmentProvider with Ray/UV/gRPC implementations
8. **Thread-Based Isolation**: LangGraph `thread_id` for parallel batch test isolation
9. **Transactional Environment Management**: UV venv operations are atomic (create or rollback)

## Architecture Overview (Updated 2026-01)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              WTB ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  API Layer:       REST/gRPC endpoints                                           │
│       ↓                                                                          │
│  Application:     ExecutionController, NodeReplacer, RayBatchTestRunner         │
│       ↓                                                                          │
│  Domain:          IStateAdapter, IUnitOfWork, IBatchTestRunner, IEnvironmentProvider
│       ↓                                                                          │
│  Infrastructure:  LangGraphStateAdapter (PRIMARY), SQLAlchemyUoW, Ray ActorPool │
│       ↓                                                                          │
│  Data:            LangGraph Checkpointer (PostgresSaver) | WTB DB | Ray Object Store
│                                                                                  │
│  State Adapter Priority:                                                         │
│  ═══════════════════════                                                         │
│  1. LangGraphStateAdapter (production-ready, battle-tested)                     │
│  2. InMemoryStateAdapter  (unit testing)                                        │
│  3. AgentGitStateAdapter  (future/experimental - marked only)                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

Batch Test Execution Flow:
══════════════════════════

User → RayBatchTestRunner → [Ray Workers (ActorPool)]
                                    ↓
                            Each worker: LangGraph graph + thread_id isolation
                                    ↓
                            Checkpoints via PostgresSaver (per-thread)
                                    ↓
                            Build comparison matrix
```

## Critical Decisions Summary (2026-01)

| Decision | Choice | Rationale | Status |
|----------|--------|-----------|--------|
| **State Persistence** | **LangGraph Checkpointer** | Production-proven, built-in time travel, thread isolation | ✅ **NEW** |
| **Batch Execution** | Ray | Distributed parallelism, resource management, fault tolerance | ✅ Approved |
| **Data Storage** | PostgreSQL (production) | Concurrent writes, JSONB support, partitioning | ✅ Approved |
| **Ephemeral Data** | Ray Object Store | Zero-copy sharing, automatic cleanup | ✅ Approved |
| **Indexing** | B-Tree + BRIN + GIN | B-Tree for lookups, BRIN for time-series, GIN for JSONB | ✅ Approved |
| **Environment Mgmt** | Interface abstraction | RayEnvironmentProvider default; LocalUvEnvironmentProvider for venvs | ✅ Approved |
| **External API** | **REST + gRPC + WebSocket** | REST for simplicity, gRPC for performance, WebSocket for real-time | 🆕 **Approved (2026-01-15)** |
| **Observability** | **OpenTelemetry → Prometheus → Grafana** | Vendor-neutral, industry standard, existing Prometheus integration | 🆕 **Approved (2026-01-15)** |
| **UV Venv Manager** | Library integration | Integrate as WTB module, not microservice; refactor for SOLID/ACID | 🆕 **Design (2026-01-15)** |
| **IStateAdapter** | **Deprecate** | Replace with ICheckpointStore; int→str migration blocked | 🆕 **P0 Gap** |
| **Connection Pooling** | PgBouncer | Prevent DB connection storm with 100+ actors | ⚠️ Required |
| **AgentGit Adapter** | **Marked Only** | Deferred to future; LangGraph takes priority for robustness | ⏸️ Deferred |
| **Migration Validation** | ParityChecker | Dry-run comparison of ThreadPool vs Ray results | ✅ **Implemented (2026-01-15)** |

## LangGraph Adapter Decision (2026-01-15)

**Decision**: Replace AgentGit adapter with LangGraph adapter as primary implementation.

### Why LangGraph First?

| Aspect | LangGraph | AgentGit | Winner |
|--------|-----------|----------|--------|
| **Battle-tested** | Used in LangSmith production | Custom implementation | LangGraph |
| **Thread isolation** | Native `thread_id` support | Manual session management | LangGraph |
| **Time travel** | Built-in `get_state_history()` | Custom rollback logic | LangGraph |
| **Checkpointer backends** | SQLite, PostgreSQL, Memory | SQLite only | LangGraph |
| **Serialization** | `JsonPlusSerializer` + encryption | Custom | LangGraph |
| **Fault tolerance** | Pending writes preserved | Manual | LangGraph |

### LangGraph Key Concepts

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH PERSISTENCE MODEL                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Thread (thread_id)                                                              │
│  └── Checkpoints (StateSnapshot at each super-step)                             │
│       ├── config: {thread_id, checkpoint_id, checkpoint_ns}                     │
│       ├── metadata: {source, writes, step}                                      │
│       ├── values: State channel values                                          │
│       ├── next: Tuple of next node names                                        │
│       └── tasks: PregelTask objects                                             │
│                                                                                  │
│  APIs:                                                                           │
│  • graph.get_state(config) → Latest StateSnapshot                               │
│  • graph.get_state_history(config) → Full checkpoint history                    │
│  • graph.update_state(config, values, as_node) → Modify state                   │
│  • Invoke with checkpoint_id → Time travel / Replay                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Checkpointer Selection

| Environment | Checkpointer | Package |
|-------------|--------------|---------|
| Unit Tests | `InMemorySaver` | `langgraph-checkpoint` (bundled) |
| Development | `SqliteSaver` | `langgraph-checkpoint-sqlite` |
| Production | `PostgresSaver` | `langgraph-checkpoint-postgres` |

## Colleague Review Validation (2025-01-09)

| Section | Verdict | Key Feedback |
|---------|---------|--------------|
| §16 (ThreadPool) | ✅ Retain | Dev/local model for testing without Ray cluster |
| §17 (Critique) | ✅ Validated | P0 risks correctly identified |
| §18 (Ray Design) | ✅ Strong/Approved | Actor pattern, runtime_env, data strategy all correct |
| §19 (Migration) | ✅ Approved | Added ParityChecker dry-run capability |
| **§20 (LangGraph)** | ✅ **NEW** | LangGraph adapter prioritized for robustness |

### Critical Risks Identified

| Risk | Mitigation | Owner |
|------|------------|-------|
| **DB Connection Storm** | PgBouncer required in front of PostgreSQL | Infra |
| **Observability Gap** | Export to Prometheus/Grafana (not just Ray Dashboard) | Backend |
| **gRPC Integration** | `GrpcEnvironmentProvider` for colleague's env-manager | Backend |
| **AgentGit Deferred** | Keep interface; implement later if needed | Backend |
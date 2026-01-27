# Thread & Process - Parallel Execution Design

**Last Updated:** 2026-01-15

## Overview

This directory indexes WTB's parallel and distributed execution design, covering ThreadPool-based local execution and Ray-based distributed batch testing.

---

## Design Documents Index

### Primary Source: WORKFLOW_TEST_BENCH_ARCHITECTURE.md

| Section | Title | Scope |
|---------|-------|-------|
| **§16** | [Parallel Internal Session Design](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | ThreadPool-based local execution |
| **§17** | [Architecture Review & Critique](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Gap analysis, risks |
| **§18** | [Ray-Based Batch Test Runner Design](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Distributed execution with Ray |
| **§19** | [Migration Path: ThreadPool → Ray](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Phased migration strategy |

### Summary Document: WORKFLOW_TEST_BENCH_SUMMARY.md

| Section | Title | Scope |
|---------|-------|-------|
| **§5.5** | [Parallel Session Design](../Project_Init/WORKFLOW_TEST_BENCH_SUMMARY.md) | High-level parallel context overview |
| **§7** | [Data Characteristics](../Project_Init/WORKFLOW_TEST_BENCH_SUMMARY.md) | Storage strategy for batch testing |
| **§8** | [Ray-Based Batch Test Execution](../Project_Init/WORKFLOW_TEST_BENCH_SUMMARY.md) | Ray execution flow summary |

---

## Quick Reference

### §16: ThreadPool Design (Development/Local)

**Purpose:** Local parallel execution for development and testing without Ray cluster.

**Core Pattern:** ParallelExecutionContext

```
BatchTestRunner
    └── ThreadPoolExecutor
            ├── Context A: Adapter A + Controller A + UoW A
            ├── Context B: Adapter B + Controller B + UoW B
            └── Context N: Adapter N + Controller N + UoW N
                    ↓
            AgentGit Database (WAL Mode)
```

**Key Decisions:**

| Aspect | Decision |
|--------|----------|
| Isolation | Each thread gets independent StateAdapter, Controller, UoW |
| Thread Safety | ThreadPoolExecutor + fully isolated contexts |
| SQLite Concurrency | WAL mode + busy_timeout (30s) |
| Cleanup | SessionLifecycleManager with timeout |

**Components:**
- `ParallelExecutionContext` - Isolated execution context
- `ParallelContextFactory` - Context factory
- `SessionLifecycleManager` - Abandoned session cleanup

---

### §17: Architecture Critique

**P0 Risks Addressed by Ray:**
- Scaling limitations (GIL-bound)
- No resource management per execution
- Basic failure handling (no retry)

**P1 Risks:**
- Observability gap → Prometheus/Grafana export required
- State consistency → Outbox pattern implemented
- Environment isolation → IEnvironmentProvider interface

---

### §18: Ray Design (Production)

**Purpose:** Distributed batch testing with resource management and fault tolerance.

**Core Pattern:** Ray ActorPool

```
RayBatchTestRunner (Orchestrator)
    └── ray.put(workflow, initial_state) → ObjectRefs
            ↓
    ActorPool (VariantExecutionActor)
        ├── Worker 1: @ray.remote(num_cpus=1, memory=2GB)
        ├── Worker 2: @ray.remote(num_cpus=1, memory=2GB)
        └── Worker N: @ray.remote(num_cpus=1, memory=2GB)
            ↓
        PostgreSQL (via PgBouncer)
```

**Key Decisions:**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Actor vs Task | Actor | DB connection reuse |
| State Sharing | ObjectRef | Zero-copy, immutable |
| Backpressure | max_pending_tasks | Prevent memory exhaustion |
| Failure | max_retries + dead-letter | Automatic retry |
| Environment | IEnvironmentProvider | Runtime isolation |

**Components:**
- `RayBatchTestRunner` - Orchestrator
- `VariantExecutionActor` - Ray Actor for variant execution
- `RayConfig` - Cluster configuration
- `IEnvironmentProvider` / `RayEnvironmentProvider` - Environment isolation

---

### §19: Migration Path

**Strategy:** Phased migration with ParityChecker validation.

| Phase | Description | Status |
|-------|-------------|--------|
| M1 | IBatchTestRunner interface | ✅ Done |
| M2 | RayBatchTestRunner implementation | ⚠️ Stub |
| M2.5 | ParityChecker dry-run | ❌ TODO |
| M3 | Ray integration tests | ❌ TODO |
| M4 | Production rollout | ❌ TODO |
| M5 | Deprecate ThreadPool | Planned |

---

## Implementation Status

| Component | Design | Implementation | Notes |
|-----------|--------|----------------|-------|
| IBatchTestRunner | §18.9, §19.1 | ✅ Done | |
| ThreadPoolBatchTestRunner | §16.4 | ✅ Done | |
| RayBatchTestRunner | §18.4 | ✅ **Done** | Full implementation 2026-01-14 |
| VariantExecutionActor | §18.4 | ✅ **Done** | ExecutionController integration |
| RayConfig | §18.7 | ✅ Done | |
| IEnvironmentProvider | §18.5 | ✅ Done | |
| RayEnvironmentProvider | §18.5 | ✅ Done | |
| GrpcEnvironmentProvider | §18.5 | ⚠️ Stub | Pending colleague integration |
| ParallelContextFactory | §16.4 | ❌ Superseded | Replaced by factory lambdas |
| SessionLifecycleManager | §16.6 | ❌ Not started | |
| ParityChecker | §19.2 | ❌ Not started | |

---

## Review Document

See: [ARCHITECTURE_REVIEW.md](./ARCHITECTURE_REVIEW.md) - Concise implementation review (2025-01-09)

---

## State Adapter Note (2026-01-15)

> **LangGraph is now the PRIMARY state adapter** for WTB.
> 
> - Ray actors use `LangGraphStateAdapter` with PostgresSaver
> - Thread isolation via LangGraph `thread_id`
> - See [../LangGraph/INDEX.md](../LangGraph/INDEX.md) for details

## Related Documents

| Document | Topic |
|----------|-------|
| [../LangGraph/INDEX.md](../LangGraph/INDEX.md) | 🆕 **LangGraph integration (PRIMARY)** |
| [../Ray/RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md](../Ray/RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md) | Ray implementation details |
| [../EventBus_and_Audit_Session/INDEX.md](../EventBus_and_Audit_Session/INDEX.md) | Event Bus & Audit Trail |
| [../Project_Init/DATABASE_DESIGN.md](../Project_Init/DATABASE_DESIGN.md) | Batch test schema, indexing |
| [../Project_Init/PROGRESS_TRACKER.md](../Project_Init/PROGRESS_TRACKER.md) | Implementation status |

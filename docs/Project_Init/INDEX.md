# WTB Documentation Index

**Last Updated:** 2025-01-09

## Quick Navigation

| Document | Purpose | Read When |
|----------|---------|-----------|
| [WORKFLOW_TEST_BENCH_SUMMARY.md](./WORKFLOW_TEST_BENCH_SUMMARY.md) | Executive summary, data flows, user flows, **data characteristics** | Start here for overview |
| [WORKFLOW_TEST_BENCH_ARCHITECTURE.md](./WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Complete architecture, **Ray BatchTestRunner design**, detailed decisions | Deep technical understanding |
| [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | Three-database schema, **indexing strategy**, Repository + UoW patterns | Database work |
| [PROGRESS_TRACKER.md](./PROGRESS_TRACKER.md) | Implementation status, **Ray migration plan** | Check what's done/pending |

## Detailed Design Documents

| Document | Purpose |
|----------|---------|
| [../Adapter_and_WTB-Storage/AGENTGIT_STATE_ADAPTER_DESIGN.md](../Adapter_and_WTB-Storage/AGENTGIT_STATE_ADAPTER_DESIGN.md) | AgentGitStateAdapter implementation, checkpoint design |
| [../Adapter_and_WTB-Storage/WTB_PERSISTENCE_DESIGN.md](../Adapter_and_WTB-Storage/WTB_PERSISTENCE_DESIGN.md) | WTB storage (InMemory + SQLAlchemy UoW) |
| [../Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md](../Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md) | Outbox Pattern, IntegrityChecker, cross-DB consistency |
| [../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) | Event Bus & Audit Trail integration with AgentGit |

## Meeting Reports

| Date | Report | Summary |
|------|--------|---------|
| 2025-12-27 | [Design_Summary_2025_12_27.md](../Metting_Report/2025_12_27/Design_Summary_2025_12_27.md) | Core architecture patterns, cross-system consistency |
| **2025-01-10** | [Implementation_Summary_2025_01_10.md](../Metting_Report/2025-1-10/Implementation_Summary_2025_01_10.md) | **Event Bus, Audit Trail, Batch Runners implemented** |

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

## Key Design Principles

1. **Dual Database Pattern**: AgentGit repos for checkpoints; SQLAlchemy UoW for WTB domain data
2. **Single Checkpoint Type**: All checkpoints atomic; node boundaries are POINTERS not separate checkpoints
3. **Interface Abstraction**: IStateAdapter, IUnitOfWork, **IBatchTestRunner** enable swappable implementations
4. **Anti-Corruption Layer**: Adapters bridge WTB ↔ AgentGit ↔ FileTracker boundaries
5. **Ray for Batch Testing**: Distributed parallelism, resource management, fault tolerance
6. **Data Lifecycle Aware**: Ephemeral data → Ray ObjectRef; Persistent data → PostgreSQL
7. **Environment Isolation via Interface**: IEnvironmentProvider with Ray/gRPC implementations

## Architecture Overview (Updated 2025-01)

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
│  Infrastructure:  AgentGitStateAdapter, SQLAlchemyUoW, Ray ActorPool            │
│       ↓                                                                          │
│  Data:            AgentGit DB | WTB DB (PostgreSQL) | FileTracker | Ray Object Store
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

Batch Test Execution Flow:
══════════════════════════

User → RayBatchTestRunner → [Ray Workers (ActorPool)]
                                    ↓
                            Execute variants in parallel
                                    ↓
                            Persist results to PostgreSQL
                                    ↓
                            Build comparison matrix
```

## Critical Decisions Summary (2025-01)

| Decision | Choice | Rationale | Status |
|----------|--------|-----------|--------|
| **Batch Execution** | Ray | Distributed parallelism, resource management, fault tolerance | ✅ Approved |
| **Data Storage** | PostgreSQL (production) | Concurrent writes, JSONB support, partitioning | ✅ Approved |
| **Ephemeral Data** | Ray Object Store | Zero-copy sharing, automatic cleanup | ✅ Approved |
| **Indexing** | B-Tree + BRIN + GIN | B-Tree for lookups, BRIN for time-series, GIN for JSONB | ✅ Approved |
| **Environment Mgmt** | Interface abstraction | RayEnvironmentProvider default; gRPC adapter for colleague's service | ✅ Approved |
| **Connection Pooling** | PgBouncer | Prevent DB connection storm with 100+ actors | ⚠️ Required |
| **Migration Path** | Phased + ParityChecker | Dry-run validation before full switchover | ✅ Approved |

## Colleague Review Validation (2025-01-09)

| Section | Verdict | Key Feedback |
|---------|---------|--------------|
| §16 (ThreadPool) | ✅ Retain | Dev/local model for testing without Ray cluster |
| §17 (Critique) | ✅ Validated | P0 risks correctly identified |
| §18 (Ray Design) | ✅ Strong/Approved | Actor pattern, runtime_env, data strategy all correct |
| §19 (Migration) | ✅ Approved | Added ParityChecker dry-run capability |

### Critical Risks Identified

| Risk | Mitigation | Owner |
|------|------------|-------|
| **DB Connection Storm** | PgBouncer required in front of PostgreSQL | Infra |
| **Observability Gap** | Export to Prometheus/Grafana (not just Ray Dashboard) | Backend |
| **gRPC Integration** | `GrpcEnvironmentProvider` for colleague's env-manager | Backend |

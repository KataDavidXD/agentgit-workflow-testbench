# WTB Project Progress Tracker

**Last Updated:** 2026-01-16 (SDK Refactor: SOLID + ACID Compliance)

## Project Structure

```
wtb/
├── api/
│   ├── __init__.py             [DONE] API layer entry point
│   ├── rest/
│   │   ├── __init__.py
│   │   ├── app.py              [DONE] FastAPI application factory
│   │   ├── models.py           [DONE] Pydantic request/response schemas
│   │   ├── dependencies.py     [DONE] FastAPI dependency injection
│   │   └── routes/
│   │       ├── workflows.py    [DONE] Workflow CRUD + batch test
│   │       ├── executions.py   [DONE] Execution control
│   │       ├── audit.py        [DONE] Audit trail access
│   │       ├── batch_tests.py  [DONE] Batch test management
│   │       └── health.py       [DONE] Health checks
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── handlers.py         [DONE] ConnectionManager + event bridge
│   └── grpc/
│       ├── __init__.py
│       └── protos/
│           └── wtb_service.proto [DONE] gRPC service definition
├── sdk/
│   ├── __init__.py
│   ├── workflow_project.py     [DONE] WorkflowProject configuration
│   └── test_bench.py           [DONE] WTBTestBench main interface
├── domain/
│   ├── models/          [DONE] workflow, execution, node_boundary, checkpoint_file, batch_test, evaluation
│   │                    [DONE] outbox (OutboxEvent), integrity (IntegrityIssue, IntegrityReport)
│   │                    [DONE] Rich Domain Model for Execution entity
│   │                    [DONE] checkpoint.py - Checkpoint, CheckpointId, ExecutionHistory ← DDD (2026-01-15) ✓
│   │                    [DONE] workspace.py - Workspace, WorkspaceConfig, OrphanWorkspace ← NEW (2026-01-16)
│   ├── interfaces/      [DONE] repositories, unit_of_work, state_adapter, execution_controller, node_replacer
│   │                    [DONE] IOutboxRepository, IAuditLogRepository
│   │                    [DONE] IEnvironmentProvider, IBatchTestRunner ← NEW (2025-01-09)
│   │                    [DONE] checkpoint_store.py - ICheckpointStore (persistence only) ← DDD (2026-01-15) ✓
│   ├── events/          [DONE] execution_events, node_events, checkpoint_events
│   │                    [DONE] Updated checkpoint_events.py - uses CheckpointId ← DDD (2026-01-15) ✓
│   │                    [DONE] file_processing_events.py - FileCommitCreated, FileRestored, etc. ← NEW (2026-01-15)
│   │                    [DONE] ray_events.py - 18 Ray batch test events (ACID compliant) ← NEW (2026-01-15)
│   │                    [DONE] workspace_events.py - 15+ workspace lifecycle/file/fork events ← NEW (2026-01-16)
│   └── audit/           [DONE] WTBAuditTrail, WTBAuditEntry (moved to infrastructure/events)
├── application/
│   ├── services/        [DONE] execution_controller, node_replacer
│   │                    [DONE] ThreadPoolBatchTestRunner, RayBatchTestRunner (stub) ← NEW (2025-01-09)
│   │                    [DONE] actor_lifecycle.py - ActorLifecycleManager ← NEW (2026-01-16)
│   │                    [DESIGN] ParallelContextFactory
│   └── factories.py     [DONE] ExecutionControllerFactory, NodeReplacerFactory, BatchTestRunnerFactory ← NEW
├── infrastructure/
│   ├── database/        [DONE] config, setup, models (ORM), repositories, unit_of_work, inmemory_unit_of_work, factory
│   │                    [DONE] OutboxORM model, SQLAlchemyOutboxRepository, InMemoryOutboxRepository
│   │                    [DONE] AuditLogORM, SQLAlchemyAuditLogRepository, InMemoryAuditLogRepository
│   │                    [DONE] migrations/ with 002_batch_tests.sql, 003_postgresql_production.sql ← NEW
│   │                    [DONE] file_processing_orm.py - FileBlobORM, FileCommitORM, FileMementoORM ← NEW (2026-01-15)
│   ├── adapters/        [DONE] InMemoryStateAdapter, AgentGitStateAdapter
│   │                    [TODO] session_manager (lifecycle cleanup)
│   ├── workspace/       [DONE] WorkspaceManager, create_file_link, orphan cleanup ← NEW (2026-01-16)
│   ├── environment/     [DONE] InProcessEnvironmentProvider, RayEnvironmentProvider ← NEW (2025-01-09)
│   │                    [DONE] venv_cache.py - VenvCacheManager with LRU eviction ← NEW (2026-01-16)
│   ├── outbox/          [DONE] OutboxProcessor (background worker)
│   ├── integrity/       [DONE] IntegrityChecker (cross-DB consistency)
│   └── events/          [DONE] WTBEventBus, WTBAuditTrail, AuditEventListener ← NEW (2025-01-09)
│                        [DONE] RayEventBridge - Ray events with outbox pattern ← NEW (2026-01-15)
├── config.py            [DONE] WTBConfig with storage modes
│                        [DONE] RayConfig for batch testing ← NEW (2025-01-09)
├── tests/
│   └── test_wtb/        [DONE] 590+ tests passing (+104 tests on 2026-01-16)
│                        [DONE] test_outbox.py, test_integrity.py, test_cross_db_consistency.py
│                        [DONE] test_event_bus.py, test_audit_trail.py, test_batch_runner.py, test_audit_repository.py ← NEW
│                        [DONE] test_file_processing_domain.py, test_file_processing_repository.py, test_file_processing_integration.py ← NEW (2026-01-15)
│                        [DONE] test_ray_event_integration.py, test_ray_transaction_consistency.py ← NEW (2026-01-15)
│                        [DONE] test_workspace_manager.py, test_workspace_integration.py, test_ray_workspace_integration.py ← NEW (2026-01-16)
│                        [DONE] test_actor_lifecycle.py, test_venv_cache.py ← NEW (2026-01-16)
│                        [TODO] test_parallel_sessions.py
│   └── test_file_processing/  [NEW] 183 tests for file processing module (2026-01-15)
│                        [DONE] unit/test_basic_operations.py - 31 tests
│                        [DONE] unit/test_execution_control.py - 30 tests
│                        [DONE] integration/test_file_event.py - 30 tests
│                        [DONE] integration/test_file_audit.py - 25 tests
│                        [DONE] integration/test_file_event_audit.py - 28 tests
│                        [DONE] integration/test_file_ray.py - 19 tests
│                        [DONE] integration/test_file_venv.py - 20 tests
└── examples/
    └── ml_pipeline_workflow.py  [DONE] 10-step ML pipeline with LangChain LLM + rollback
```

## Completed ✓

| Component                            | Status          | Notes                                                                    |
| ------------------------------------ | --------------- | ------------------------------------------------------------------------ |
| Domain Models                        | ✓              | Workflow, Execution, NodeBoundary, CheckpointFile, BatchTest, Evaluation |
| Domain Interfaces                    | ✓              | IRepository, IStateAdapter, IExecutionController, INodeReplacer          |
| Domain Events                        | ✓              | Execution, Node, Checkpoint events                                       |
| SQLAlchemy ORM                       | ✓              | All 7 WTB tables defined + OutboxORM + AuditLogORM                       |
| Repositories                         | ✓              | All repository implementations                                           |
| SQLAlchemyUnitOfWork                 | ✓              | Production UoW with SQLAlchemy                                           |
| **InMemoryUnitOfWork**         | ✓**NEW** | For testing - no I/O, fast, isolated                                     |
| **UnitOfWorkFactory**          | ✓**NEW** | Factory pattern for UoW creation                                         |
| Database Config                      | ✓              | Local data/ folder, redirect AgentGit                                    |
| InMemoryStateAdapter                 | ✓              | For testing/development                                                  |
| **AgentGitStateAdapter**       | ⏸️**DEFERRED** | Marked only - LangGraph adapter takes priority                         |
| **LangGraphCheckpointStore**   | ✓**NEW** | PRIMARY adapter using LangGraph checkpointers (2026-01-15)              |
| ExecutionController                  | ✓              | run, pause, resume, stop, rollback                                       |
| NodeReplacer                         | ✓              | variant registry, hot-swap                                               |
| **ExecutionControllerFactory** | ✓**NEW** | DI factory for controller creation                                       |
| **NodeReplacerFactory**        | ✓**NEW** | DI factory for replacer creation                                         |
| **WTBConfig**                  | ✓**NEW** | Centralized config with storage modes                                    |
| **Outbox Pattern**             | ✓**NEW** | Cross-DB consistency (P0 fix)                                            |
| **IntegrityChecker**           | ✓**NEW** | Data integrity validation (P0 fix)                                       |
| **Rich Domain Model**          | ✓**NEW** | Enhanced Execution entity (P1 fix)                                       |
| **WTBEventBus**                | ✓**NEW** | Thread-safe event bus with bounded history (2025-01-09)                 |
| **WTBAuditTrail**              | ✓**NEW** | Execution/Node-level audit tracking (2025-01-09)                        |
| **IAuditLogRepository**        | ✓**NEW** | Persistence for audit logs (2025-01-09)                                 |
| **IBatchTestRunner**           | ✓**NEW** | Interface for batch test execution (2025-01-09)                         |
| **ThreadPoolBatchTestRunner**  | ✓**NEW** | Local multithreaded batch runner (2025-01-09)                           |
| **RayBatchTestRunner**         | ✓**STUB** | Ray-based distributed batch runner (2025-01-09)                         |
| **VariantExecutionActor**      | ✓**STUB** | Ray Actor for variant execution (2025-01-09)                            |
| **BatchTestRunnerFactory**     | ✓**NEW** | Factory for ThreadPool/Ray selection (2025-01-09)                       |
| **RayConfig**                  | ✓**NEW** | Ray cluster configuration (2025-01-09)                                  |
| **IEnvironmentProvider**       | ✓**NEW** | Environment isolation interface (2025-01-09)                            |
| **RayEnvironmentProvider**     | ✓**NEW** | Ray runtime_env provider (2025-01-09)                                   |
| **Database Migrations**        | ✓**NEW** | Batch test tables + PostgreSQL indexes (2025-01-09)                     |
| **Checkpoint (Domain)**        | ✓**NEW** | DDD: Checkpoint, CheckpointId, ExecutionHistory (2026-01-15)            |
| **ICheckpointStore**           | ✓**NEW** | DDD: Persistence-only interface (2026-01-15)                            |
| **InMemoryCheckpointStore**    | ✓**NEW** | DDD: Testing implementation (2026-01-15)                                |
| **LangGraphCheckpointStore**   | ✓**NEW** | DDD: LangGraph adapter (2026-01-15)                                     |
| **LangGraph Audit Docs**       | ✓**NEW** | AUDIT_EVENT_SYSTEM.md - streaming, tracing, custom events (2026-01-15) |
| **LangGraphEventBridge**       | ✓**NEW** | Bridge LangGraph events to WTB EventBus (2026-01-15)                  |
| **ActorLifecycleManager**      | ✓**NEW** | Hot/Warm/Cold pause strategies for Ray actors (2026-01-16)           |
| **VenvCacheManager**           | ✓**NEW** | LRU-evicting venv cache for performance (2026-01-16)                 |
| Unit Tests                           | ✓              | 713+ tests passing (530 wtb + 183 file_processing full-scale suite)     |
| ML Pipeline Example                  | ✓              | LangChain + real rollback demo                                           |
| **REST API (FastAPI)**         | ✓**NEW** | External control: workflows, executions, audit, batch tests (2026-01-15) |
| **WebSocket Handler**          | ✓**NEW** | Real-time event streaming (2026-01-15)                                  |
| **gRPC Proto Definition**      | ✓**NEW** | Internal services, streaming, Ray workers (2026-01-15)                  |
| **SDK (WorkflowProject)**      | ✓**NEW** | Type-safe workflow submission (2026-01-15)                              |
| **SDK (WTBTestBench)**         | ✓**NEW** | Main interface for testing (2026-01-15)                                 |
| **API Unit Tests**             | ✓**NEW** | REST models and SDK tests (2026-01-15)                                  |
| **API Integration Tests**      | ✓**NEW** | REST endpoint integration tests (2026-01-15)                            |
| **External Control Unit Tests** | ✓**NEW** | ExecutionService, AuditService tests (2026-01-15)                      |
| **External Control Integration** | ✓**NEW** | Execution control endpoint tests (2026-01-15)                         |
| **Workflow Submission Tests**  | ✓**NEW** | SDK + WorkflowProject integration tests (2026-01-15)                   |
| **RAG Pipeline Example**       | ✓**NEW** | Complex example with variants, resources (2026-01-15)                  |
| **Workspace Model**            | ✓**NEW** | Workspace, WorkspaceConfig, WorkspaceStrategy (2026-01-16)             |
| **WorkspaceManager**           | ✓**NEW** | Create, activate, cleanup isolated workspaces (2026-01-16)             |
| **Workspace Events**           | ✓**NEW** | 15+ domain events for workspace lifecycle (2026-01-16)                 |
| **Ray-Workspace Integration**  | ✓**NEW** | Workspace isolation in RayBatchTestRunner (2026-01-16)                 |
| **Orphan Workspace Cleanup**   | ✓**NEW** | Lock file + PID detection for crashed processes (2026-01-16)           |
| **Hard Link with Fallback**    | ✓**NEW** | Cross-partition copy fallback for Windows (2026-01-16)                 |

## FileTracker Verification in OutboxProcessor (2026-01-15) ✓ COMPLETE

### Summary
Enhanced OutboxProcessor with comprehensive FileTracker verification handlers for cross-database consistency between WTB, AgentGit, and FileTracker. Implements ACID-compliant verification with detailed statistics and history tracking.

### New Outbox Event Types

| Event Type | Description |
|------------|-------------|
| `FILE_BATCH_VERIFY` | Batch verification for multiple commits in batch tests |
| `FILE_INTEGRITY_CHECK` | Deep integrity verification with hash checking |
| `FILE_RESTORE_VERIFY` | Verify files were correctly restored from commit |
| `ROLLBACK_FILE_RESTORE` | Coordinate file restoration during rollback |
| `ROLLBACK_VERIFY` | Full rollback verification (state + files) |

### Files Modified

- `wtb/domain/models/outbox.py` - Added 5 new OutboxEventType values + factory methods
- `wtb/infrastructure/outbox/processor.py` - Added 6 new handlers + IFileTrackingService protocol
- `tests/test_wtb/test_outbox_filetracker.py` - 27 unit tests

### Key Features

| Feature | Description |
|---------|-------------|
| **IFileTrackingService Protocol** | DIP-compliant protocol for FileTracker integration |
| **VerificationResult** | Dataclass for tracking verification outcomes |
| **FileVerificationResult** | Extended result with file-specific metrics |
| **Verification History** | Bounded history of verification results |
| **Extended Statistics** | Success rates, file counts, blob counts |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | Each handler has single responsibility (one event type) |
| **OCP** | New handlers via handler dict, no modification needed |
| **LSP** | Mock implementations substitutable for real repos |
| **ISP** | Focused protocols (ICommitRepository, IBlobRepository, IFileTrackingService) |
| **DIP** | Depends on protocols, not concrete implementations |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | Each event processed in single transaction |
| **Consistent** | Verification ensures cross-DB consistency |
| **Isolated** | Events processed independently |
| **Durable** | Status persisted before verification |

### Usage

```python
from wtb.infrastructure.outbox.processor import OutboxProcessor
from wtb.domain.models.outbox import OutboxEvent

# Create processor with FileTracker integration
processor = OutboxProcessor(
    wtb_db_url="sqlite:///data/wtb.db",
    checkpoint_repo=agentgit_repo,
    file_tracking_service=file_service,  # NEW
    strict_verification=True,
)

# Create batch verification event
event = OutboxEvent.create_file_batch_verify(
    execution_id="exec-123",
    commit_ids=["commit-1", "commit-2"],
    expected_total_files=10,
    verify_blobs=True,
)

# Get verification history
history = processor.get_verification_history(limit=20, failed_only=True)
```

---

## External API Layer Implementation (2026-01-15) ✓ COMPLETE

### Summary
Implemented complete external API layer for WTB following the approved design in `EXTERNAL_API_AND_OBSERVABILITY_DESIGN.md` and `WORKFLOW_SUBMISSION_DESIGN.md`. Includes REST API (FastAPI), WebSocket for real-time updates, gRPC service definition, and SDK for workflow submission.

### Files Created

**REST API:**
- `wtb/api/__init__.py` - API layer entry point
- `wtb/api/rest/__init__.py` - REST subpackage init
- `wtb/api/rest/app.py` - FastAPI application with CORS, middleware
- `wtb/api/rest/models.py` - 30+ Pydantic schemas for requests/responses
- `wtb/api/rest/dependencies.py` - Dependency injection functions
- `wtb/api/rest/routes/__init__.py` - Routes subpackage init
- `wtb/api/rest/routes/workflows.py` - Workflow CRUD + node management
- `wtb/api/rest/routes/executions.py` - Execution control (pause/resume/stop/rollback)
- `wtb/api/rest/routes/audit.py` - Audit event queries
- `wtb/api/rest/routes/batch_tests.py` - Batch test management
- `wtb/api/rest/routes/health.py` - Health/readiness endpoints

**WebSocket:**
- `wtb/api/websocket/__init__.py` - WebSocket subpackage init
- `wtb/api/websocket/handlers.py` - ConnectionManager + event streaming

**gRPC:**
- `wtb/api/grpc/__init__.py` - gRPC subpackage init
- `wtb/api/grpc/protos/wtb_service.proto` - Service definition with streaming RPCs

**SDK:**
- `wtb/sdk/__init__.py` - SDK package init
- `wtb/sdk/workflow_project.py` - WorkflowProject configuration
- `wtb/sdk/test_bench.py` - WTBTestBench main interface

**Tests:**
- `tests/test_api/__init__.py` - Test package init
- `tests/test_api/test_rest_models.py` - Unit tests for Pydantic models
- `tests/test_api/test_sdk.py` - Unit tests for SDK classes
- `tests/test_api/test_rest_integration.py` - Integration tests for REST endpoints

### REST API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/api/v1/workflows` | GET, POST | List/create workflows |
| `/api/v1/workflows/{id}` | GET, PUT, PATCH, DELETE | Workflow CRUD |
| `/api/v1/workflows/{id}/nodes` | GET, POST | Node management |
| `/api/v1/workflows/{id}/nodes/{node_id}/variants` | GET, POST | Variant management |
| `/api/v1/workflows/{id}/execute` | POST | Start execution |
| `/api/v1/workflows/{id}/batch-test` | POST | Run batch test |
| `/api/v1/executions` | GET | List executions |
| `/api/v1/executions/{id}` | GET | Get execution details |
| `/api/v1/executions/{id}/pause` | POST | Pause execution |
| `/api/v1/executions/{id}/resume` | POST | Resume execution |
| `/api/v1/executions/{id}/stop` | POST | Stop execution |
| `/api/v1/executions/{id}/rollback` | POST | Rollback to checkpoint |
| `/api/v1/executions/{id}/audit` | GET | Get audit trail |
| `/api/v1/audit/events` | GET | Query audit events |
| `/api/v1/batch-tests` | GET, POST | Batch test management |
| `/api/v1/batch-tests/{id}` | GET | Get batch test status |
| `/api/v1/batch-tests/{id}/results` | GET | Get batch test results |
| `/api/v1/batch-tests/{id}/stop` | POST | Stop batch test |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | Each route file handles one resource type |
| **OCP** | New endpoints via router.include_router() |
| **LSP** | Service interfaces allow mock implementations |
| **ISP** | Separate dependencies for each service |
| **DIP** | Routes depend on service abstractions via FastAPI Depends() |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomicity** | Services use UnitOfWork pattern |
| **Consistency** | Pydantic models validate all requests/responses |
| **Isolation** | Dependency injection provides isolated service instances |
| **Durability** | Services persist via configured database |

### SDK Usage Example

```python
from wtb.sdk import WorkflowProject, WTBTestBench

# Create project with full configuration
project = WorkflowProject(
    name="rag_pipeline",
    graph_factory=create_rag_graph,
    file_tracking=FileTrackingConfig(enabled=True),
    environment=EnvironmentConfig(granularity="node"),
    execution=ExecutionConfig(batch_executor="ray"),
)

# Register variants
project.register_variant("retriever", "bm25", bm25_retriever)
project.register_variant("retriever", "faiss", faiss_retriever)

# Run tests via SDK
wtb = WTBTestBench()
wtb.register_project(project)
result = wtb.run(project="rag_pipeline", initial_state={"query": "test"})

# Get execution history
history = wtb.get_execution_history("rag_pipeline", limit=10)
```

---

## External Control Tests & RAG Pipeline Example (2026-01-15) ✓ COMPLETE

### Summary
Created comprehensive unit and integration tests for External Control API endpoints, Workflow Submission SDK, and a complex RAG pipeline example demonstrating all workflow submission features.

### Files Created

**Tests:**
- `tests/test_api/test_external_control.py` - Unit tests for ExecutionService, AuditService
- `tests/test_api/test_external_control_integration.py` - Integration tests for execution control endpoints
- `tests/test_api/test_workflow_submission_integration.py` - Integration tests for SDK and WorkflowProject

**Examples:**
- `examples/rag_pipeline_workflow.py` - Complex RAG pipeline with variants, resources, environments

### Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_external_control.py` | 15+ | ExecutionService, AuditService unit tests |
| `test_external_control_integration.py` | 10+ | REST endpoints with mocked services |
| `test_workflow_submission_integration.py` | 10+ | SDK workflow execution and batch testing |

### RAG Pipeline Example Features

| Feature | Description |
|---------|-------------|
| **Complex Multi-Node Workflow** | Query expansion → Retrieval → Reranking → Generation |
| **Node Version Control** | Register and swap node implementations at runtime |
| **Node-Level Variants** | `bm25_retriever`, `gpt4_generator` for A/B testing |
| **Workflow-Level Variants** | `simple_rag_architecture` for architecture comparison |
| **Node-Level Environments** | Different dependencies per node |
| **Node-Level Resources** | Different CPU/GPU/memory allocation per node |
| **Batch Testing with Variant Matrix** | Parallel comparison of 4+ configurations |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | Each test file tests one component (ExecutionService, AuditService, etc.) |
| **OCP** | Mock implementations allow extending tests without modifying services |
| **LSP** | Mock services are interchangeable with real implementations |
| **ISP** | Separate fixtures for execution, audit, and batch test services |
| **DIP** | Tests depend on interfaces via mock AppState injection |

### ACID Compliance (Tested)

| Property | Test Coverage |
|----------|---------------|
| **Atomicity** | Pause/resume/rollback operations test atomic state transitions |
| **Consistency** | State modification tests validate consistent state updates |
| **Isolation** | Mock AppState provides isolated service instances per test |
| **Durability** | Integration tests verify persistence via repository mocks |

### Usage Example

```python
# External Control - Pause/Resume
from wtb.api.rest.dependencies import ExecutionService
service = ExecutionService(controller, event_bus, audit_trail)
await service.pause(execution_id, reason="user request")
await service.resume(execution_id, modified_state={"step": 1})

# Workflow Submission - Batch Test
from wtb.sdk import WTBTestBench
wtb = WTBTestBench()
wtb.register_project(project)
batch_result = await wtb.run_batch_test_async(
    project="complex_rag_pipeline",
    variant_matrix=[
        {"retriever": "default"},
        {"retriever": "bm25_retriever"},
        {"_workflow": "simple_rag_architecture"},
    ],
    test_cases=[{"query": "Test query"}],
)
```

---

## File Processing Full-Scale Test Suite (2026-01-15) ✓ COMPLETE

### Summary
Created comprehensive test suite for file processing module covering basic operations, advanced execution control, event integration, audit integration, Ray processing, and venv integration. **183 tests total**, all passing.

### Test Structure Created:

```
tests/test_file_processing/
├── __init__.py
├── conftest.py                          # Shared fixtures (InMemory repositories)
├── unit/
│   ├── __init__.py
│   ├── test_basic_operations.py         # 31 tests - FileMemento, FileCommit, Blob, CheckpointFileLink
│   └── test_execution_control.py        # 30 tests - Checkpoint, rollback, branch, pause/resume
└── integration/
    ├── __init__.py
    ├── test_file_event.py               # 30 tests - Event publishing, handlers, correlation
    ├── test_file_audit.py               # 25 tests - Audit trail integration
    ├── test_file_event_audit.py         # 28 tests - Combined event + audit
    ├── test_file_ray.py                 # 19 tests - Ray distributed processing
    └── test_file_venv.py                # 20 tests - Virtual environment integration
```

### Unit Tests (61 tests)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_basic_operations.py` | 31 | FileMemento, FileCommit, Blob storage, CheckpointFileLink |
| `test_execution_control.py` | 30 | Checkpoint creation, rollback, branching, pause/resume, single node |

### Integration Tests (122 tests)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_file_event.py` | 30 | Event publishing, handlers, correlation, immutability |
| `test_file_audit.py` | 25 | Audit trail recording, rollback audit, error audit |
| `test_file_event_audit.py` | 28 | Combined event + audit pipeline, transaction consistency |
| `test_file_ray.py` | 19 | Ray distributed file tracking, concurrent operations |
| `test_file_venv.py` | 20 | Venv linking, cross-environment sharing, lifecycle |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | Each test class tests one specific aspect (events, audit, etc.) |
| **OCP** | Mock repositories implement interfaces, easily swappable |
| **LSP** | InMemory implementations interchangeable with SQLAlchemy |
| **ISP** | Separate fixtures for different testing needs |
| **DIP** | Tests depend on interfaces (IBlobRepository, etc.) |

### ACID Compliance Tests

| Property | Tests |
|----------|-------|
| **Atomicity** | `test_file_event_audit.py::TestTransactionConsistency` |
| **Consistency** | `test_file_ray.py::TestTransactionConsistency` |
| **Isolation** | `test_file_ray.py::TestConcurrentOperations` |
| **Durability** | `test_file_audit.py::TestAuditTrailIntegration` |

### Key Test Categories

| Category | Description |
|----------|-------------|
| **Basic Operations** | Create, read, update, delete for all entities |
| **Execution Control** | Checkpoint, rollback, branch, pause, resume, single node execution |
| **Event Publishing** | File tracking events published correctly |
| **Event Handling** | Handlers receive and process events |
| **Audit Recording** | All operations recorded in audit trail |
| **Ray Processing** | Distributed file tracking across actors |
| **Venv Integration** | File tracking within virtual environments |

---

## File Processing DDD Refactoring (2026-01-15) ✓ COMPLETE

### Summary
Refactored legacy `file_processing/file_processing/FileTracker/` module to DDD structure.
Integrated with WTB's event bus, audit trail, and outbox pattern for ACID compliance.

### Files Created:
- `wtb/domain/models/file_processing.py` - FileCommit, FileMemento, BlobId, CommitId
- `wtb/domain/interfaces/file_processing_repository.py` - IBlobRepository, IFileCommitRepository
- `wtb/domain/events/file_processing_events.py` - 12 domain events
- `wtb/infrastructure/database/file_processing_orm.py` - ORM models
- `wtb/infrastructure/database/repositories/file_processing_repository.py` - SQLAlchemy + InMemory repos
- `docs/file_processing/INDEX.md` - Documentation index
- `docs/file_processing/ARCHITECTURE.md` - Architecture and design decisions
- `tests/test_wtb/test_file_processing_domain.py` - 47 domain tests
- `tests/test_wtb/test_file_processing_repository.py` - 35 repository tests
- `tests/test_wtb/test_file_processing_integration.py` - 19 integration tests

### SOLID Compliance:
| Principle | Implementation |
|-----------|----------------|
| **SRP** | FileCommit handles commits, FileMemento handles snapshots, BlobRepository handles storage |
| **OCP** | New storage backends via interface implementation |
| **LSP** | InMemory, SQLAlchemy repositories interchangeable |
| **ISP** | Separate interfaces for commits, mementos, blobs |
| **DIP** | Domain depends on abstractions (IRepository interfaces) |

### ACID Compliance:
| Property | Implementation |
|----------|----------------|
| **Atomicity** | UnitOfWork pattern ensures all-or-nothing commits |
| **Consistency** | Domain invariants enforced in entity constructors |
| **Isolation** | Database-level isolation via transactions |
| **Durability** | PostgreSQL/SQLite with WAL mode |

### Test Results:
- 101 new tests (47 domain + 35 repository + 19 integration)
- All tests passing

---

## DDD Checkpoint Refactor (2026-01-15) ✓ COMPLETE

### Summary
Refactored checkpoint concepts from infrastructure to domain layer following DDD principles.
Removed AgentGit-specific concepts and implemented LangGraph-compatible checkpoint model.

### Files Created:
- `wtb/domain/models/checkpoint.py` - Checkpoint, CheckpointId, ExecutionHistory domain models
- `wtb/domain/interfaces/checkpoint_store.py` - ICheckpointStore, ICheckpointStoreFactory interfaces
- `wtb/infrastructure/stores/__init__.py` - Checkpoint store exports
- `wtb/infrastructure/stores/inmemory_checkpoint_store.py` - InMemoryCheckpointStore implementation
- `wtb/infrastructure/stores/langgraph_checkpoint_store.py` - LangGraphCheckpointStore implementation
- `tests/test_wtb/test_checkpoint_models.py` - 52 tests for domain checkpoint models
- `tests/test_wtb/test_checkpoint_stores.py` - 33 tests for checkpoint stores
- `tests/test_wtb/test_langgraph_time_travel.py` - LangGraph time travel/rollback tests (2026-01-15)

### Files Modified:
- `wtb/domain/models/node_boundary.py` - Removed AgentGit concepts, uses CheckpointId
- `wtb/domain/events/checkpoint_events.py` - Uses CheckpointId, removed tool_track_position
- `wtb/domain/interfaces/repositories.py` - Updated INodeBoundaryRepository (execution_id based)
- `wtb/infrastructure/events/wtb_audit_trail.py` - Updated for new checkpoint events
- `wtb/infrastructure/database/models.py` - Added 'pending' and 'running' to node_status
- `wtb/infrastructure/database/inmemory_unit_of_work.py` - New execution-based methods
- `wtb/infrastructure/database/repositories/node_boundary_repository.py` - New execution-based methods

### Key Changes:
| Old (AgentGit) | New (DDD/LangGraph) |
|----------------|---------------------|
| `internal_session_id: int` | Removed (use execution_id) |
| `checkpoint_id: int` | `CheckpointId(value: str)` |
| `tool_track_position: int` | Removed (LangGraph doesn't track tools) |
| `tool_count`, `checkpoint_count` | Removed from NodeBoundary |
| `IStateAdapter` (business logic) | `ICheckpointStore` (persistence only) |
| `find_by_session(session_id)` | `find_by_execution(execution_id)` |

### Test Results:
- 386 passed, 12 skipped
- 88 new tests for checkpoint models and stores
- All LLM integration tests passing (OpenAI package added to dependencies)

---

## New Implementation (2025-01-09)

### Files Created (2025-01-09):

**Event Bus & Audit:**
- `wtb/infrastructure/events/__init__.py` - Event module exports
- `wtb/infrastructure/events/wtb_event_bus.py` - Thread-safe WTBEventBus with bounded history
- `wtb/infrastructure/events/wtb_audit_trail.py` - WTBAuditTrail, WTBAuditEntry, AuditEventListener
- `wtb/infrastructure/database/repositories/audit_repository.py` - AuditLogRepository

**Batch Test Infrastructure:**
- `wtb/domain/interfaces/batch_runner.py` - IBatchTestRunner, IEnvironmentProvider interfaces
- `wtb/application/services/batch_test_runner.py` - ThreadPoolBatchTestRunner implementation
- `wtb/application/services/ray_batch_runner.py` - RayBatchTestRunner (stub), VariantExecutionActor

**Environment Providers:**
- `wtb/infrastructure/environment/__init__.py` - Environment module exports
- `wtb/infrastructure/environment/providers.py` - InProcess/Ray/Grpc environment providers

**Database Migrations:**
- `wtb/infrastructure/database/migrations/002_batch_tests.sql` - SQLite batch test tables
- `wtb/infrastructure/database/migrations/003_postgresql_production.sql` - PostgreSQL indexes + JSONB

**Tests:**
- `tests/test_wtb/test_event_bus.py` - 20 tests for WTBEventBus
- `tests/test_wtb/test_audit_trail.py` - 24 tests for WTBAuditTrail
- `tests/test_wtb/test_audit_repository.py` - 3 tests for AuditRepository
- `tests/test_wtb/test_batch_runner.py` - 20 tests for batch runners

**Modified:**
- `wtb/config.py` - Added RayConfig dataclass and ray_enabled/ray_config fields
- `wtb/application/factories.py` - Added BatchTestRunnerFactory
- `wtb/domain/interfaces/__init__.py` - Export batch runner interfaces
- `wtb/infrastructure/__init__.py` - Export event bus and environment providers
- `wtb/domain/interfaces/repositories.py` - Added IAuditLogRepository
- `wtb/domain/interfaces/unit_of_work.py` - Added audit_logs
- `wtb/infrastructure/database/models.py` - Added AuditLogORM
- `wtb/infrastructure/database/unit_of_work.py` - Added audit_logs initialization
- `wtb/infrastructure/database/inmemory_unit_of_work.py` - Added InMemoryAuditLogRepository

### Design Patterns Implemented (2025-01-09):

- **Thread-Safe Event Bus**: RLock + bounded deque for concurrent access
- **Publish-Subscribe**: Event-driven audit tracking via AuditEventListener
- **Factory Pattern**: BatchTestRunnerFactory for ThreadPool/Ray selection
- **Interface Abstraction**: IBatchTestRunner, IEnvironmentProvider for swappable implementations
- **Actor Pattern (Ray)**: VariantExecutionActor for connection reuse

---

## Previous Implementation (2024-12-23)

### Files Created:

- `wtb/config.py` - WTBConfig with for_testing(), for_development(), for_production() presets
- `wtb/infrastructure/database/inmemory_unit_of_work.py` - Full in-memory repository implementations
- `wtb/infrastructure/database/factory.py` - UnitOfWorkFactory for mode-based UoW creation
- `wtb/infrastructure/adapters/agentgit_state_adapter.py` - AgentGit integration (**DEFERRED** - see LangGraph)
- `wtb/infrastructure/adapters/langgraph_state_adapter.py` - 🆕 **PRIMARY** state adapter (TODO)
- `wtb/application/factories.py` - ExecutionControllerFactory, NodeReplacerFactory
- `tests/test_wtb/test_factories.py` - 24 new tests for factories and config

### Design Patterns Implemented:

- **LangGraph-First Pattern**: LangGraph checkpointers + WTB (domain data) (Updated 2026-01-15)
- **Factory Pattern**: UoW and service factories for dependency injection
- **Repository Pattern**: In-memory implementations for all 7 repositories
- **Anti-Corruption Layer**: LangGraphStateAdapter bridges WTB ↔ LangGraph

## Architecture Fix (P0-P1) - 2024-12-23 - IMPLEMENTED ✓

### Architecture Review Results

| Priority     | Issue                            | Solution          | Status  |
| ------------ | -------------------------------- | ----------------- | ------- |
| **P0** | Cross-DB Transaction Consistency | Outbox Pattern    | ✅ DONE |
| **P0** | Data Integrity (Logical FKs)     | IntegrityChecker  | ✅ DONE |
| **P1** | Anemic Domain Model              | Rich Domain Model | ✅ DONE |
| P2           | Error Standardization            | Error Hierarchy   | TODO    |

### Files Created/Modified:

**Domain Models:**

- `wtb/domain/models/outbox.py` - OutboxEvent, OutboxEventType, OutboxStatus
- `wtb/domain/models/integrity.py` - IntegrityIssue, IntegrityReport, RepairAction
- `wtb/domain/models/workflow.py` - Enhanced Execution with rich business logic

**Interfaces:**

- `wtb/domain/interfaces/outbox_repository.py` - IOutboxRepository interface
- `wtb/domain/interfaces/unit_of_work.py` - Added outbox property to IUnitOfWork

**Infrastructure:**

- `wtb/infrastructure/database/models.py` - Added OutboxEventORM
- `wtb/infrastructure/database/repositories/outbox_repository.py` - SQLAlchemyOutboxRepository
- `wtb/infrastructure/database/inmemory_unit_of_work.py` - Added InMemoryOutboxRepository
- `wtb/infrastructure/outbox/processor.py` - OutboxProcessor background worker
- `wtb/infrastructure/integrity/checker.py` - IntegrityChecker implementation

**Tests (57 new tests):**

- `tests/test_wtb/test_outbox.py` - 26 tests for Outbox Pattern
- `tests/test_wtb/test_integrity.py` - 20 tests for IntegrityChecker
- `tests/test_wtb/test_cross_db_consistency.py` - 11 integration tests

### Outbox Pattern Overview:

```
┌─────────────────────────────────────────────────────────────┐
│                    WTB DB (Transaction Center)               │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │ wtb_executions│  │node_boundaries│  │   wtb_outbox    │  │
│  └───────────────┘  └───────────────┘  └────────┬────────┘  │
│                                                  │           │
│                            Atomic Write ─────────┘           │
└─────────────────────────────────────────────────────────────┘
                               │
                     OutboxProcessor (Background)
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       AgentGit DB      FileTracker DB    FileTracker FS
```

### Rich Domain Model Enhancements:

| Method                                  | Purpose                                  |
| --------------------------------------- | ---------------------------------------- |
| `Execution.start()`                   | State transition with validation         |
| `Execution.pause()`                   | Pause with reason tracking               |
| `Execution.resume()`                  | Resume with state modification support   |
| `Execution.complete()`                | Mark complete with final state           |
| `Execution.fail()`                    | Record failure with error details        |
| `Execution.record_node_result()`      | Track node execution results             |
| `Execution.advance_to_node()`         | Move to next node                        |
| `Execution.restore_from_checkpoint()` | Rollback support                         |
| `InvalidStateTransition`              | Domain exception for invalid transitions |

### Documentation Created:

- `docs/Adapter_and_WTB-Storage/ARCHITECTURE_FIX_DESIGN.md` - Full design document

## Event Bus & Audit Trail Design - 2024-12-23 - DESIGN COMPLETE

### AgentGit Analysis:

- **EventBus**: Publish-subscribe pattern, DomainEvent base, global singleton
- **AuditTrail**: LangChain callback integration, checkpoint metadata storage

### WTB Integration Design:

| Component          | Status      | Description                                |
| ------------------ | ----------- | ------------------------------------------ |
| WTBEventBus        | ✓ DESIGNED | Wraps AgentGit EventBus + thread-safety    |
| WTBAuditTrail      | ✓ DESIGNED | Node/Execution-level audit (vs tool-level) |
| AuditEventListener | ✓ DESIGNED | Auto-records WTB events to audit           |
| AgentGit Bridge    | ✓ DESIGNED | Bridge AgentGit events to WTB              |

### Documentation Created:

- `docs/EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md` - Full design document
- `docs/EventBus_and_Audit_Session/INDEX.md` - Navigation index

## Ray Batch Test Runner Design (2025-01) - DESIGN COMPLETE ✓

### Design Decision: Ray over ThreadPoolExecutor

| Criteria | ThreadPoolExecutor | Ray | Decision |
|----------|-------------------|-----|----------|
| **Parallelism** | GIL-bound | True distributed | Ray ✓ |
| **Resource Mgmt** | Manual | Declarative (`num_cpus`, `memory`) | Ray ✓ |
| **Failure Handling** | Basic exceptions | Built-in retry, fault tolerance | Ray ✓ |
| **Scaling** | Single-node | Multi-node cluster | Ray ✓ |
| **Development** | Simple | Local mode available | Tie |

### Key Components Designed

| Component | Status | Description |
|-----------|--------|-------------|
| `RayBatchTestRunner` | ✅ DESIGNED | Orchestrates parallel batch tests with ActorPool |
| `VariantExecutionActor` | ✅ DESIGNED | Ray Actor for executing single variant |
| `IBatchTestRunner` | ✅ DESIGNED | Interface for ThreadPool/Ray abstraction |
| `BatchTestRunnerFactory` | ✅ DESIGNED | Factory for runner selection |
| `RayConfig` | ✅ DESIGNED | Cluster configuration dataclass |
| `IEnvironmentProvider` | ✅ DESIGNED | Environment isolation interface |
| `RayEnvironmentProvider` | ✅ DESIGNED | Ray runtime_env implementation |

### Environment Management Decision

**Decision**: Adapt existing environment service via interface abstraction.
- Default: `RayEnvironmentProvider` (Ray runtime_env)
- Optional: `GrpcEnvironmentProvider` (wraps existing service)
- Rationale: Ray runtime_env is sufficient for most cases; interface allows future integration

### Documentation References

- Architecture: `WORKFLOW_TEST_BENCH_ARCHITECTURE.md` §17-19
- Data Storage: `DATABASE_DESIGN.md` (Batch Test Schema)
- Summary: `WORKFLOW_TEST_BENCH_SUMMARY.md` §7-8

---

## Parallel Session Design (2024-12-23) - SUPERSEDED BY RAY DESIGN

> **Note**: The ThreadPoolExecutor design below is superseded by Ray for production.
> ThreadPoolExecutor remains available for development/testing via `BatchTestRunnerFactory`.

### Original Design Decision: Multithreading + Application-Level Isolation

| Approach                     | Decision                | Rationale                                                     |
| ---------------------------- | ----------------------- | ------------------------------------------------------------- |
| **Threading Model**    | ThreadPoolExecutor      | WTB is I/O-bound (DB ops, LLM calls); GIL released during I/O |
| **Isolation Strategy** | App-level isolation     | Each thread gets own Adapter/Controller/UoW instances         |
| **SQLite Concurrency** | WAL mode enabled        | Allows concurrent reads, serialized writes                    |
| **Session Cleanup**    | SessionLifecycleManager | Timeout-based cleanup for abandoned sessions                  |

### New Components Designed

| Component                  | Status      | Description                                                    |
| -------------------------- | ----------- | -------------------------------------------------------------- |
| ParallelExecutionContext   | ✓ DESIGNED | Isolated context (adapter + controller + uow) per parallel run |
| ParallelContextFactory     | ✓ DESIGNED | Factory for creating isolated contexts                         |
| BatchTestRunner (parallel) | ✓ DESIGNED | ThreadPoolExecutor-based parallel execution                    |
| WAL Mode Config            | ✓ DESIGNED | SQLite WAL mode for concurrent access                          |
| SessionLifecycleManager    | ✓ DESIGNED | Cleanup abandoned sessions                                     |

### Documentation Updated

- [X] `WORKFLOW_TEST_BENCH_ARCHITECTURE.md` - Section 16 added
- [X] `WORKFLOW_TEST_BENCH_SUMMARY.md` - Section 5.5 added
- [X] `INDEX.md` - Links to parallel design sections

### Implementation TODO

| Component                 | Priority | Description                       |
| ------------------------- | -------- | --------------------------------- |
| ParallelExecutionContext  | HIGH     | Implement isolated context class  |
| ParallelContextFactory    | HIGH     | Implement context factory         |
| BatchTestRunner           | HIGH     | Implement with ThreadPoolExecutor |
| WAL Mode Config           | HIGH     | Add to database config            |
| test_parallel_sessions.py | HIGH     | Unit tests for parallel isolation |
| SessionLifecycleManager   | MEDIUM   | Timeout-based cleanup             |

---

---

## ✅ COMPLETED TODAY (2025-01-09)

### Morning: Event Bus & Audit Trail - ✓ DONE

| # | Task | Status | Files Created |
|---|------|--------|---------------|
| 1 | **Implement `WTBEventBus`** | ✅ DONE | `wtb/infrastructure/events/wtb_event_bus.py` |
| | - Standalone thread-safe implementation (RLock) | | |
| | - Bounded history (deque with maxlen) | | |
| | - Optional AgentGit bridge | | |
| | - 20 unit tests passing | | |
| 2 | **Implement `WTBAuditTrail`** | ✅ DONE | `wtb/infrastructure/events/wtb_audit_trail.py` |
| | - `WTBAuditEntry` dataclass | | |
| | - `add_entry()`, `flush()`, `to_dict()` | | |
| | - `AuditEventListener` for auto-recording | | |
| | - **Implement `AuditLogRepository`** | ✅ DONE | `wtb/infrastructure/database/repositories/audit_repository.py` |
| | - Added AuditLogORM, IAuditLogRepository | | |
| | - 27 unit tests passing | | |

### Afternoon: BatchTestRunner Infrastructure - ✓ DONE

| # | Task | Status | Files Created |
|---|------|--------|---------------|
| 3 | **Implement `IBatchTestRunner`** | ✅ DONE | `wtb/domain/interfaces/batch_runner.py` |
| | - `run_batch_test()`, `get_status()`, `cancel()` | | |
| | - `IEnvironmentProvider` interface | | |
| 4 | **Implement `ThreadPoolBatchTestRunner`** | ✅ DONE | `wtb/application/services/batch_test_runner.py` |
| | - ThreadPoolExecutor with UoW/StateAdapter factories | | |
| | - Progress tracking, cancellation support | | |
| | - 7 unit tests passing | | |
| 5 | **Implement `BatchTestRunnerFactory`** | ✅ DONE | `wtb/application/factories.py` |
| | - Factory method for ThreadPool/Ray selection | | |
| | - Config-based switching | | |

### Evening: Ray Foundation - ✓ DONE

| # | Task | Status | Files Created |
|---|------|--------|---------------|
| 6 | **Implement `RayConfig`** | ✅ DONE | `wtb/config.py` |
| | - Dataclass with cluster settings | | |
| | - `for_local_development()`, `for_production()` presets | | |
| 7 | **Stub `RayBatchTestRunner`** | ✅ STUB | `wtb/application/services/ray_batch_runner.py` |
| | - Basic structure with `@ray.remote` decorator | | |
| | - `VariantExecutionActor` stub | | |
| 8 | **Create database migrations** | ✅ DONE | `wtb/infrastructure/database/migrations/` |
| | - `002_batch_tests.sql` (SQLite) | | |
| | - `003_postgresql_production.sql` (PostgreSQL) | | |
| 9 | **Implement Environment Providers** | ✅ DONE | `wtb/infrastructure/environment/providers.py` |
| | - `InProcessEnvironmentProvider` | | |
| | - `RayEnvironmentProvider` | | |
| | - `GrpcEnvironmentProvider` (stub) | | |

### Files Created (2025-01-09)

```
wtb/
├── domain/
│   └── interfaces/
│       └── batch_runner.py          [CREATED] IBatchTestRunner, IEnvironmentProvider
├── application/
│   ├── services/
│       ├── batch_test_runner.py     [CREATED] ThreadPoolBatchTestRunner
│       └── ray_batch_runner.py      [CREATED] RayBatchTestRunner (stub), VariantExecutionActor
│   └── factories.py                 [MODIFIED] Added BatchTestRunnerFactory
├── infrastructure/
│   ├── events/
│   │   ├── __init__.py              [CREATED]
│   │   ├── wtb_event_bus.py         [CREATED] WTBEventBus
│   │   └── wtb_audit_trail.py       [CREATED] WTBAuditTrail, AuditEventListener
│   ├── environment/
│   │   ├── __init__.py              [CREATED]
│   │   └── providers.py             [CREATED] Ray/InProcess/Grpc providers
│   └── database/
│       ├── repositories/
│       │   └── audit_repository.py  [CREATED] AuditLogRepository
│       └── migrations/
│           ├── __init__.py          [CREATED]
│           ├── 002_batch_tests.sql  [CREATED] Batch test tables
│           └── 003_postgresql_production.sql [CREATED] PG indexes
├── config.py                        [MODIFIED] Added RayConfig
└── tests/
    └── test_wtb/
        ├── test_event_bus.py        [CREATED] 20 tests
        ├── test_audit_trail.py      [CREATED] 24 tests
        ├── test_audit_repository.py [CREATED] 3 tests
        └── test_batch_runner.py     [CREATED] 20 tests

Total: 275 tests passing (was 208, +67 new tests)
```

### Success Criteria - ALL MET ✅

- [x] `WTBEventBus` passes thread-safety tests (20 tests)
- [x] `WTBAuditTrail` can flush to repository (24 tests)
- [x] `ThreadPoolBatchTestRunner` can execute simple batch test (7 tests)
- [x] `BatchTestRunnerFactory` correctly selects runner based on config (3 tests)
- [x] Database migration files created
- [x] All new code has test coverage (67 new tests)
- [x] **AuditLogRepository implemented and tested**

---

## TODO (Backlog)

### P0 - Critical (External API + LangGraph Adapter)

| Component                              | Priority | Description                                    | Status |
| -------------------------------------- | -------- | ---------------------------------------------- | ------ |
| **External API (REST)**          | P0       | FastAPI REST endpoints for workflows/executions | ✅ DONE (2026-01-15) |
| **External API (WebSocket)**     | P0       | Real-time event streaming                       | ✅ DONE (2026-01-15) |
| **External API (gRPC)**          | P0       | gRPC service definition for internal/Ray comms  | ✅ DONE (2026-01-15) |
| **Workflow Submission SDK**      | P0       | WorkflowProject + WTBTestBench                  | ✅ DONE (2026-01-15) |
| **FileTracker Verification**     | P0       | Outbox handlers for FileTracker verification    | ✅ DONE (2026-01-15) |
| **OpenTelemetry Integration**    | P0       | Observability: traces, metrics, logs            | 🔄 TODO |
| **LangGraphStateAdapter**        | P0       | PRIMARY: Adapter using LangGraph checkpointers | 🆕 TODO |
| **LangGraph Checkpointer Setup** | P0       | Configure PostgresSaver for production         | 🆕 TODO |
| **RayBatchTestRunner (full)**    | P0       | Complete Ray implementation with ActorPool     | ✅ DONE |
| **VariantExecutionActor**        | P0       | Ray Actor for workflow variant execution       | ✅ DONE |
| **ParityChecker**                | P0       | Dry-run validation for ThreadPool→Ray migration| ✅ DONE (2026-01-15) |
| **RayEventBridge**               | P0       | Ray events integrated with EventBus & Audit    | ✅ DONE (2026-01-15) |
| **PgBouncer Setup**              | P0       | Connection pooling for production              | TODO |
| **Outbox Verify Handlers**       | P0       | FileTracker verification in OutboxProcessor    | TODO |

### P1 - High Priority (Supporting Infrastructure)

| Component                              | Priority | Description                                    | Status |
| -------------------------------------- | -------- | ---------------------------------------------- | ------ |
| **IEnvironmentProvider**         | P1       | Interface for environment isolation            | ✅ DONE |
| **RayEnvironmentProvider**       | P1       | Ray runtime_env based isolation                | ✅ DONE |
| **GrpcEnvironmentProvider**      | P1       | Adapter for UV Venv Manager gRPC service       | ✅ DONE |
| **Prometheus Metrics**           | P1       | Metric export for observability                | TODO |
| **WAL Mode Config**              | P1       | SQLite concurrent access support               | ✅ DONE |
| **PostgreSQL Migration**         | P1       | Production database migration scripts          | ✅ DONE |

### P2 - Medium Priority

| Component                              | Priority | Description                                    |
| -------------------------------------- | -------- | ---------------------------------------------- |
| EvaluationEngine                       | P2       | Metrics collection & scoring                   |
| SessionLifecycleManager                | P2       | Cleanup abandoned sessions                     |
| Error Hierarchy                        | P2       | Standardized error types and handling          |
| Parallel Session Tests                 | P2       | Test isolation and thread safety               |
| Ray Integration Tests                  | P2       | Test Ray batch execution end-to-end            |

### P3 - Low Priority

| Component                              | Priority | Description                                    | Status |
| -------------------------------------- | -------- | ---------------------------------------------- | ------ |
| ~~FileTracker Integration~~            | ~~P3~~   | ~~Link checkpoints to file commits~~           | ✅ DONE |
| IDE Sync                               | P3       | WebSocket events to audit UI                   | TODO |
| AgentGit Integration Tests             | P3       | Integration tests with real AgentGit database  | TODO |

---

## ActorLifecycleManager + VenvCacheManager Implementation (2026-01-16) ✓ COMPLETE

### Summary
Implemented `ActorLifecycleManager` for managing Ray actor lifecycle with Hot/Warm/Cold pause strategies, and `VenvCacheManager` for caching virtual environments with LRU eviction policy.

### Files Created

**Application Services:**
- `wtb/application/services/actor_lifecycle.py` - ActorLifecycleManager (~400 lines)
  - Hot pause: Actor running, paused flag set
  - Warm pause: Actor running, minimal state
  - Cold pause: Actor killed, recreate on resume
  - PauseStrategySelector for automatic strategy selection

**Infrastructure:**
- `wtb/infrastructure/environment/venv_cache.py` - VenvCacheManager (~300 lines)
  - LRU eviction based on last_access_time
  - Age-based eviction (max 7 days default)
  - Spec hash-based cache lookup
  - Copy-to-workspace functionality

**Tests:**
- `tests/test_wtb/test_actor_lifecycle.py` - 25 unit tests
- `tests/test_wtb/test_venv_cache.py` - 18 unit tests

### Key Components

| Component | Description |
|-----------|-------------|
| `ActorLifecycleManager` | Manages Ray actor create/reset/pause/resume/fork/kill |
| `PauseStrategySelector` | Selects Hot/Warm/Cold based on duration + resources |
| `ActorHandle` | Tracks actor state, resources, workspace |
| `VenvCacheManager` | LRU cache for virtual environments |
| `VenvCacheEntry` | Cache entry with path, spec_hash, size, last_access |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | ActorLifecycleManager handles lifecycle only, VenvCacheManager handles caching only |
| **OCP** | New pause strategies via PauseStrategy enum extension |
| **LSP** | All pause strategies implement same contract |
| **ISP** | Focused interfaces for each manager |
| **DIP** | Depends on WTBEventBus abstraction |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | Actor operations are atomic (create/kill) |
| **Consistent** | State transitions validated |
| **Isolated** | Per-actor state tracking |
| **Durable** | Events published to audit trail |

### Test Results
- 43 new tests (25 actor lifecycle + 18 venv cache)
- All tests passing

### Architecture

```
ActorLifecycleManager
    │
    ├── PauseStrategySelector
    │       │
    │       ├── duration < 5min → HOT
    │       ├── duration < 30min + no GPU → WARM
    │       └── duration >= 30min OR GPU → COLD
    │
    ├── Actor Operations
    │       │
    │       ├── create_actor() → Ray actor + ActorHandle
    │       ├── reset_actor() → Clear internal state
    │       ├── pause_actor() → Apply strategy
    │       ├── resume_actor() → Resume or recreate
    │       ├── fork_actor() → New actor for fork
    │       └── kill_actor() → Terminate + cleanup
    │
    └── Event Publishing
            │
            └── WTBEventBus → Audit Trail

VenvCacheManager
    │
    ├── Cache Operations
    │       │
    │       ├── get_by_spec(hash) → Cached venv path
    │       ├── put(entry) → Add to cache
    │       ├── copy_to_workspace() → Copy cached venv
    │       └── invalidate() → Remove from cache
    │
    └── Eviction Policy
            │
            ├── LRU by last_access_time
            └── Age-based (max 7 days)
```

---

## Workspace Isolation Implementation (2026-01-16) ✓ COMPLETE

### Summary
Implemented workspace isolation for parallel variant execution via Ray. Each variant runs in an isolated workspace directory, preventing file system race conditions and data corruption during batch tests. Supports hard links for efficient file sharing with fallback to copy for cross-partition scenarios.

### Files Created

**Domain Layer:**
- `wtb/domain/models/workspace.py` - Workspace, WorkspaceConfig, WorkspaceStrategy, LinkMethod, LinkResult, OrphanWorkspace, CleanupReport (~350 lines)
- `wtb/domain/events/workspace_events.py` - 15+ workspace domain events (lifecycle, file ops, fork, venv, Ray actor, cleanup)

**Infrastructure:**
- `wtb/infrastructure/workspace/__init__.py` - Module exports
- `wtb/infrastructure/workspace/manager.py` - WorkspaceManager with hard links, orphan cleanup (~400 lines)

**SDK:**
- `wtb/sdk/workflow_project.py` - Added WorkspaceIsolationConfig

**Tests:**
- `tests/test_wtb/test_workspace_manager.py` - 38 unit tests for Workspace model, config, linking, manager
- `tests/test_wtb/test_workspace_integration.py` - 13 integration tests for end-to-end scenarios
- `tests/test_wtb/test_ray_workspace_integration.py` - 10 integration tests for Ray-workspace integration
- `tests/test_workspace/` - Comprehensive workspace isolation test suite (87 tests total):
  - `conftest.py` - Shared fixtures for Ray, LangGraph, Venv, FileSystem
  - `test_real_ray_workspace.py` - Real Ray + workspace integration (11 tests)
  - `test_langgraph_workspace.py` - LangGraph + workspace + checkpoint (10 tests)
  - `test_venv_workspace.py` - Venv isolation tests (20 tests)
  - `test_filesystem_workspace.py` - FileTracker + workspace tests (20 tests)
  - `test_full_integration.py` - All systems combined: pause/resume/rollback/branch (15 tests)
  - `test_parallel_integration.py` - Parallel execution isolation tests (13 tests)

### Files Modified

- `wtb/application/services/ray_batch_runner.py` - Integrated workspace isolation:
  - `VariantExecutionActor.__init__` accepts workspace_config, workspace_id
  - `VariantExecutionActor._ensure_initialized` initializes WorkspaceManager
  - `VariantExecutionActor.execute_variant` activates/deactivates workspace
  - `RayBatchTestRunner.__init__` accepts workspace_config, initializes WorkspaceManager
  - `RayBatchTestRunner._create_actor_pool` passes workspace_config to actors
  - `RayBatchTestRunner.run_batch_test` creates workspaces per variant, passes workspace_id, cleans up in finally

### Key Components

| Component | Description |
|-----------|-------------|
| `Workspace` | Value object with derived paths (input, output, venv, lock, meta) |
| `WorkspaceConfig` | Configuration with base_dir, strategy, isolation flags |
| `WorkspaceStrategy` | FULL_COPY, HARDLINK_WITH_FALLBACK, SYMLINK |
| `WorkspaceManager` | Creates, activates, cleans up isolated workspaces |
| `LinkResult` | Tracks link method and size for each file |
| `OrphanWorkspace` | Detects abandoned workspaces via lock files + PID checks |
| `CleanupReport` | Reports cleanup results with statistics |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | Workspace handles state, WorkspaceManager handles lifecycle |
| **OCP** | New strategies via WorkspaceStrategy enum |
| **LSP** | LinkMethod implementations interchangeable |
| **ISP** | Focused interfaces for workspace operations |
| **DIP** | RayBatchTestRunner depends on WorkspaceManager abstraction |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | Workspace creation/cleanup in single operations |
| **Consistent** | Lock files ensure single-writer per workspace |
| **Isolated** | Each variant gets isolated directory tree |
| **Durable** | Workspace state persisted via meta.json |

### Test Results
- 148 workspace-related tests total:
  - `tests/test_wtb/`: 61 tests (38 unit + 13 integration + 10 Ray integration)
  - `tests/test_workspace/`: 87 comprehensive integration tests
    - Real Ray parallel execution with workspace isolation
    - LangGraph checkpoint + rollback + fork coordination
    - Venv spec hash tracking and invalidation detection
    - FileTracker integration and file isolation
    - Pause/resume/update node/update workflow/branch/rollback flows
    - Thread-safe concurrent workspace creation (20+ threads)
    - High concurrency file writes (50+ workers)
- All tests passing

### Architecture

```
RayBatchTestRunner
    │
    ├── WorkspaceManager.create_workspace() [per variant]
    │       │
    │       ▼
    │   base_dir/
    │   └── batch_{batch_id}/
    │       └── variant_{variant_id}/
    │           ├── input/      [hard-linked source files]
    │           ├── output/     [variant-specific outputs]
    │           ├── venv/       [isolated Python environment]
    │           ├── workspace.lock
    │           └── workspace_meta.json
    │
    ├── VariantExecutionActor.execute_variant()
    │       │
    │       ├── workspace.activate()
    │       ├── [execute workflow in isolated workspace]
    │       └── workspace.deactivate()
    │
    └── WorkspaceManager.cleanup_batch() [in finally block]
```

### Usage

```python
from wtb.domain.models.workspace import WorkspaceConfig, WorkspaceStrategy
from wtb.application.services.ray_batch_runner import RayBatchTestRunner

# Create workspace config
workspace_config = WorkspaceConfig(
    base_dir=Path("./workspaces"),
    strategy=WorkspaceStrategy.HARDLINK_WITH_FALLBACK,
    enable_venv_isolation=True,
)

# Create runner with workspace isolation
runner = RayBatchTestRunner(
    config=RayConfig.for_local_development(),
    agentgit_db_url="data/agentgit.db",
    wtb_db_url="sqlite:///data/wtb.db",
    workspace_config=workspace_config,
)

# Execute batch test - workspaces automatically managed
result = runner.run_batch_test(batch_test)
```

---

## Ray Event Bus & Audit Integration (2026-01-15) ✓ COMPLETE

### Summary
Integrated Ray batch testing with WTB Event Bus and Audit system, ensuring ACID-compliant event publishing using the outbox pattern.

### Files Created

**Domain Layer:**
- `wtb/domain/events/ray_events.py` - 18 Ray domain events (batch test, actor, variant lifecycle)

**Infrastructure:**
- `wtb/infrastructure/events/ray_event_bridge.py` - RayEventBridge with outbox pattern (~600 lines)

**Tests:**
- `tests/test_wtb/test_ray_event_integration.py` - 35+ unit tests for Ray events
- `tests/test_wtb/test_ray_transaction_consistency.py` - 20+ ACID compliance tests

### Files Modified

- `wtb/domain/events/__init__.py` - Export Ray events
- `wtb/infrastructure/events/__init__.py` - Export RayEventBridge
- `wtb/infrastructure/events/wtb_audit_trail.py` - Added 12 Ray audit event types
- `wtb/application/services/ray_batch_runner.py` - Integrated event bridge

### Key Components

| Component | Description |
|-----------|-------------|
| `RayEventBridge` | Publishes events with outbox pattern for ACID compliance |
| `RayBatchTestStartedEvent` | Published when batch test begins |
| `RayBatchTestCompletedEvent` | Published when batch test completes |
| `RayVariantExecutionCompletedEvent` | Published per variant completion |
| `RayActorPoolCreatedEvent` | Published when actor pool is created |
| `WTBAuditEventType.RAY_*` | 12 Ray-specific audit event types |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | RayEventBridge handles event publishing only |
| **OCP** | New event types via inheritance from WTBEvent |
| **LSP** | Ray events interchangeable with other WTBEvents |
| **ISP** | Focused event interfaces (serialization, publishing) |
| **DIP** | Depends on WTBEventBus abstraction, IOutboxRepository |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | Events written to outbox in same transaction as state |
| **Consistent** | Event schema validated on serialization |
| **Isolated** | Per-batch audit trails, thread-safe publishing |
| **Durable** | Outbox pattern ensures events persist before publish |

### Architecture

```
Ray Actor ──► RayEventBridge ──► OutboxRepository (transactional)
                   │                    │
                   │                    ▼
                   │              OutboxProcessor (background)
                   │                    │
                   ▼                    ▼
             WTBEventBus ◄────────────────
                   │
                   ▼
             WTBAuditTrail
```

### Usage

```python
from wtb.application.services.ray_batch_runner import RayBatchTestRunner
from wtb.infrastructure.events import get_wtb_event_bus, RayEventBridge

# Create runner with event bridge
runner = RayBatchTestRunner(
    config=RayConfig.for_local_development(),
    agentgit_db_url="data/agentgit.db",
    wtb_db_url="sqlite:///data/wtb.db",
    enable_audit=True,
)

# Execute batch test - events automatically published
result = runner.run_batch_test(batch_test)

# Get audit trail for the batch test
audit = runner.get_batch_audit_trail(batch_test.id)
print(audit.format_display())
```

---

## Single-Run File Tracking Integration (2026-01-17) ✓ COMPLETE

### Summary
Implemented file tracking for single `bench.run()` execution path, bridging the gap between Ray batch execution (which had file tracking) and single-run execution (which didn't).

### Problem Solved
- Ray `RayBatchTestRunner` had file tracking via `RayFileTrackerService` ✅
- `ExecutionController` and `WTBTestBench.run()` did NOT track files ❌
- Rollback restored LangGraph state but NOT file system state
- Demo incorrectly claimed "File system restored" during rollback

### Solution
1. Created `SqliteFileTrackingService` - lightweight SQLite-based file tracking (no PostgreSQL)
2. Wired `IFileTrackingService` into `ExecutionController` as optional dependency
3. Updated `WTBTestBenchFactory` with `enable_file_tracking` parameter
4. Fixed demo script to accurately reflect file rollback status

### Files Created

**Infrastructure:**
- `wtb/infrastructure/file_tracking/sqlite_service.py` - SqliteFileTrackingService (~600 lines)
  - SQLite + content-addressed blob storage (Git-like)
  - Thread-safe with connection-per-thread pattern
  - Full `IFileTrackingService` implementation

### Files Modified

- `wtb/infrastructure/file_tracking/__init__.py` - Added SqliteFileTrackingService export
- `wtb/application/services/execution_controller.py` - Added file_tracking_service parameter, file restore on rollback
- `wtb/application/factories.py` - Added enable_file_tracking to create_for_development() and create_with_langgraph()
- `examples/wtb_presentation/scripts/05_full_presentation.py` - Fixed rollback demo to show accurate file status

### Key Components

| Component | Description |
|-----------|-------------|
| `SqliteFileTrackingService` | Lightweight SQLite-based file tracking (no PostgreSQL) |
| `ExecutionController.rollback()` | Now restores files if file_tracking_service provided |
| `WTBTestBenchFactory` | `enable_file_tracking=True` to enable file rollback |

### Storage Layout

```
{workspace}/.filetrack/
├── blobs/              # Content-addressed file storage
│   ├── ab/
│   │   └── cdef1234... # SHA256 hash prefix directory
│   └── ...
└── filetrack.db        # SQLite: commits, mementos, checkpoint_links
```

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | SqliteFileTrackingService handles file tracking only |
| **OCP** | New implementations via IFileTrackingService interface |
| **LSP** | Mock, SQLite, PostgreSQL services interchangeable |
| **ISP** | Focused interface for file operations |
| **DIP** | ExecutionController depends on IFileTrackingService abstraction |

### ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomic** | SQLite transactions for commit creation |
| **Consistent** | SHA256 hashes validate file content |
| **Isolated** | Per-thread connections |
| **Durable** | SQLite with WAL mode |

### Usage

```python
# Enable file tracking for development
from wtb.application.factories import WTBTestBenchFactory

# Option 1: Development with file tracking
wtb = WTBTestBenchFactory.create_for_development(
    data_dir="data",
    enable_file_tracking=True  # NEW!
)

# Option 2: LangGraph with file tracking
wtb = WTBTestBenchFactory.create_with_langgraph(
    checkpointer_type="sqlite",
    data_dir="data",
    enable_file_tracking=True  # NEW!
)

# Now rollback restores BOTH state AND files
rollback_result = wtb.rollback(execution_id, checkpoint_id)

# Check file restore status
state = wtb.get_state(execution_id)
file_status = state.workflow_variables.get("_file_restore_status", {})
print(f"Files restored: {file_status.get('success', False)}")
```

---

## Ray + FileTracker Integration (2026-01-15) ✓ COMPLETE

### Summary
Implemented full integration between Ray Batch Test Runner and FileTracker for distributed file version control during batch test execution.

### Files Created

**Domain Layer:**
- `wtb/domain/interfaces/file_tracking.py` - IFileTrackingService interface with value objects

**Config:**
- `wtb/config.py` - Added FileTrackingConfig dataclass

**Infrastructure:**
- `wtb/infrastructure/file_tracking/__init__.py` - Module exports
- `wtb/infrastructure/file_tracking/mock_service.py` - MockFileTrackingService (testing)
- `wtb/infrastructure/file_tracking/filetracker_service.py` - FileTrackerService (real FileTracker)
- `wtb/infrastructure/file_tracking/ray_filetracker_service.py` - RayFileTrackerService (Ray actors)

**Tests:**
- `tests/test_wtb/test_file_tracking.py` - 31 unit tests
- `tests/test_wtb/test_ray_filetracker_integration.py` - 20 integration tests (16 passed, 4 skipped)

### Files Modified

- `wtb/application/services/ray_batch_runner.py` - Added FileTracker integration to VariantExecutionActor and RayBatchTestRunner
- `wtb/domain/interfaces/__init__.py` - Export file tracking interfaces

### Key Components

| Component | Description |
|-----------|-------------|
| `IFileTrackingService` | Interface for file tracking operations |
| `FileTrackingConfig` | Configuration with presets (testing/dev/prod) |
| `MockFileTrackingService` | In-memory mock for unit testing |
| `FileTrackerService` | Real integration with FileTracker (PostgreSQL) |
| `RayFileTrackerService` | Ray-compatible wrapper with serializable config |

### SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | IFileTrackingService only handles file operations |
| **OCP** | New tracking strategies via interface implementation |
| **LSP** | Mock, Local, Ray services are interchangeable |
| **ISP** | Focused interface with single responsibility |
| **DIP** | High-level components depend on IFileTrackingService abstraction |

### Usage

```python
from wtb.config import FileTrackingConfig, RayConfig
from wtb.application.services.ray_batch_runner import RayBatchTestRunner

# Create FileTracker config
ft_config = FileTrackingConfig.for_production(
    postgres_url="postgresql://localhost/filetracker",
    storage_path="/data/file_storage",
    wtb_db_url="postgresql://localhost/wtb",
)

# Create runner with FileTracker
runner = RayBatchTestRunner(
    config=RayConfig.for_production("ray://cluster:10001"),
    agentgit_db_url="data/agentgit.db",
    wtb_db_url="postgresql://localhost/wtb",
    filetracker_config=ft_config.to_dict(),
)

# Execute batch test - files automatically tracked
result = runner.run_batch_test(batch_test)
```

---

## Architecture Decision (2026-01-15)

### LangGraph Adapter Priority - ✓ APPROVED

**Decision**: Use LangGraph checkpointers as PRIMARY state persistence instead of AgentGit.

| Aspect | LangGraph Advantage |
|--------|---------------------|
| **Production-proven** | Used by LangSmith in production |
| **Thread isolation** | Native `thread_id` for batch test parallelism |
| **Time travel** | Built-in `get_state_history()`, `update_state()` |
| **Backends** | `InMemorySaver`, `SqliteSaver`, `PostgresSaver` |
| **Fault tolerance** | Pending writes preserved on node failure |
| **Serialization** | `JsonPlusSerializer` with optional encryption |

### LangGraph Key APIs

```python
# Compile with checkpointer
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
graph = workflow.compile(checkpointer=checkpointer)

# Execute with thread isolation
config = {"configurable": {"thread_id": f"batch-{variant_id}"}}
result = graph.invoke(initial_state, config)

# Time travel
history = list(graph.get_state_history(config))
graph.get_state({"configurable": {"thread_id": "1", "checkpoint_id": "abc123"}})

# Update state mid-execution
graph.update_state(config, {"modified_value": 42}, as_node="node_name")
```

### Impact on State Adapter

| Adapter | Status | Description |
|---------|--------|-------------|
| `LangGraphStateAdapter` | 🆕 **TODO (P0)** | PRIMARY - wraps LangGraph checkpointer |
| `InMemoryStateAdapter` | ✅ Kept | For unit testing |
| `AgentGitStateAdapter` | ⏸️ **DEFERRED** | Interface marked only, implement later if needed |

---

## New Implementation (2026-01-14)

### Ray Batch Test Runner - ✓ COMPLETE

| # | Task | Status | Files |
|---|------|--------|-------|
| 1 | **Implement `VariantExecutionActor`** | ✅ DONE | `wtb/application/services/ray_batch_runner.py` |
| | - Ray Actor with lazy initialization | | |
| | - ExecutionController integration | | |
| | - Isolated UoW/StateAdapter per actor | | |
| | - Health check and stats tracking | | |
| 2 | **Implement `RayBatchTestRunner`** | ✅ DONE | `wtb/application/services/ray_batch_runner.py` |
| | - ActorPool for connection reuse | | |
| | - ObjectRef tracking for cancellation | | |
| | - Backpressure via max_pending_tasks | | |
| | - Workflow loading and serialization | | |
| 3 | **Add comprehensive tests** | ✅ DONE | `tests/test_wtb/test_ray_batch_runner.py` |
| | - 26 tests (15 passed, 11 skipped) | | |
| | - ACID compliance tests | | |
| | - Performance tests | | |

### Design Decisions (2026-01-14)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Actor vs Task | Actor | Database connection reuse |
| Backpressure | ray.wait() + max_pending | Prevent OOM |
| Cancellation | ObjectRef tracking | Clean task termination |
| Isolation | Per-actor UoW/StateAdapter | Thread-safe execution |
| Serialization | Workflow.to_dict() | Ray-compatible |

### Files Modified (2026-01-14)

```
wtb/
├── application/
│   └── services/
│       └── ray_batch_runner.py    [REWRITTEN] Full implementation
tests/
└── test_wtb/
    └── test_ray_batch_runner.py   [CREATED] 26 comprehensive tests
pyproject.toml                      [MODIFIED] Package configuration
```

---

## UV Venv Manager Cleanup (2026-01-15) ✓ COMPLETE

### Summary
Refactored UV Venv Manager to focus on ENVIRONMENT PROVISIONING ONLY. Removed `RunCode` functionality (nodes are complete projects, not code snippets), removed duplicate Ray integration (Ray belongs in WTB), and cleaned up outdated code.

### Architecture Decision

| Decision | Rationale |
|----------|-----------|
| **RunCode REMOVED** | A node is a complete project (e.g., RAG pipeline), not a code snippet to execute |
| **Ray integration REMOVED** | Ray belongs in WTB's RayBatchTestRunner, not in UV Venv Manager |
| **gRPC Service Pattern** | UV Venv Manager is a standalone gRPC service (like FileTracker) |

### Files Deleted
- `uv_venv_manager/src/integrations/ray_executor.py` - Duplicate Ray integration
- `docs/venv_management/ARCHITECTURE_REVIEW.md` - Outdated
- `docs/venv_management/ERROR_HANDLING_ROLLBACK.md` - Implemented in code
- `docs/venv_management/INTEGRATION_POINTS.md` - Superseded by gRPC pattern
- `docs/venv_management/MIGRATION_PLAN.md` - No longer applicable
- `docs/venv_management/SYSTEM_OVERVIEW.md` - Consolidated into INDEX.md
- `docs/venv_management/VENV_LIFECYCLE_DESIGN.md` - Implemented in code

### Files Modified
- `uv_venv_manager/src/protos/env_manager.proto` - Removed `RunCode` RPC
- `uv_venv_manager/src/api.py` - Removed `/run` endpoint
- `uv_venv_manager/src/grpc_servicer.py` - Removed `RunCode` handler
- `uv_venv_manager/src/services/env_manager.py` - Removed `run()` method
- `uv_venv_manager/src/services/uv_executor.py` - Removed `run_code()` method
- `uv_venv_manager/src/integrations/client.py` - Removed `run_code()` method
- `uv_venv_manager/src/models.py` - Removed `RunRequest`, `RunResponse`
- `uv_venv_manager/src/exceptions.py` - Removed `ExecutionTimeout`
- `uv_venv_manager/src/domain/interfaces.py` - Removed `publish_code_execution()`
- `uv_venv_manager/src/infrastructure/event_publisher.py` - Removed code execution events
- `wtb/domain/events/environment_events.py` - Removed `CodeExecution*` events
- `docs/venv_management/INDEX.md` - Consolidated documentation

### Files Created
- `tests/test_wtb/test_environment_events.py` - 21 unit tests for environment events

### Test Results
- 21 environment event tests passing
- gRPC stubs regenerated

### Documentation Consolidated
All venv_management documentation consolidated into single `INDEX.md` with:
- Architecture decision summary
- Component diagram
- SOLID/ACID compliance table
- gRPC Service API reference
- Domain events table
- Project structure
- Usage examples

---

## New Implementation (2026-01-15)

### ParityChecker for ThreadPool→Ray Migration - ✓ COMPLETE

| # | Task | Status | Files |
|---|------|--------|-------|
| 1 | **Implement `ParityChecker`** | ✅ DONE | `wtb/application/services/parity_checker.py` |
| | - Dry-run comparison of ThreadPool vs Ray | | |
| | - Configurable metric tolerance | | |
| | - Statistical comparison support | | |
| | - Discrepancy tracking and reporting | | |
| 2 | **Create `ParityCheckResult` model** | ✅ DONE | `wtb/application/services/parity_checker.py` |
| | - Speedup factor calculation | | |
| | - Discrepancy list with types | | |
| | - Serialization to dict | | |
| 3 | **Add comprehensive tests** | ✅ DONE | `tests/test_wtb/test_parity_checker.py` |
| | - 21 tests (20 passed, 1 skipped) | | |
| | - Unit tests with mocked runners | | |
| | - Statistical comparison tests | | |
| 4 | **Update factories** | ✅ DONE | `wtb/application/factories.py` |
| | - Added `create_parity_checker()` | | |
| | - Updated exports in `__init__.py` | | |

### Design Decisions (2026-01-15)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Comparison Mode | Dry-run by default | Avoid modifying original batch test |
| Tolerance | Configurable (default 1%) | Account for non-determinism |
| Timing Metrics | Ignored by default | Timing varies between runners |
| Discrepancy Types | Enum-based | Clear categorization |
| Statistical Mode | Multiple runs | Validate consistency |

### Files Created/Modified (2026-01-15)

```
wtb/
├── application/
│   ├── services/
│   │   ├── __init__.py            [MODIFIED] Added exports
│   │   └── parity_checker.py      [CREATED] Full implementation (~400 lines)
│   └── factories.py               [MODIFIED] Added create_parity_checker()
tests/
└── test_wtb/
    └── test_parity_checker.py     [CREATED] 21 comprehensive tests
docs/
└── Project_Init/
    └── WORKFLOW_TEST_BENCH_ARCHITECTURE.md [MODIFIED] Added decision
```

---

## Recently Completed (2024-12-23)

| Component               | Status      | Tests    |
| ----------------------- | ----------- | -------- |
| ~~Outbox Pattern~~     | ✅ DONE     | 26 tests |
| ~~IntegrityChecker~~   | ✅ DONE     | 20 tests |
| ~~Rich Domain Model~~  | ✅ DONE     | 11 tests |
| ~~Event Bus Design~~   | ✅ DESIGNED | -        |
| ~~Audit Trail Design~~ | ✅ DESIGNED | -        |

## Database Status

| Database | Location             | Status                            |
| -------- | -------------------- | --------------------------------- |
| AgentGit | `data/agentgit.db` | 31 checkpoints, 22 sessions       |
| WTB      | `data/wtb.db`      | Schema created, persistence ready |

## Usage Examples

### Testing Mode (In-Memory)

```python
from wtb.config import WTBConfig
from wtb.application import ExecutionControllerFactory

config = WTBConfig.for_testing()
controller = ExecutionControllerFactory.create_for_testing()
```

### Development Mode (SQLite)

```python
config = WTBConfig.for_development()
controller = ExecutionControllerFactory.create(config)
```

### Production Mode (PostgreSQL)

```python
config = WTBConfig.for_production("postgresql://user:pass@host/db")
controller = ExecutionControllerFactory.create(config)
```

## Next Steps

### Completed ✓

1. ~~Create `AgentGitStateAdapter` to replace `InMemoryStateAdapter`~~ ✓ DONE
2. ~~Add `InMemoryUnitOfWork` for fast testing~~ ✓ DONE
3. ~~Create factories for dependency injection~~ ✓ DONE
4. ~~Design parallel session isolation architecture~~ ✓ DONE (Section 16)
5. ~~Implement Outbox Pattern for cross-DB consistency~~ ✓ DONE (P0)
6. ~~Implement IntegrityChecker for data integrity~~ ✓ DONE (P0)
7. ~~Enhance Execution with Rich Domain Model~~ ✓ DONE (P1)
8. ~~Design Event Bus & Audit Trail integration~~ ✓ DONE (Design)
9. ~~Design Ray-based BatchTestRunner architecture~~ ✓ DONE (2025-01)
10. ~~Design IEnvironmentProvider interface~~ ✓ DONE (2025-01)
11. ~~Define data characteristics & indexing strategy~~ ✓ DONE (2025-01)
12. ~~Implement `WTBEventBus` with thread-safety~~ ✓ DONE (2025-01-09)
13. ~~Implement `WTBAuditTrail` and `AuditEventListener`~~ ✓ DONE (2025-01-09)
14. ~~Implement `IBatchTestRunner` interface~~ ✓ DONE (2025-01-09)
15. ~~Implement `ThreadPoolBatchTestRunner`~~ ✓ DONE (2025-01-09)
16. ~~Create `BatchTestRunnerFactory`~~ ✓ DONE (2025-01-09)
17. ~~Add `RayConfig` to `WTBConfig`~~ ✓ DONE (2025-01-09)
18. ~~Create database migrations for batch test tables~~ ✓ DONE (2025-01-09)
19. ~~Implement `IEnvironmentProvider` and `RayEnvironmentProvider`~~ ✓ DONE (2025-01-09)
20. ~~Stub `RayBatchTestRunner` with `VariantExecutionActor`~~ ✓ STUB (2025-01-09)
21. ~~Implement `IAuditLogRepository` for audit persistence~~ ✓ DONE (2025-01-09)
22. ~~Complete `RayBatchTestRunner` implementation~~ ✓ DONE (2026-01-14)
23. ~~Complete `VariantExecutionActor` with ExecutionController integration~~ ✓ DONE (2026-01-14)
24. ~~Add comprehensive Ray unit tests~~ ✓ DONE (2026-01-14)
25. ~~Create LangGraph time travel unit tests~~ ✓ DONE (2026-01-15)
    - `test_langgraph_time_travel.py` - Tests for rollback, no future leak, branching
26. ~~Update documentation for AgentGit dual-granularity DEFERRED status~~ ✓ DONE (2026-01-15)
    - Changed "REJECTED/WRONG" to "DEFERRED" in all docs
    - Preserved node-file commit relationship diagrams
    - Clarified node start/end DB + Event control (NodeBoundary) is implemented
27. ~~Create LangGraph Audit & Event System documentation~~ ✓ DONE (2026-01-15)
    - `docs/LangGraph/AUDIT_EVENT_SYSTEM.md` - Streaming events, tracing, ACID
    - Updated `WTB_INTEGRATION.md` with `LangGraphEventBridge` design
    - Added audit integration architecture diagrams

### Completed (P0) - External API Layer (2026-01-15) ✓

28. ~~**Implement REST API (FastAPI)**~~ ✓ DONE (2026-01-15)
    - Workflow CRUD, execution control, audit queries
    - Pydantic schemas for request/response validation
29. ~~**Implement WebSocket handler**~~ ✓ DONE (2026-01-15)
    - Real-time event streaming
    - ConnectionManager with event bus bridge
30. ~~**Implement gRPC service definition**~~ ✓ DONE (2026-01-15)
    - `wtb_service.proto` with streaming RPCs
    - ExecutionControl, BatchTest, InteractiveSession services
31. ~~**Implement Workflow Submission SDK**~~ ✓ DONE (2026-01-15)
    - `WorkflowProject` configuration dataclass
    - `WTBTestBench` main interface
32. ~~**Create API unit and integration tests**~~ ✓ DONE (2026-01-15)
    - Pydantic model tests, SDK tests
    - REST endpoint integration tests

### In Progress (P0) - Observability & LangGraph (2026-01-15)

33. **Implement OpenTelemetry integration** ← **NEXT**
    - Configure OTLP exporters for traces/metrics/logs
    - Instrument FastAPI and gRPC with auto-instrumentation
    - Add custom spans for workflow execution
34. **Implement `LangGraphEventBridge`**
    - Bridge LangGraph `astream_events()` to WTB EventBus
    - Transform LangGraph events to WTB domain events
    - Handle event correlation (run_id → execution_id)
35. **Update `ExecutionController` with event bridging**
    - Add `run_async()` method with event streaming
    - Emit checkpoint audit events after execution
36. **Add LangGraph tracing configuration**
    - Configure LangSmith environment variables
    - Add OpenTelemetry integration option
37. **Implement `StreamModeConfig`**
    - Environment-specific stream mode selection
    - Production audit vs development debugging
38. **Add Prometheus metrics for LangGraph**
    - `MetricsEventListener` for execution metrics
    - Node duration histograms, checkpoint counters

### Completed (P0) - DDD Refactoring (2026-01-15) ✓

25. ~~**Create domain checkpoint models**~~ ✓ DONE
    - `Checkpoint` value object
    - `CheckpointId` value object  
    - `ExecutionHistory` aggregate root
26. ~~**Create `ICheckpointStore` interface**~~ ✓ DONE
    - Infrastructure interface for persistence only
    - No business logic in store
27. ~~**Update `NodeBoundary` model**~~ ✓ DONE
    - Remove `internal_session_id`, `tool_count`, `checkpoint_count`
    - Use `CheckpointId` (string) instead of `int`
28. ~~**Update checkpoint events**~~ ✓ DONE
    - Use `CheckpointId` value object
    - Remove `tool_track_position`
29. ~~**Implement `LangGraphCheckpointStore`**~~ ✓ DONE
    - Persistence only, maps domain ↔ LangGraph

### In Progress (P0) - Other

39. **Configure LangGraph checkpointers (SqliteSaver, PostgresSaver)**
40. **Implement Outbox verify handlers (FileTracker integration)**

### Completed (P1) - Actor Lifecycle + Venv Cache (2026-01-16) ✓

30. ~~**Implement `LangGraphEventBridge`**~~ ✓ DONE (2026-01-16)
    - Bridge LangGraph streaming events to WTB EventBus
    - Event transformation and correlation
31. ~~**Implement `ActorLifecycleManager`**~~ ✓ DONE (2026-01-16)
    - Hot/Warm/Cold pause strategies
    - Actor create, reset, pause, resume, fork, kill
    - 25 unit tests
32. ~~**Implement `VenvCacheManager`**~~ ✓ DONE (2026-01-16)
    - LRU eviction policy
    - Spec hash-based cache lookup
    - 18 unit tests

### Upcoming (P1)

33. **Add LangSmith/OpenTelemetry tracing configuration**
    - Production observability setup
34. **Implement `MetricsEventListener` for Prometheus**
    - LangGraph execution metrics
35. Implement `EvaluationEngine` for metrics collection
36. Implement `SessionLifecycleManager` for cleanup
37. Add Prometheus metrics export (general WTB metrics)
38. Configure PgBouncer for production
39. Deprecate `IStateAdapter` in favor of `ICheckpointStore` + domain logic

### Future (P2-P3)

40. ~~Implement `GrpcEnvironmentProvider` for existing env-manager~~ ✓ DONE
41. Add Ray E2E integration tests with real cluster ← **NEXT**
42. IDE sync WebSocket events
43. ⏸️ **AgentGitStateAdapter** (deferred - interface marked only)

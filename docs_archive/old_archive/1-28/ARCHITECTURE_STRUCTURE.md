# WTB Architecture Structure

**Last Updated:** 2026-01-28  
**Status:** Implemented

---

## 1. Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              WTB LAYER ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                           API LAYER (wtb/api/)                             │ │
│   │  REST routes, WebSocket handlers, gRPC protos                              │ │
│   │  Entry points for external consumers                                        │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                      APPLICATION LAYER (wtb/application/)                  │ │
│   │  ExecutionController, BatchTestRunner, NodeReplacer                        │ │
│   │  Orchestration, use cases, transaction boundaries                          │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                        DOMAIN LAYER (wtb/domain/)                          │ │
│   │  Models (Execution, Checkpoint, Workflow), Events, Interfaces              │ │
│   │  Business logic, domain rules, abstractions                                │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                   INFRASTRUCTURE LAYER (wtb/infrastructure/)               │ │
│   │  Adapters, Repositories, Event Bus, File Tracking, Outbox                  │ │
│   │  Concrete implementations, external system integration                     │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                        EXTERNAL SYSTEMS                                    │ │
│   │  SQLite/PostgreSQL, LangGraph, Ray, FileTracker                           │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

### 2.1 API Layer (`wtb/api/`)

```
wtb/api/
├── __init__.py
├── grpc/                    # gRPC definitions
│   ├── __init__.py         # gRPC exports
│   ├── servicer.py         # WTBServicer implementation (v2.1)
│   └── protos/
│       └── wtb_service.proto  # Protocol buffer definitions
├── rest/                    # REST API (FastAPI)
│   ├── app.py              # FastAPI application setup
│   ├── dependencies.py     # Dependency injection (v2.1: API services)
│   ├── models.py           # Pydantic request/response models
│   └── routes/
│       ├── batch.py        # Batch test endpoints
│       ├── checkpoint.py   # Checkpoint operations
│       ├── executions.py   # Execution lifecycle
│       ├── health.py       # Health checks
│       ├── variant.py      # Node variant management
│       └── workflow.py     # Workflow CRUD
└── websocket/
    └── handlers.py         # Real-time event streaming
```

**SOLID Compliance (v2.1):**
- SRP: Each route file handles one domain concern
- DIP: Routes depend on API service interfaces (IExecutionAPIService, etc.)
- ISP: Separate interfaces for Execution, Audit, BatchTest, Workflow operations

### 2.2 Application Layer (`wtb/application/`)

```
wtb/application/
├── __init__.py
├── factories.py                     # Service factory (DI container)
└── services/
    ├── actor_lifecycle.py           # Ray actor lifecycle management
    ├── api_services.py              # API service implementations (v2.1)
    ├── batch_test_runner.py         # Sequential batch runner
    ├── execution_controller.py      # Core execution orchestration
    ├── langgraph_node_replacer.py   # LangGraph-specific node swapping
    ├── node_replacer.py             # Generic node replacement logic
    ├── parity_checker.py            # Variant comparison/parity
    ├── project_service.py           # Project-level operations
    └── ray_batch_runner.py          # Ray parallel batch execution
```

**Key Services:**

| Service | Responsibility | SOLID |
|---------|---------------|-------|
| `ExecutionController` | Workflow lifecycle (run/pause/resume/stop/rollback) | SRP ✅ |
| `RayBatchRunner` | Parallel variant execution with Ray actors | SRP ✅ |
| `NodeReplacer` | A/B testing node substitution | OCP ✅ |
| `ParityChecker` | Variant result comparison | SRP ✅ |
| `ExecutionAPIService` | REST/gRPC execution operations (v2.1) | SRP, DIP ✅ |
| `AuditAPIService` | REST/gRPC audit operations (v2.1) | SRP, DIP ✅ |
| `BatchTestAPIService` | REST/gRPC batch test operations (v2.1) | SRP, DIP ✅ |
| `WorkflowAPIService` | REST/gRPC workflow CRUD (v2.1) | SRP, DIP ✅ |

### 2.3 Domain Layer (`wtb/domain/`)

```
wtb/domain/
├── __init__.py
├── events/                          # Domain events
│   ├── __init__.py                 # Event exports (70+ event types)
│   ├── checkpoint_events.py        # CheckpointCreated, Rollback, Branch
│   ├── environment_events.py       # Venv lifecycle events
│   ├── execution_events.py         # Execution lifecycle events
│   ├── file_processing_events.py   # File commit/restore events
│   ├── langgraph_events.py         # LangGraph audit events
│   ├── node_events.py              # Node execution events
│   ├── ray_events.py               # Ray batch/actor events
│   └── workspace_events.py         # Workspace isolation events
├── interfaces/                      # Abstractions (Ports)
│   ├── __init__.py                 # Interface exports
│   ├── api_services.py             # API service interfaces (v2.1)
│   ├── batch_runner.py             # IBatchTestRunner
│   ├── checkpoint_store.py         # ICheckpointStore (PRIMARY)
│   ├── evaluator.py                # IEvaluator, IEvaluationEngine
│   ├── execution_controller.py     # IExecutionController
│   ├── file_processing_repository.py # File processing repos
│   ├── file_tracking.py            # IFileTrackingService
│   ├── node_executor.py            # INodeExecutor
│   ├── node_replacer.py            # INodeReplacer, IVariantRegistry
│   ├── repositories.py             # Repository interfaces (13 repos)
│   ├── state_adapter.py            # IStateAdapter (DEPRECATED)
│   └── unit_of_work.py             # IUnitOfWork
└── models/                          # Domain entities and value objects
    ├── __init__.py                 # Model exports
    ├── batch_test.py               # BatchTest aggregate
    ├── checkpoint_file.py          # CheckpointFile link
    ├── checkpoint.py               # Checkpoint, ExecutionHistory
    ├── evaluation.py               # EvaluationResult
    ├── file_processing.py          # FileCommit, FileMemento, BlobId
    ├── integrity.py                # IntegrityReport, RepairAction
    ├── node_boundary.py            # NodeBoundary (entry/exit checkpoints)
    ├── outbox.py                   # OutboxEvent (cross-DB consistency)
    ├── workflow.py                 # TestWorkflow, Execution, ExecutionState
    └── workspace.py                # Workspace isolation models
```

**Domain Model Summary:**

| Aggregate | Key Entities | Purpose |
|-----------|-------------|---------|
| `TestWorkflow` | WorkflowNode, WorkflowEdge | Workflow definition |
| `Execution` | ExecutionState, ExecutionStatus | Runtime state |
| `Checkpoint` | CheckpointId, ExecutionHistory | Time-travel support |
| `BatchTest` | VariantCombination, BatchTestResult | A/B testing |
| `FileCommit` | FileMemento, BlobId | File versioning |
| `Workspace` | WorkspaceConfig, WorkspaceStrategy | Isolation |

### 2.4 Infrastructure Layer (`wtb/infrastructure/`)

```
wtb/infrastructure/
├── __init__.py
├── adapters/                        # State adapter implementations
│   ├── __init__.py
│   ├── inmemory_state_adapter.py   # In-memory (testing)
│   ├── langgraph_state_adapter.py  # LangGraph checkpointer (PRIMARY)
│   └── agentgit_state_adapter.py   # AgentGit (deprecated)
├── database/                        # Persistence
│   ├── __init__.py
│   ├── config.py                   # Database configuration
│   ├── factory.py                  # Connection factories
│   ├── file_processing_orm.py      # File processing tables
│   ├── inmemory_unit_of_work.py    # In-memory UoW (testing)
│   ├── models.py                   # SQLAlchemy ORM models
│   ├── setup.py                    # Schema initialization
│   ├── unit_of_work.py             # SQLAlchemy UoW (ACID)
│   ├── migrations/                 # SQL migrations
│   │   ├── 002_batch_tests.sql
│   │   └── 003_postgresql_production.sql
│   └── repositories/               # Repository implementations
│       ├── audit_repository.py
│       ├── base.py                 # Base repository pattern
│       ├── batch_test_repository.py
│       ├── checkpoint_file_repository.py
│       ├── evaluation_result_repository.py
│       ├── execution_repository.py
│       ├── file_processing_repository.py
│       ├── node_boundary_repository.py
│       ├── node_variant_repository.py
│       ├── outbox_repository.py    # Outbox Pattern
│       └── workflow_repository.py
├── environment/                     # Venv management integration
│   └── (7 files)
├── events/                          # Event bus
│   ├── __init__.py
│   └── wtb_event_bus.py            # Thread-safe pub/sub
├── file_tracking/                   # File state management
│   └── (5 files)
├── integrity/                       # Cross-database integrity
│   └── (2 files)
├── outbox/                          # Outbox Pattern processor
│   └── processor.py                # Background event processing
├── stores/                          # Checkpoint stores
│   └── (3 files)
└── workspace/                       # Workspace isolation
    └── (2 files)
```

### 2.5 SDK Layer (`wtb/sdk/`)

```
wtb/sdk/
├── __init__.py
├── test_bench.py           # High-level TestBench API
└── workflow_project.py     # WorkflowProject configuration
```

**SDK Usage Example:**
```python
from wtb.sdk import TestBench, WorkflowProject

project = WorkflowProject(
    name="my-workflow",
    db_path="./data/wtb.db",
    output_dir="./outputs",
)

bench = TestBench(project)
result = bench.run(graph, initial_state={"query": "hello"})
```

---

## 3. SOLID Principles Implementation

### 3.1 Single Responsibility Principle (SRP)

| Component | Responsibility | Violations |
|-----------|---------------|------------|
| `ExecutionController` | Workflow lifecycle orchestration | ✅ None |
| `LangGraphStateAdapter` | LangGraph ↔ WTB translation | ✅ None |
| `SQLAlchemyUnitOfWork` | Transaction boundaries | ✅ None |
| `WTBEventBus` | Event pub/sub | ✅ None |
| `OutboxProcessor` | Cross-DB sync processing | ✅ None |

### 3.2 Open/Closed Principle (OCP)

**Extension Points:**

```
IStateAdapter                     ICheckpointStore
├── InMemoryStateAdapter          ├── InMemoryCheckpointStore
├── LangGraphStateAdapter  ◄──    ├── LangGraphCheckpointStore  ◄── PRIMARY
└── (deprecated)AgentGit          └── SqliteCheckpointStore

IEvaluator                        INodeExecutor
├── AccuracyEvaluator            ├── DefaultNodeExecutor
├── LatencyEvaluator             ├── MockNodeExecutor
└── CustomEvaluator (plugin)     └── RemoteNodeExecutor
```

### 3.3 Liskov Substitution Principle (LSP)

All interface implementations are substitutable:
```python
# Any IStateAdapter works with ExecutionController
controller = ExecutionController(
    state_adapter=LangGraphStateAdapter(...),  # ✅
    # state_adapter=InMemoryStateAdapter(...),  # ✅ Also works
)
```

### 3.4 Interface Segregation Principle (ISP)

```
IRepository<T>
├── IReadRepository<T>      # get, list, find
└── IWriteRepository<T>     # add, update, delete

IExecutionController
├── IExecutionRunner        # run, pause, resume, stop
└── IExecutionInspector     # get_status, get_state

API Service Interfaces (v2.1)
├── IExecutionAPIService    # Execution lifecycle operations
├── IAuditAPIService        # Audit event queries
├── IBatchTestAPIService    # Batch test management
└── IWorkflowAPIService     # Workflow CRUD
```

### 3.5 Dependency Inversion Principle (DIP)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DEPENDENCY DIRECTION                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Application Layer                  Infrastructure Layer                │
│   ─────────────────                  ────────────────────                │
│                                                                          │
│   ExecutionController ─────────────► IStateAdapter (abstraction)        │
│           ▲                                  │                           │
│           │                                  ▼                           │
│           │                          LangGraphStateAdapter               │
│           │                          InMemoryStateAdapter                │
│                                                                          │
│   Both depend on abstractions, not concretions ✅                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. ACID Compliance

### 4.1 Transaction Boundaries (Unit of Work)

```python
# wtb/infrastructure/database/unit_of_work.py
class SQLAlchemyUnitOfWork(IUnitOfWork):
    """
    Manages transaction boundaries across multiple repositories.
    
    Usage:
        with SQLAlchemyUnitOfWork("sqlite:///wtb.db") as uow:
            workflow = uow.workflows.get(workflow_id)
            execution = Execution(workflow_id=workflow.id)
            uow.executions.add(execution)
            uow.commit()  # ATOMIC commit
    """
```

**Repositories Managed:**
- `workflows`, `executions`, `variants`
- `batch_tests`, `evaluation_results`
- `node_boundaries`, `checkpoint_files`
- `outbox`, `audit_logs`

### 4.2 Cross-Database Consistency (Outbox Pattern)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        OUTBOX PATTERN FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. Business Transaction                                                │
│   ────────────────────────                                               │
│   BEGIN TX                                                               │
│   ├── INSERT execution (wtb.db)                                          │
│   ├── INSERT outbox_event (wtb.db)   ◄── Same transaction               │
│   COMMIT TX                                                              │
│                                                                          │
│   2. Background Processor                                                │
│   ────────────────────────                                               │
│   OutboxProcessor.process_pending()                                      │
│   ├── Read PENDING events                                                │
│   ├── Verify checkpoint exists (LangGraph)                               │
│   ├── Verify file commit exists (FileTracker)                            │
│   ├── Mark PROCESSED or FAILED                                           │
│   └── Retry on failure (max 5)                                           │
│                                                                          │
│   Event Types:                                                           │
│   • CHECKPOINT_VERIFY                                                    │
│   • FILE_COMMIT_VERIFY                                                   │
│   • CHECKPOINT_FILE_LINK_VERIFY                                          │
│   • ROLLBACK_FILE_RESTORE                                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 LangGraph Checkpoint ACID

```python
# LangGraph provides atomic checkpoints per super-step
class LangGraphStateAdapter(IStateAdapter):
    """
    ACID Compliance:
    - Atomic: Super-step commits are atomic
    - Consistent: State schema validated via TypedDict
    - Isolated: Thread-based isolation (wtb-{execution_id})
    - Durable: Checkpoints persisted to SQLite/PostgreSQL
    """
```

---

## 5. Event System

### 5.1 Event Bus Architecture

```python
# wtb/infrastructure/events/wtb_event_bus.py
class WTBEventBus:
    """
    Thread-safe pub/sub with bounded history.
    
    Features:
    - RLock for nested publish safety
    - Bounded event history (default 1000)
    - Optional AgentGit bridge
    """
```

### 5.2 Event Categories

| Category | Events | Purpose |
|----------|--------|---------|
| **Execution** | Started, Paused, Resumed, Completed, Failed, Cancelled | Lifecycle |
| **Node** | Started, Completed, Failed, Skipped | Node execution |
| **Checkpoint** | Created, Rollback, Branch | Time-travel |
| **File** | Committed, Restored, Verified | File tracking |
| **Ray** | BatchStarted, ActorCreated, VariantCompleted | Parallelism |
| **Workspace** | Created, Activated, Forked, CleanedUp | Isolation |

---

## 6. File Tracking Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FILE TRACKING ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────┐      ┌──────────────────┐      ┌──────────────┐  │
│   │ ExecutionController│───►│ IFileTrackingService│───►│ FileCommit   │  │
│   └──────────────────┘      └──────────────────┘      │ FileMemento  │  │
│                                      │                 │ BlobId       │  │
│                                      │                 └──────────────┘  │
│                                      ▼                                   │
│                             ┌──────────────────┐                        │
│                             │ Content-Addressable│                       │
│                             │ Storage (SHA-256)  │                       │
│                             │ objects/{hash[:2]}/│                       │
│                             │         {hash[2:]} │                       │
│                             └──────────────────┘                        │
│                                                                          │
│   Features:                                                              │
│   • Automatic deduplication via SHA-256 hashing                         │
│   • Checkpoint-file linking for rollback                                │
│   • Blob storage with Git-like sharding                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Workspace Isolation (Parallel Execution)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WORKSPACE ISOLATION ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Base Workspace                                                         │
│   ┌────────────────────────────────────────┐                            │
│   │ ./base_workspace/                       │                            │
│   │   ├── inputs/                           │                            │
│   │   └── outputs/                          │                            │
│   └────────────────────────────────────────┘                            │
│                      │                                                   │
│                      │ Fork (copy-on-write)                             │
│                      ▼                                                   │
│   ┌─────────────────────┐    ┌─────────────────────┐                    │
│   │ Variant A Workspace │    │ Variant B Workspace │                    │
│   │ ./workspaces/var-a/ │    │ ./workspaces/var-b/ │                    │
│   │   ├── inputs/       │    │   ├── inputs/       │                    │
│   │   └── outputs/      │    │   └── outputs/      │                    │
│   └─────────────────────┘    └─────────────────────┘                    │
│            │                          │                                  │
│            │ Ray Actor 1              │ Ray Actor 2                     │
│            ▼                          ▼                                  │
│   Isolated file system           Isolated file system                   │
│   No race conditions ✅          No race conditions ✅                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Test Structure

```
tests/
├── test_api/                    # REST/gRPC/integration tests
│   ├── test_api_services_unit.py        # API service unit tests (v2.1)
│   ├── test_api_transaction_consistency.py  # ACID tests (v2.1)
│   ├── test_external_control.py
│   ├── test_rest_integration.py
│   └── test_rest_models.py
├── test_file_processing/        # File tracking tests
│   ├── integration/
│   └── unit/
├── test_langgraph/              # LangGraph integration
│   ├── integration/
│   └── unit/
├── test_outbox_transaction_consistency/  # ACID compliance tests
│   ├── test_batch_parallel.py
│   ├── test_branching_rollback.py
│   ├── test_cross_system_acid.py
│   └── test_pause_resume.py
├── test_sdk/                    # SDK tests
├── test_workspace/              # Workspace isolation tests
└── test_wtb/                    # Core WTB tests (47 files)
```

---

## 9. Dependencies

### Core Dependencies
- `langgraph` / `langgraph-checkpoint-sqlite` - Checkpoint persistence
- `sqlalchemy` - ORM and Unit of Work
- `ray` - Parallel execution (optional)
- `fastapi` - REST API
- `pydantic` - Data validation
- `grpcio` / `grpcio-tools` - gRPC support (v2.1)

### Python Version
- **Python 3.12** (Ray does not support 3.13 on Windows)

---

## 10. API Service Architecture (v2.1)

### 10.1 Interface-Based Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API SERVICE ARCHITECTURE (v2.1)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   REST Routes                    gRPC Servicer                              │
│   (FastAPI)                      (WTBServicer)                              │
│       │                              │                                      │
│       └──────────────┬───────────────┘                                      │
│                      │                                                      │
│                      ▼                                                      │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                    API Service Interfaces                             │ │
│   │  ┌─────────────────────┐  ┌─────────────────────┐                    │ │
│   │  │ IExecutionAPIService│  │ IAuditAPIService    │                    │ │
│   │  │ - list_executions() │  │ - query_events()    │                    │ │
│   │  │ - get_execution()   │  │ - get_summary()     │                    │ │
│   │  │ - pause_execution() │  │ - get_timeline()    │                    │ │
│   │  │ - resume_execution()│  └─────────────────────┘                    │ │
│   │  │ - stop_execution()  │                                              │ │
│   │  │ - rollback_exec()   │  ┌─────────────────────┐                    │ │
│   │  │ - inspect_state()   │  │ IBatchTestAPIService│                    │ │
│   │  │ - modify_state()    │  │ - create_batch()    │                    │ │
│   │  │ - list_checkpoints()│  │ - get_batch()       │                    │ │
│   │  │ - create_checkpoint │  │ - list_batches()    │                    │ │
│   │  └─────────────────────┘  └─────────────────────┘                    │ │
│   │                                                                       │ │
│   │  ┌─────────────────────┐                                              │ │
│   │  │ IWorkflowAPIService │                                              │ │
│   │  │ - create_workflow() │                                              │ │
│   │  │ - get_workflow()    │                                              │ │
│   │  │ - list_workflows()  │                                              │ │
│   │  │ - update_workflow() │                                              │ │
│   │  │ - delete_workflow() │                                              │ │
│   │  └─────────────────────┘                                              │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                      │                                                      │
│                      ▼                                                      │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                    Concrete Implementations                           │ │
│   │  ExecutionAPIService, AuditAPIService, BatchTestAPIService,          │ │
│   │  WorkflowAPIService                                                   │ │
│   │                                                                       │ │
│   │  Dependencies:                                                        │ │
│   │  ├── IUnitOfWork (transaction boundaries)                            │ │
│   │  ├── IExecutionController (domain operations)                        │ │
│   │  ├── IBatchTestRunner (batch execution)                              │ │
│   │  └── OutboxRepository (event ordering)                               │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Transaction Flow

```python
# Example: Pause Execution with ACID Compliance
async def pause_execution(self, execution_id: str, reason: str) -> ControlResultDTO:
    """
    1. Validate execution exists (Consistency)
    2. Pause via ExecutionController (Atomicity)
    3. Create outbox event (Durability)
    4. Return DTO (Isolation via per-request UoW)
    """
    try:
        execution = await self._controller.pause(execution_id)
        # Outbox event created within same transaction
        return ControlResultDTO(success=True, status=execution.status.value)
    except ValueError as e:
        return ControlResultDTO(success=False, error=str(e))
```

### 10.3 Outbox Event Types (v2.1)

| Event Type | Description |
|------------|-------------|
| `EXECUTION_PAUSED` | Execution paused by user |
| `EXECUTION_RESUMED` | Execution resumed |
| `EXECUTION_STOPPED` | Execution stopped/cancelled |
| `EXECUTION_FORKED` | Execution branched |
| `EXECUTION_STATE_MODIFIED` | State manually modified |
| `CHECKPOINT_CREATED_MANUAL` | Manual checkpoint created |
| `CHECKPOINT_CREATED_AUTO` | Auto checkpoint (node boundary) |
| `CHECKPOINT_CREATED_BREAKPOINT` | Breakpoint checkpoint |
| `ROLLBACK_INITIATED` | Rollback started |
| `ROLLBACK_COMPLETED` | Rollback finished |
| `BATCH_TEST_CREATED` | Batch test started |
| `BATCH_TEST_COMPLETED` | Batch test finished |
| `WORKFLOW_CREATED` | Workflow registered |
| `WORKFLOW_UPDATED` | Workflow modified |
| `WORKFLOW_DELETED` | Workflow removed |

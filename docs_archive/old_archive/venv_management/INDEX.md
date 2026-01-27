# UV Venv Manager - Architecture Documentation

**Last Updated:** 2026-01-15
**Status:** Refactored & Production Ready
**Version:** 0.2.0

---

## Architecture Decision

### Core Principle: Environment Provisioning ONLY

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    UV VENV MANAGER SCOPE                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✅ WHAT IT DOES:                                                          │
│  • Create virtual environments with UV                                      │
│  • Manage dependencies (add, update, remove packages)                       │
│  • Sync environments from lock files                                        │
│  • Export environment configurations                                        │
│  • Cleanup stale environments                                               │
│  • Audit all operations                                                     │
│                                                                             │
│  ❌ WHAT IT DOES NOT DO:                                                   │
│  • Execute code (REMOVED - RunCode is gone)                                │
│  • Ray integration (handled by WTB)                                         │
│  • Node execution orchestration                                             │
│                                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│  KEY INSIGHT:                                                               │
│  A node is a COMPLETE PROJECT (e.g., RAG pipeline with multiple files,    │
│  threads, GPU resources), NOT a code snippet to run via RunCode.           │
│                                                                             │
│  Execution is Ray's responsibility in WTB, not UV Venv Manager's.          │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture

### Integration Pattern: gRPC Service (Like FileTracker)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICE PATTERN                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FileTracker Pattern (Existing):                                             │
│  ═════════════════════════════                                               │
│  WTB → IFileTrackingService → FileTrackerService → gRPC → FileTracker       │
│                                                                              │
│  UV Venv Manager Pattern (Same):                                             │
│  ══════════════════════════════                                              │
│  WTB → IEnvironmentProvider → GrpcEnvironmentProvider → gRPC → UV Service   │
│                                                                              │
│  Benefits:                                                                   │
│  • Consistent integration pattern                                            │
│  • Independent scaling                                                       │
│  • Clear service boundaries                                                  │
│  • Audit isolation                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              WTB Core                                      │
│                                                                            │
│  RayBatchTestRunner                                                        │
│         │                                                                  │
│         ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │        IEnvironmentProvider (Environment PROVISIONING Only)          │  │
│  │                                                                      │  │
│  │  • create_environment(variant_id, config) → env_path, python_path   │  │
│  │  • get_runtime_env(variant_id) → venv_path, env_vars                │  │
│  │  • cleanup_environment(variant_id)                                  │  │
│  │                                                                      │  │
│  │  ⚠️ NO execute_in_env() - Execution is Ray's responsibility         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         │                                                                  │
│         ▼                                                                  │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │              GrpcEnvironmentProvider                                │   │
│  │              ════════════════════════                               │   │
│  │  • Calls UV Venv Manager Service via gRPC                          │   │
│  │  • Returns: env_path, python_path, venv_path                       │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                               │                                            │
└───────────────────────────────┼────────────────────────────────────────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
┌───────────────────────────┐   ┌─────────────────────────────────────────┐
│                           │   │                                         │
│  UV Venv Manager Service  │   │  Ray Cluster                            │
│  (Environment Provisioner)│   │  (Node Execution Engine)                │
│  ═════════════════════════│   │  ════════════════════════               │
│                           │   │                                         │
│  gRPC Server              │   │  VariantExecutionActor                  │
│  ├── CreateEnv            │   │  ┌───────────────────────────────────┐  │
│  ├── GetEnvStatus         │   │  │ Node Project (e.g., RAG Pipeline) │  │
│  ├── SyncEnv              │   │  │                                   │  │
│  ├── AddDeps              │   │  │ • Multi-file project              │  │
│  ├── ExportEnv            │   │  │ • GPU/CPU resources               │  │
│  ├── DeleteEnv            │   │  │ • Multi-threading                 │  │
│  └── Cleanup              │   │  │ • Database connections            │  │
│                           │   │  │ • LLM API calls                   │  │
│  Storage:                 │   │  │                                   │  │
│  envs/{wf}_{node}_{ver}/  │   │  │ Executed via python_path:         │  │
│  ├── pyproject.toml       │◄──┼──┤ subprocess.run([python_path,      │  │
│  ├── uv.lock              │   │  │   "-m", "node_project.main"])     │  │
│  ├── .venv/               │   │  └───────────────────────────────────┘  │
│  └── metadata.json        │   │                                         │
│                           │   │                                         │
└───────────────────────────┘   └─────────────────────────────────────────┘
```

---

## SOLID Compliance

| Principle | Implementation |
|-----------|----------------|
| **SRP** | EnvManager handles lifecycle only; UVExecutor handles CLI only; MetadataRepository handles persistence only |
| **OCP** | New event publishers can be added without modifying existing code |
| **LSP** | All environment providers implement IEnvironmentProvider consistently |
| **ISP** | Focused interfaces: IVenvExecutor, IMetadataRepository, IEnvironmentEventPublisher |
| **DIP** | High-level modules depend on abstractions, not concrete implementations |

---

## ACID Compliance

| Property | Implementation |
|----------|----------------|
| **Atomicity** | Environment creation uses rollback on failure; metadata written atomically (temp file + rename) |
| **Consistency** | Metadata status updated only after successful operations; CREATING → ACTIVE transition |
| **Isolation** | AsyncIO Lock per env_id prevents concurrent modifications |
| **Durability** | UV handles lockfile integrity; metadata persisted with fsync |

---

## gRPC Service API

| RPC Method | Purpose | Notes |
|------------|---------|-------|
| `CreateEnv` | Provision environment with dependencies | Returns env_path, python_path |
| `GetEnvStatus` | Check if environment is ready | Returns status, has_venv |
| `SyncEnv` | Sync dependencies with lock file | Rebuilds .venv |
| `AddDeps` | Add packages to environment | Uses `uv add` |
| `UpdateDeps` | Upgrade packages | Uses `uv add --upgrade` |
| `RemoveDeps` | Remove packages | Uses `uv remove` |
| `ListDeps` | List installed packages | Reads pyproject.toml |
| `ExportEnv` | Export pyproject.toml + uv.lock | For reproducibility |
| `DeleteEnv` | Delete environment | Cleans up files |
| `Cleanup` | Batch cleanup stale environments | TTL-based |

---

## Domain Events

| Event | Published When |
|-------|----------------|
| `EnvironmentCreationStartedEvent` | Creation begins |
| `EnvironmentCreatedEvent` | Creation succeeds |
| `EnvironmentCreationFailedEvent` | Creation fails (rollback performed) |
| `EnvironmentDeletedEvent` | Environment deleted |
| `DependenciesAddedEvent` | Packages added |
| `DependenciesUpdatedEvent` | Packages upgraded |
| `DependenciesRemovedEvent` | Packages removed |
| `DependencyOperationFailedEvent` | Dependency operation fails |
| `EnvironmentSyncedEvent` | Sync succeeds |
| `EnvironmentSyncFailedEvent` | Sync fails |
| `EnvironmentCleanupCompletedEvent` | Cleanup completes |

---

## Project Structure

```
uv_venv_manager/
├── src/
│   ├── domain/                    # Domain layer (SOLID interfaces & value objects)
│   │   ├── interfaces.py          # IVenvExecutor, IMetadataRepository, IEnvironmentEventPublisher
│   │   ├── exceptions.py          # Domain exceptions (no HTTP coupling)
│   │   └── value_objects.py       # EnvId, EnvStatus, EnvMetadata, VenvResult
│   │
│   ├── infrastructure/            # Infrastructure implementations
│   │   ├── metadata_repository.py # JsonFileMetadataRepository
│   │   └── event_publisher.py     # WTBEventBridgePublisher, NoOpEventPublisher
│   │
│   ├── services/                  # Application services
│   │   ├── env_manager.py         # EnvManager (lifecycle orchestration)
│   │   ├── uv_executor.py         # UVCommandExecutor (UV CLI wrapper)
│   │   ├── dep_manager.py         # DependencyManager
│   │   ├── lock_manager.py        # AsyncIO lock management
│   │   └── project_info.py        # Package name mapping
│   │
│   ├── db_service/                # Audit database
│   │   ├── connection.py          # PostgreSQL connection
│   │   ├── env_audit.py           # EnvAudit operations
│   │   ├── env_repository.py      # Repository pattern
│   │   └── models.py              # ORM models
│   │
│   ├── integrations/              # External integrations
│   │   └── client.py              # HTTP client for API
│   │
│   ├── grpc_generated/            # Generated gRPC code
│   ├── protos/                    # Proto definitions
│   ├── api.py                     # FastAPI application
│   ├── grpc_servicer.py           # gRPC service implementation
│   └── models.py                  # Pydantic request/response models
│
├── tests/                         # Test directory
└── docs/                          # Service documentation
```

---

## Usage Examples

### From WTB (via GrpcEnvironmentProvider)

```python
from wtb.infrastructure.environment.providers import GrpcEnvironmentProvider

# Create provider
provider = GrpcEnvironmentProvider("localhost:50051")

# Provision environment
env_info = provider.create_environment("variant-1", {
    "workflow_id": "ml_pipeline",
    "node_id": "rag",
    "packages": ["langchain", "chromadb"],
    "python_version": "3.11",
})

# Get python_path for Ray execution
python_path = env_info["python_path"]  # /path/to/.venv/bin/python

# Ray executes the node project using this python_path
# subprocess.run([python_path, "-m", "node_project.main"])
```

### Direct HTTP Client

```python
from uv_venv_manager.src.integrations.client import EnvFabricClient

client = EnvFabricClient("http://localhost:8000")

# Ensure environment exists
python_path = client.ensure_env(
    "workflow-1", "node-a",
    packages=["numpy", "pandas"]
)

# python_path can be used with Ray runtime_env
```

---

## Removed Features (2026-01-15)

| Feature | Reason | Alternative |
|---------|--------|-------------|
| `RunCode` RPC | Nodes are complete projects, not code snippets | Ray executes node projects via subprocess |
| Ray integration in UV Venv Manager | Ray belongs in WTB | Use GrpcEnvironmentProvider in WTB |
| `RayEnvExecutor` class | Duplicate functionality | Use WTB's RayBatchTestRunner |

---

## Related Documentation

| Document | Location | Description |
|----------|----------|-------------|
| Progress Tracker | `docs/Project_Init/PROGRESS_TRACKER.md` | Implementation status |
| Architecture | `docs/Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md` | Main architecture doc |
| Ray Integration | `docs/Ray/` | Ray batch runner design |
| LangGraph Integration | `docs/LangGraph/WTB_INTEGRATION.md` | LangGraph checkpoint integration |

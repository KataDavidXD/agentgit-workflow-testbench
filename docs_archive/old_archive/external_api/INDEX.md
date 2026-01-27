# External API & Observability Documentation

**Last Updated:** 2026-01-15

## Overview

This folder contains design documents for the WTB external API layer and observability infrastructure.

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| REST API (FastAPI) | ✅ Implemented | `wtb/api/rest/` |
| WebSocket Handler | ✅ Implemented | `wtb/api/websocket/` |
| gRPC Proto Definition | ✅ Implemented | `wtb/api/grpc/protos/` |
| SDK (WorkflowProject, WTBTestBench) | ✅ Implemented | `wtb/sdk/` |
| Unit Tests (REST Models) | ✅ Implemented | `tests/test_api/test_rest_models.py` |
| Unit Tests (SDK) | ✅ Implemented | `tests/test_api/test_sdk.py` |
| Unit Tests (External Control) | ✅ Implemented | `tests/test_api/test_external_control.py` |
| Integration Tests (REST) | ✅ Implemented | `tests/test_api/test_rest_integration.py` |
| Integration Tests (External Control) | ✅ Implemented | `tests/test_api/test_external_control_integration.py` |
| Integration Tests (Workflow Submission) | ✅ Implemented | `tests/test_api/test_workflow_submission_integration.py` |
| RAG Pipeline Example | ✅ Implemented | `examples/rag_pipeline_workflow.py` |
| OpenTelemetry Integration | 🔄 Pending | - |

## Documents

| Document | Purpose | Status |
|----------|---------|--------|
| [EXTERNAL_API_AND_OBSERVABILITY_DESIGN.md](./EXTERNAL_API_AND_OBSERVABILITY_DESIGN.md) | Complete API & observability architecture | ✅ APPROVED |
| [WORKFLOW_SUBMISSION_DESIGN.md](./WORKFLOW_SUBMISSION_DESIGN.md) | How users submit LangGraph workflows to WTB | ✅ APPROVED |

## Quick Reference

### API Protocols

| Protocol | Port | Use Case |
|----------|------|----------|
| **REST** (FastAPI) | 8000 | Web UI, external clients, CRUD |
| **gRPC** | 50051 | Internal services, streaming, Ray workers |
| **WebSocket** | 8000/ws | Real-time UI updates |

### Observability Stack

```
WTB Application
    │
    ├─► OpenTelemetry SDK
    │       │
    │       ├─► Traces → Jaeger/Tempo
    │       ├─► Metrics → Prometheus
    │       └─► Logs → Loki
    │
    └─► Grafana Dashboards
```

### Workflow Submission Model

```
User Code                           WTB System
═════════                           ══════════
WorkflowProject                     
├── graph_factory       ─────────►  WorkflowRegistry
├── variants                        ├── Node Variants
│   ├── node-level      ─────────►  │   └── A/B Testing
│   └── workflow-level  ─────────►  └── Workflow Variants
├── file_tracking       ─────────►  FileTracker Integration
├── environment         ─────────►  UV Venv Manager
│   ├── workflow-level              ├── Per-Workflow Env
│   ├── node-level                  ├── Per-Node Env
│   └── variant-level               └── Per-Variant Env
└── execution           ─────────►  Ray Batch Runner
    └── node_resources              └── Per-Node Resources
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| External Control | REST + gRPC + WebSocket | REST for simplicity; gRPC for performance |
| Observability | OpenTelemetry → Prometheus → Grafana | Vendor-neutral, industry standard |
| Audit Exposure | REST API + gRPC Stream + Prometheus | Query, subscribe, aggregate |
| Transaction Safety | Outbox Pattern + Event Sourcing | ACID compliance |
| Workflow Submission | SDK Registration | Native Python, type-safe, IDE support |
| Variant Granularity | Workflow + Node | Architecture comparison + component A/B testing |
| Environment Granularity | Workflow + Node + Variant | Flexible dependency isolation |
| Ray Resources | Node-level allocation | Fine-grained resource control |
| Default Executor | Ray | Better CPU/process/thread management |

## Code Structure

```
wtb/
├── api/
│   ├── __init__.py          # API layer entry point
│   ├── rest/
│   │   ├── __init__.py
│   │   ├── app.py           # FastAPI application factory
│   │   ├── models.py        # Pydantic request/response schemas
│   │   ├── dependencies.py  # FastAPI dependency injection
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── workflows.py    # Workflow CRUD + batch test
│   │       ├── executions.py   # Execution control
│   │       ├── audit.py        # Audit trail access
│   │       ├── batch_tests.py  # Batch test management
│   │       └── health.py       # Health checks
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── handlers.py      # ConnectionManager + event bridge
│   └── grpc/
│       ├── __init__.py
│       └── protos/
│           └── wtb_service.proto  # gRPC service definition
├── sdk/
│   ├── __init__.py
│   ├── workflow_project.py  # WorkflowProject configuration
│   └── test_bench.py        # WTBTestBench main interface
```

## Quick Start

### REST API
```python
from wtb.api.rest.app import create_app, run_server

# Create and run the server
run_server(host="0.0.0.0", port=8000)
```

### SDK Usage
```python
from wtb.sdk import WorkflowProject, WTBTestBench

# Create project
project = WorkflowProject(
    name="my_workflow",
    graph_factory=create_my_graph,
)

# Register variants
project.register_variant("retriever", "bm25", bm25_impl)

# Run tests
wtb = WTBTestBench()
wtb.register_project(project)

result = wtb.run(
    project="my_workflow",
    initial_state={"query": "test"},
    variant_config={"retriever": "bm25"},
)
```

## Complex Example: RAG Pipeline

See `examples/rag_pipeline_workflow.py` for a complete example demonstrating:

### Features Demonstrated

| Feature | Description |
|---------|-------------|
| **Complex Multi-Node Workflow** | Query expansion → Retrieval → Reranking → Generation |
| **Node Version Control** | Register and swap node implementations at runtime |
| **Node-Level Variants** | `bm25_retriever`, `gpt4_generator` for A/B testing |
| **Workflow-Level Variants** | `simple_rag_architecture` for architecture comparison |
| **Node-Level Environments** | Different dependencies per node (faiss, transformers, openai) |
| **Node-Level Resources** | Different CPU/GPU/memory allocation per node |
| **Batch Testing with Variant Matrix** | Parallel comparison of multiple configurations |

### Example Workflow Structure

```
                    ┌──────────────────┐
                    │  query_expander  │  ← EnvSpec(spacy)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │    retriever     │  ← EnvSpec(faiss, sentence-transformers)
                    │                  │
                    │  Variants:       │
                    │  ├─ default      │
                    │  └─ bm25_retriever (rank-bm25)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │     reranker     │  ← EnvSpec(transformers)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │    generator     │  ← EnvSpec(openai, tiktoken)
                    │                  │
                    │  Variants:       │    NodeResourceConfig(num_gpus=0.5)
                    │  ├─ default      │
                    │  └─ gpt4_generator (anthropic)
                    └──────────────────┘
```

### Quick Example Usage

```python
from examples.rag_pipeline_workflow import project
from wtb.sdk import WTBTestBench

# Register and run
wtb = WTBTestBench()
wtb.register_project(project)

# Single execution with variant
result = await wtb.run_async(
    project="complex_rag_pipeline",
    initial_state={"query": "What is LangGraph?"},
    variant_config={"retriever": "bm25_retriever"},
)

# Batch test with variant matrix
batch_result = await wtb.run_batch_test_async(
    project="complex_rag_pipeline",
    variant_matrix=[
        {"retriever": "default", "generator": "default"},
        {"retriever": "bm25_retriever", "generator": "default"},
        {"_workflow": "simple_rag_architecture"},
    ],
    test_cases=[{"query": "Query 1"}, {"query": "Query 2"}],
)
```

## Test Coverage

### Unit Tests

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_rest_models.py` | 40+ | Pydantic model validation |
| `test_sdk.py` | 25+ | WorkflowProject, WTBTestBench |
| `test_external_control.py` | 15+ | ExecutionService, AuditService |

### Integration Tests

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_rest_integration.py` | 20+ | REST endpoints with TestClient |
| `test_external_control_integration.py` | 10+ | Execution control endpoints |
| `test_workflow_submission_integration.py` | 10+ | SDK + WorkflowProject |

### Key Test Scenarios

| Scenario | Description |
|----------|-------------|
| **Default Workflow Execution** | Run workflow with no variants |
| **Node-Level Variant Execution** | Run with `bm25_retriever` variant |
| **Workflow-Level Variant Execution** | Run with `simple_rag_architecture` |
| **Batch Test with Variant Matrix** | Parallel comparison of 4 configurations |
| **Pause/Resume/Rollback** | Execution control operations |
| **State Inspection/Modification** | Get/modify execution state |
| **Audit Trail Querying** | Filter audit events by execution_id, event_type |

## Related Documentation

- [WORKFLOW_TEST_BENCH_ARCHITECTURE.md](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) - Core architecture
- [WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) - Event bus design
- [DATABASE_DESIGN.md](../Project_Init/DATABASE_DESIGN.md) - Database schema
- [examples/rag_pipeline_workflow.py](../../examples/rag_pipeline_workflow.py) - Complete RAG example
# WTB Quick Start Guide

> Workflow Test Bench (WTB) - SDK for testing LangGraph workflows

---

## 🚀 Installation

```powershell
# Install with test dependencies (recommended)
uv sync --extra test

# Or install all dependencies
uv sync --extra all
```

---

## 📋 Running Tests

### Quick Test Run
```powershell
cd D:\12-22
uv run pytest -v
```

### Test Coverage Summary
| Category | Count |
|----------|-------|
| **Total Tests** | 1845 |
| **Passed** | 1845 ✅ |
| **Skipped** | 0 |
| **Warnings** | 11 |

---

## 🔧 Configuration

Test environment variables are auto-configured via `pyproject.toml`:

```toml
[tool.pytest_env]
RAY_E2E_TESTS = "1"
RAY_INTEGRATION_TESTS = "1"
```

---

## 🧪 Basic SDK Usage

### 1. Create a Workflow Project

```python
from wtb.sdk import WorkflowProject, WTBTestBench
from langgraph.graph import StateGraph, START, END

# Define your LangGraph workflow
def create_my_graph():
    graph = StateGraph(dict)
    graph.add_node("process", lambda state: {"result": "done"})
    graph.add_edge(START, "process")
    graph.add_edge("process", END)
    return graph.compile()

# Create project
project = WorkflowProject(
    name="my_workflow",
    graph_factory=create_my_graph,
    description="My first WTB workflow",
)
```

### 2. Register and Run

```python
# Create test bench (in-memory for testing)
wtb = WTBTestBench.create(mode="testing")

# Register project
wtb.register_project(project)

# Run execution
result = wtb.run(
    project="my_workflow",
    initial_state={"input": "hello"},
)

print(f"Status: {result.status}")  # ExecutionStatus.COMPLETED
print(f"State: {result.state}")
```

### 3. Register Node Variants (A/B Testing)

```python
# Alternative implementation
def fast_process(state):
    return {"result": "fast_done"}

# Register variant
project.register_variant(
    node="process",
    name="fast",
    implementation=fast_process,
    description="Optimized processor",
)

# Run with variant
result = wtb.run(
    project="my_workflow",
    initial_state={"input": "test"},
    variant_config={"process": "fast"},
)
```

### 4. Batch Testing

```python
# Run batch tests with variant matrix
batch_result = wtb.run_batch_test(
    project="my_workflow",
    variant_matrix=[
        {"process": "default"},
        {"process": "fast"},
    ],
    test_cases=[
        {"input": "test1"},
        {"input": "test2"},
    ],
)

print(f"Results: {len(batch_result.results)} variants tested")
```

---

## 🌐 With UV Venv Manager (gRPC)

### Start the Environment Service

```powershell
# Terminal 1: Start UV Venv Manager
cd D:\12-22\uv_venv_manager
uv run uvicorn src.api:create_app --host localhost --port 10900 --factory
```

Services:
- **REST API**: `http://localhost:10900`
- **gRPC**: `localhost:50051`

### Run gRPC Integration Tests

```powershell
# Terminal 2: Run tests
cd D:\12-22
uv run pytest tests/test_wtb/test_grpc_environment_provider_integration.py -v
```

---

## 📦 Dependency Groups

| Group | Command | Description |
|-------|---------|-------------|
| `test` | `uv sync --extra test` | Full testing (Ray, gRPC, OpenAI, FastAPI) |
| `ray` | `uv sync --extra ray` | Ray batch runner only |
| `api` | `uv sync --extra api` | REST API dependencies |
| `grpc` | `uv sync --extra grpc` | gRPC dependencies |
| `all` | `uv sync --extra all` | Everything |

---

## 🏗️ Project Structure

```
D:\12-22\
├── wtb/                    # Main SDK
│   ├── sdk/               # User-facing API
│   │   ├── test_bench.py  # WTBTestBench
│   │   └── workflow_project.py  # WorkflowProject
│   ├── domain/            # Domain models
│   ├── application/       # Services & factories
│   └── infrastructure/    # Adapters & repositories
├── tests/                  # Test suite (1845 tests)
├── uv_venv_manager/       # Environment provisioning service
└── docs/                  # Documentation
```

---

## 🔍 Troubleshooting

### Port 50051 in use
```powershell
# Find and kill the process
netstat -ano | findstr 50051
taskkill /PID <PID> /F
```

### Ray not initialized
```powershell
# Set environment variables
$env:RAY_E2E_TESTS="1"
$env:RAY_INTEGRATION_TESTS="1"
```

### Missing dependencies
```powershell
# Reinstall with test extras
uv sync --extra test --reinstall
```

---

## 📚 More Documentation

- [Architecture](docs/Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md)
- [Progress Tracker](docs/Project_Init/PROGRESS_TRACKER.md)
- [Workflow Submission Design](docs/external_api/WORKFLOW_SUBMISSION_DESIGN.md)

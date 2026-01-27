# WTB gRPC Client for UV Venv Manager

**Last Updated:** 2026-01-15  
**Status:** CLEANED UP - gRPC Client Only

## Architecture Decision

This directory contains **ONLY** the gRPC client stubs for communicating with the UV Venv Manager service.

**The actual service implementation lives in `uv_venv_manager/` project.**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURE OVERVIEW                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  WTB (This Directory)              UV Venv Manager Service                       │
│  ════════════════════              ═══════════════════════                       │
│  gRPC CLIENT only                  Standalone gRPC + REST service                │
│                                                                                  │
│  grpc_generated/                   uv_venv_manager/src/                          │
│  ├── env_manager_pb2.py            ├── api.py (FastAPI)                         │
│  ├── env_manager_pb2_grpc.py       ├── grpc_servicer.py                         │
│  └── env_manager_pb2.pyi           ├── services/                                │
│                                    │   ├── env_manager.py                       │
│                                    │   ├── uv_executor.py                       │
│                                    │   └── ...                                  │
│                                    └── db_service/ (audit)                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```text
wtb/infrastructure/environment/uv_manager/
├── __init__.py                 # Module exports
├── grpc_generated/             # Generated gRPC client stubs
│   ├── __init__.py
│   ├── env_manager_pb2.py      # Protocol buffer messages
│   ├── env_manager_pb2_grpc.py # gRPC service stubs
│   └── env_manager_pb2.pyi     # Type hints
└── README.md                   # This file
```

## Usage

### Option 1: High-Level Provider (Recommended)

```python
from wtb.infrastructure.environment.providers import GrpcEnvironmentProvider

# Create provider
provider = GrpcEnvironmentProvider("localhost:50051")

# Provision environment
env = provider.create_environment("variant-1", {
    "workflow_id": "ml_pipeline",
    "node_id": "rag",
    "packages": ["langchain", "chromadb"],
})

# Get runtime env for Ray
runtime_env = provider.get_runtime_env("variant-1")
# Returns: {"python_path": "/path/to/.venv/bin/python", ...}
```

### Option 2: Direct gRPC Client

```python
import grpc
from wtb.infrastructure.environment.uv_manager.grpc_generated import (
    env_manager_pb2 as pb2,
    env_manager_pb2_grpc as pb2_grpc,
)

channel = grpc.insecure_channel("localhost:50051")
stub = pb2_grpc.EnvManagerServiceStub(channel)

# Create environment
request = pb2.CreateEnvRequest(
    workflow_id="ml_pipeline",
    node_id="rag",
    packages=["langchain", "chromadb"],
)
response = stub.CreateEnv(request)
```

## Running the Service

The UV Venv Manager service must be running for gRPC calls to work:

```bash
# From uv_venv_manager directory
cd uv_venv_manager
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up -d
```

## Related Documentation

| Document | Location |
|----------|----------|
| Service Implementation | `uv_venv_manager/README.md` |
| Architecture Design | `docs/venv_management/INDEX.md` |
| Integration Points | `docs/venv_management/INTEGRATION_POINTS.md` |
| Provider Implementation | `wtb/infrastructure/environment/providers.py` |

## Proto File

The gRPC stubs are generated from `uv_venv_manager/src/protos/env_manager.proto`.

To regenerate:

```bash
cd uv_venv_manager
python -m grpc_tools.protoc \
    -I src/protos \
    --python_out=src/grpc_generated \
    --grpc_python_out=src/grpc_generated \
    --pyi_out=src/grpc_generated \
    src/protos/env_manager.proto
```

Then copy to WTB:

```bash
cp uv_venv_manager/src/grpc_generated/* wtb/infrastructure/environment/uv_manager/grpc_generated/
```

"""
WTB gRPC Client for UV Venv Manager Service.

This module contains ONLY the gRPC client stubs for communicating with
the UV Venv Manager service. The actual service implementation lives in
the `uv_venv_manager` project.

ARCHITECTURE DECISION (2026-01-15):
- UV Venv Manager = ENVIRONMENT PROVISIONING ONLY (standalone gRPC service)
- WTB = gRPC CLIENT (this module)
- Ray = NODE EXECUTION (using provisioned python_path)

Usage:
    from wtb.infrastructure.environment.uv_manager.grpc_generated import (
        env_manager_pb2 as pb2,
        env_manager_pb2_grpc as pb2_grpc,
    )
    
    channel = grpc.insecure_channel("localhost:50051")
    stub = pb2_grpc.EnvManagerServiceStub(channel)
    
    # Or use the high-level provider:
    from wtb.infrastructure.environment.providers import GrpcEnvironmentProvider
    provider = GrpcEnvironmentProvider("localhost:50051")

See Also:
    - wtb/infrastructure/environment/providers.py - GrpcEnvironmentProvider
    - uv_venv_manager/src/ - The actual service implementation
    - docs/venv_management/INDEX.md - Architecture documentation
"""

from wtb.infrastructure.environment.uv_manager.grpc_generated import (
    env_manager_pb2,
    env_manager_pb2_grpc,
)

__all__ = [
    "env_manager_pb2",
    "env_manager_pb2_grpc",
]
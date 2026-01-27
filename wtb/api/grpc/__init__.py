"""
gRPC API for internal services and high-throughput communication.

Provides:
- Execution control (start, pause, resume, stop, rollback)
- Event streaming (execution events, audit events)
- Batch test management with progress streaming
- Interactive debugging session (bidirectional)

Port: 50051 (default)

Usage:
    from wtb.api.grpc import create_grpc_server, WTBServicer
    
    servicer = WTBServicer(...)
    server = create_grpc_server(servicer, port=50051)
    server.start()
"""

# gRPC components will be available after proto compilation
# Run: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. wtb_service.proto

__all__ = []

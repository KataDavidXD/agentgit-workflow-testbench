from __future__ import annotations

from dataclasses import dataclass


class ServiceError(Exception):
    def __init__(self, http_status: int, code: str, message: str):
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class InvalidPackages(ServiceError):
    def __init__(self, message: str = "The format of packages is invalid"):
        super().__init__(http_status=400, code="INVALID_PACKAGES", message=message)


class EnvNotFound(ServiceError):
    def __init__(self, message: str = "Environment not found"):
        super().__init__(http_status=404, code="ENV_NOT_FOUND", message=message)


class EnvAlreadyExists(ServiceError):
    def __init__(self, message: str = "Environment already exists"):
        super().__init__(http_status=409, code="ENV_ALREADY_EXISTS", message=message)


class PackageResolutionFailed(ServiceError):
    def __init__(self, message: str = "Dependency resolution failed"):
        super().__init__(http_status=422, code="PACKAGE_RESOLUTION_FAILED", message=message)


class EnvLocked(ServiceError):
    def __init__(self, message: str = "Environment is locked by another operation"):
        super().__init__(http_status=423, code="ENV_LOCKED", message=message)


class UVExecutionError(ServiceError):
    def __init__(self, message: str = "UV command execution failed"):
        super().__init__(http_status=500, code="UV_EXECUTION_ERROR", message=message)


class DBAuditError(ServiceError):
    def __init__(self, message: str = "Database auditing failed"):
        super().__init__(http_status=500, code="DB_AUDIT_ERROR", message=message)


class ExecutionTimeout(ServiceError):
    def __init__(self, message: str = "Code execution timed out"):
        super().__init__(http_status=504, code="EXECUTION_TIMEOUT", message=message)


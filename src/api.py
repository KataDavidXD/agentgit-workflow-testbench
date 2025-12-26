from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .exceptions import EnvLocked, EnvNotFound, InvalidPackages, ServiceError
from .models import (
    CleanupRequest,
    CleanupResponse,
    CreateEnvRequest,
    CreateEnvResponse,
    DepsResponse,
    EnvStatusResponse,
    ErrorResponse,
    ExportResponse,
    PackagesRequest,
    RunRequest,
    RunResponse,
    SyncResponse,
)
from src.services.dep_manager import DependencyManager
from src.services.env_manager import EnvManager
from src.services.lock_manager import LockManager
from src.services.uv_executor import UVCommandExecutor


def create_app(settings: Settings | None = None, *, executor: UVCommandExecutor | None = None) -> FastAPI:
    """Create a FastAPI application instance."""

    resolved_settings = settings or get_settings()
    resolved_settings.validate_storage_layout()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("env-manager")

    resolved_executor = executor or UVCommandExecutor(
        envs_base_path=resolved_settings.envs_base_path,
        uv_cache_dir=resolved_settings.uv_cache_dir,
    )
    lock_manager = LockManager()
    env_manager = EnvManager(
        envs_base_path=resolved_settings.envs_base_path,
        executor=resolved_executor,
        default_python=resolved_settings.default_python,
        execution_timeout_seconds=resolved_settings.execution_timeout_seconds,
    )
    dep_manager = DependencyManager(resolved_settings.envs_base_path, resolved_executor)

    app = FastAPI(
        title="LangGraph Node Environment Manager",
        version="0.1.0",
        description="UV-based node-level Python virtual environment isolation and dependency management service",
    )

    @app.exception_handler(ServiceError)
    async def _service_error_handler(_, exc: ServiceError) -> JSONResponse:
        """Handle custom service errors."""
        logger.warning("service_error code=%s message=%s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
        """Handle Pydantic validation errors and map them to standard ErrorResponse."""
        message = "Request parameter validation failed"
        if exc.errors():
            message = "; ".join(
                f"{'.'.join(str(x) for x in (err.get('loc') or []))}: {err.get('msg')}"
                for err in exc.errors()
            )
        invalid = InvalidPackages(message)
        logger.warning("validation_error message=%s", invalid.message)
        return JSONResponse(
            status_code=invalid.http_status,
            content=ErrorResponse(code=invalid.code, message=invalid.message).model_dump(),
        )

    @app.get("/envs/{node_id}", response_model=EnvStatusResponse)
    async def get_env_status(node_id: str) -> EnvStatusResponse:
        """Retrieve the current status of an environment."""

        logger.info("get_env_status node_id=%s", node_id)
        status = env_manager.get_status(node_id)
        return EnvStatusResponse(
            node_id=node_id,
            status=status.status,
            env_path=str(status.env_path),
            has_pyproject=status.has_pyproject,
            has_uv_lock=status.has_uv_lock,
            has_venv=status.has_venv,
            metadata=status.metadata,
        )

    @app.post("/envs", response_model=CreateEnvResponse)
    async def create_env(req: CreateEnvRequest) -> CreateEnvResponse:
        """Create a new environment and optionally install initial dependencies."""

        lock = lock_manager.get_lock(req.node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            logger.info("create_env node_id=%s python=%s", req.node_id, req.python_version)
            # Perform UV initialization and package installation
            env_path, version = await env_manager.create_env(
                req.node_id, python_version=req.python_version, packages=req.packages
            )
            # Return the generated pyproject.toml content for verification
            pyproject = (env_path / "pyproject.toml").read_text(encoding="utf-8")
            return CreateEnvResponse(
                node_id=req.node_id,
                env_path=str(env_path),
                python_version=version,
                status="created",
                pyproject_toml=pyproject,
            )

    @app.delete("/envs/{node_id}")
    async def delete_env(node_id: str) -> dict[str, str]:
        """Delete an environment and clean up its associated lock."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            logger.info("delete_env node_id=%s", node_id)
            env_manager.delete_env(node_id)
            # Remove the lock from memory to avoid leakage
            await lock_manager.cleanup_lock(node_id)
        return {"node_id": node_id, "status": "deleted"}

    @app.post("/envs/{node_id}/deps")
    async def add_deps(node_id: str, req: PackagesRequest) -> dict[str, str]:
        """Add new dependencies to the environment using 'uv add'."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            if not (resolved_settings.envs_base_path / node_id).exists():
                raise EnvNotFound()
            logger.info("add_deps node_id=%s packages=%s", node_id, req.packages)
            await dep_manager.add(node_id, req.packages)
            # Update the last used timestamp
            env_manager.touch(node_id)
        return {"node_id": node_id, "status": "added"}

    @app.put("/envs/{node_id}/deps")
    async def update_deps(node_id: str, req: PackagesRequest) -> dict[str, str]:
        """Upgrade existing dependencies using 'uv add --upgrade'."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            if not (resolved_settings.envs_base_path / node_id).exists():
                raise EnvNotFound()
            logger.info("update_deps node_id=%s packages=%s", node_id, req.packages)
            await dep_manager.update(node_id, req.packages)
            env_manager.touch(node_id)
        return {"node_id": node_id, "status": "updated"}

    @app.delete("/envs/{node_id}/deps")
    async def delete_deps(node_id: str, req: PackagesRequest) -> dict[str, str]:
        """Remove dependencies from the environment using 'uv remove'."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            if not (resolved_settings.envs_base_path / node_id).exists():
                raise EnvNotFound()
            logger.info("delete_deps node_id=%s packages=%s", node_id, req.packages)
            await dep_manager.remove(node_id, req.packages)
            env_manager.touch(node_id)
        return {"node_id": node_id, "status": "removed"}

    @app.get("/envs/{node_id}/deps", response_model=DepsResponse)
    async def list_deps(node_id: str) -> DepsResponse:
        """List dependencies by reading pyproject.toml and uv.lock."""

        logger.info("list_deps node_id=%s", node_id)
        deps, locked = dep_manager.list_dependencies(node_id)
        env_manager.touch(node_id)
        return DepsResponse(node_id=node_id, dependencies=deps, locked_versions=locked)

    @app.post("/envs/{node_id}/sync", response_model=SyncResponse)
    async def sync_env(node_id: str) -> SyncResponse:
        """Synchronize the environment from the lock file using 'uv sync'."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            logger.info("sync_env node_id=%s", node_id)
            await env_manager.sync(node_id)
        return SyncResponse(node_id=node_id, status="synced", packages_installed=None)

    @app.get("/envs/{node_id}/export", response_model=ExportResponse)
    async def export_env(node_id: str) -> ExportResponse:
        """Export environment configuration files (pyproject.toml and uv.lock)."""

        logger.info("export_env node_id=%s", node_id)
        pyproject, uv_lock = env_manager.export_env(node_id)
        return ExportResponse(node_id=node_id, pyproject_toml=pyproject, uv_lock=uv_lock)

    @app.post("/envs/{node_id}/run", response_model=RunResponse)
    async def run_code(node_id: str, req: RunRequest) -> RunResponse:
        """Execute Python code within the isolated environment using 'uv run'."""

        lock = lock_manager.get_lock(node_id)
        if lock.locked():
            raise EnvLocked()
        async with lock:
            logger.info("run_code node_id=%s timeout=%s", node_id, req.timeout)
            result = await env_manager.run(node_id, req.code, timeout_seconds=req.timeout)
        return RunResponse(node_id=node_id, stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code)

    @app.post("/envs/cleanup", response_model=CleanupResponse)
    async def cleanup(req: CleanupRequest) -> CleanupResponse:
        """Clean up environments that have not been used for a long time."""

        logger.info("cleanup idle_hours=%s", req.idle_hours)
        # Use provided idle_hours or fall back to system default
        deleted = env_manager.cleanup(idle_hours=req.idle_hours or resolved_settings.cleanup_idle_hours)
        return CleanupResponse(deleted=deleted, checked_at=datetime.now(timezone.utc))

    return app


app = create_app()

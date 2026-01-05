from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.exceptions import EnvNotFound, ExecutionTimeout
from src.services.project_info import ProjectInfo
from src.services.uv_executor import UVCommandExecutor, UVResult


@dataclass(frozen=True, slots=True)
class EnvStatus:
    status: str
    env_path: Path
    has_pyproject: bool
    has_uv_lock: bool
    has_venv: bool
    metadata: dict[str, Any] | None


class EnvManager:
    """Manages the full lifecycle of node environments."""

    def __init__(
        self,
        envs_base_path: Path,
        executor: UVCommandExecutor,
        default_python: str,
        execution_timeout_seconds: int,
    ) -> None:
        self.envs_base_path = envs_base_path
        self.executor = executor
        self.default_python = default_python
        self.execution_timeout_seconds = execution_timeout_seconds

    @staticmethod
    def get_env_id(workflow_id: str, node_id: str, version_id: str | None = None) -> str:
        """Generate a unique environment identifier/directory name."""
        base = f"{workflow_id}_{node_id}"
        if version_id:
            return f"{base}_{version_id}"
        return base

    def _project_path(self, env_id: str) -> Path:
        """Get the root directory of an environment."""
        return self.envs_base_path / env_id

    def _metadata_path(self, env_id: str) -> Path:
        """Get the path to the metadata.json file."""
        return self._project_path(env_id) / "metadata.json"

    def _read_metadata(self, env_id: str) -> dict[str, Any] | None:
        path = self._metadata_path(env_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_metadata(self, env_id: str, metadata: dict[str, Any]) -> None:
        path = self._metadata_path(env_id)
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def _touch_last_used(self, env_id: str) -> None:
        """Update the last used timestamp in metadata."""
        metadata = self._read_metadata(env_id) or {}
        metadata["env_id"] = env_id
        metadata["last_used_at"] = datetime.now(timezone.utc).isoformat()
        if "created_at" not in metadata:
            metadata["created_at"] = metadata["last_used_at"]
        self._write_metadata(env_id, metadata)

    def touch(self, env_id: str) -> None:
        """Public method to update activity timestamp."""
        project_path = self._project_path(env_id)
        if not project_path.exists():
            raise EnvNotFound()
        self._touch_last_used(env_id)

    async def create_env(
        self,
        env_id: str,
        *,
        python_version: str | None,
        packages: list[str],
    ) -> tuple[Path, str]:
        """Create a new UV project and optionally install initial packages."""
        project_path = self._project_path(env_id)
        version = python_version or self.default_python

        try:
            if not project_path.exists():
                await self.executor.init_project(env_id, version)
        except Exception:
            # If environment creation failed, check if it was created concurrently
            if project_path.exists():
                pass
            else:
                raise

        self._touch_last_used(env_id)

        if packages:
            mapped_packages = ProjectInfo.get_instance().get_dependency_mapping(packages)
            await self.executor.add_packages(env_id, mapped_packages)
            self._touch_last_used(env_id)

        return project_path, version

    def get_status(self, env_id: str) -> EnvStatus:
        """Check the current status and components of an environment."""
        project_path = self._project_path(env_id)
        if not project_path.exists():
            return EnvStatus(
                status="NOT_EXISTS",
                env_path=project_path,
                has_pyproject=False,
                has_uv_lock=False,
                has_venv=False,
                metadata=None,
            )

        pyproject_path = project_path / "pyproject.toml"
        uv_lock_path = project_path / "uv.lock"
        venv_path = project_path / ".venv"
        metadata = self._read_metadata(env_id)

        return EnvStatus(
            status="ACTIVE",
            env_path=project_path,
            has_pyproject=pyproject_path.exists(),
            has_uv_lock=uv_lock_path.exists(),
            has_venv=venv_path.exists(),
            metadata=metadata,
        )

    async def delete_env(self, env_id: str) -> bool:
        """Remove the environment directory and all its contents."""
        project_path = self._project_path(env_id)
        if not project_path.exists():
            return False

        import shutil

        shutil.rmtree(project_path, ignore_errors=True)
        return True

    async def sync(self, env_id: str) -> UVResult:
        """Re-sync the environment from uv.lock."""
        project_path = self._project_path(env_id)
        if not project_path.exists():
            raise EnvNotFound()
        result = await self.executor.sync_env(env_id)
        self._touch_last_used(env_id)
        return result

    async def run(self, env_id: str, code: str, *, timeout_seconds: int | None) -> UVResult:
        """Execute Python code within the environment."""
        project_path = self._project_path(env_id)
        if not project_path.exists():
            raise EnvNotFound()

        timeout = timeout_seconds or self.execution_timeout_seconds
        try:
            result = await self.executor.run_code(env_id, code, timeout_seconds=timeout)
        except TimeoutError as e:
            raise ExecutionTimeout() from e

        self._touch_last_used(env_id)
        return result

    def cleanup(self, *, idle_hours: int) -> list[str]:
        """Remove environments that haven't been used for a specified duration."""
        deleted: list[str] = []
        if not self.envs_base_path.exists():
            return deleted

        # Calculate the cutoff time for idle environments
        threshold = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
        
        # Iterate through all environment directories
        for child in self.envs_base_path.iterdir():
            if not child.is_dir():
                continue
                
            node_id = child.name
            meta_path = child / "metadata.json"
            if not meta_path.exists():
                continue
                
            try:
                # Load metadata and parse the last used timestamp
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                last_used = datetime.fromisoformat(metadata.get("last_used_at"))
            except Exception:
                # Skip if metadata is corrupted or timestamp is missing
                continue
                
            # Ensure timezone awareness for comparison
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
                
            # Delete the environment if it has been idle longer than the threshold
            if last_used < threshold:
                shutil.rmtree(child, ignore_errors=True)
                deleted.append(node_id)

        return deleted

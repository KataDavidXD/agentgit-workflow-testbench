from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    data_root: Path
    envs_base_path: Path
    uv_cache_dir: Path
    default_python: str
    execution_timeout_seconds: int
    cleanup_idle_hours: int

    def validate_storage_layout(self) -> None:
        envs_parent = self.envs_base_path.resolve().parent
        cache_parent = self.uv_cache_dir.resolve().parent
        if envs_parent != cache_parent:
            raise ValueError("UV_CACHE_DIR must be a sibling directory of ENVS_BASE_PATH")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_root = Path(os.getenv("DATA_ROOT", "/data"))
    envs_base_path = Path(os.getenv("ENVS_BASE_PATH", str(data_root / "envs")))
    uv_cache_dir = Path(os.getenv("UV_CACHE_DIR", str(data_root / "uv_cache")))
    default_python = os.getenv("DEFAULT_PYTHON", "3.11")
    execution_timeout_seconds = int(os.getenv("EXECUTION_TIMEOUT", "30"))
    cleanup_idle_hours = int(os.getenv("CLEANUP_IDLE_HOURS", "72"))

    return Settings(
        data_root=data_root,
        envs_base_path=envs_base_path,
        uv_cache_dir=uv_cache_dir,
        default_python=default_python,
        execution_timeout_seconds=execution_timeout_seconds,
        cleanup_idle_hours=cleanup_idle_hours,
    )


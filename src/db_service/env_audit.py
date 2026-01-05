"""
High-level helper for recording environment operations.

This module provides a minimal, non-intrusive way to persist
environment-related actions into the database.

One call = one row in env_operations table.
"""

from __future__ import annotations

import time
from typing import Any
from sqlalchemy.orm import Session
from src.db_service.env_repository import EnvOperationRepository


class EnvAudit:
    """
    Helper class to record env operations.

    Typical usage (in API layer):

        logger = EnvAuditLogger(
            db=db,
            workflow_id=workflow_id,
            node_id=node_id,
        )

        start = logger.start()

        try:
            result = ...
            logger.success(
                operation="add_deps",
                start_time=start,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                metadata={"packages": packages},
            )
        except Exception as e:
            logger.failed(
                operation="add_deps",
                start_time=start,
                error=str(e),
                metadata={"packages": packages},
            )
            raise
    """

    def __init__(
        self,
        *,
        db: Session,
        workflow_id: str,
        node_id: str,
        version_id: str | None = None,
    ) -> None:
        self._db = db
        self._repo = EnvOperationRepository(db)
        self._workflow_id = workflow_id
        self._node_id = node_id
        self._version_id = version_id

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def start() -> float:
        """
        Mark the start time of an operation.
        """
        return time.time()

    @staticmethod
    def _duration_ms(start_time: float) -> float:
        return time.time() - start_time

    # ------------------------------------------------------------------
    # Record helpers
    # ------------------------------------------------------------------

    def success(
        self,
        *,
        operation: str,
        start_time: float,
        stdout: str | None = None,
        stderr: str | None = None,
        exit_code: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a successful env operation.
        """
        self._repo.create(
            workflow_id=self._workflow_id,
            node_id=self._node_id,
            version_id=self._version_id,
            operation=operation,
            status="success",
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=self._duration_ms(start_time),
            metadata=metadata,
        )

    def failed(
        self,
        *,
        operation: str,
        start_time: float,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a failed env operation.
        """
        meta: dict[str, Any] = dict(metadata or {})
        meta["error"] = error

        self._repo.create(
            workflow_id=self._workflow_id,
            node_id=self._node_id,
            version_id=self._version_id,
            operation=operation,
            status="failed",
            stderr=error,
            duration_ms=self._duration_ms(start_time),
            metadata=meta,
        )

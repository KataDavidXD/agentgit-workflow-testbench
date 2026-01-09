"""
SQLAlchemy Audit Log Repository Implementation.
"""

from typing import List, Optional
import json
from sqlalchemy.orm import Session
from sqlalchemy import desc

from wtb.domain.interfaces.repositories import IAuditLogRepository
from wtb.infrastructure.events.wtb_audit_trail import (
    WTBAuditEntry,
    WTBAuditEventType,
    WTBAuditSeverity,
)
from wtb.infrastructure.database.models import AuditLogORM
from .base import BaseRepository


class SQLAlchemyAuditLogRepository(BaseRepository[WTBAuditEntry, AuditLogORM], IAuditLogRepository):
    """
    SQLAlchemy implementation of Audit Log Repository.
    """
    
    def __init__(self, session: Session):
        super().__init__(session, AuditLogORM)
    
    def _to_domain(self, orm: AuditLogORM) -> WTBAuditEntry:
        """Convert ORM to domain entity."""
        return WTBAuditEntry(
            timestamp=orm.timestamp,
            event_type=WTBAuditEventType(orm.event_type),
            severity=WTBAuditSeverity(orm.severity),
            message=orm.message,
            execution_id=orm.execution_id,
            node_id=orm.node_id,
            details=json.loads(orm.details) if orm.details else {},
            error=orm.error,
            duration_ms=orm.duration_ms,
        )
    
    def _to_orm(self, entity: WTBAuditEntry) -> AuditLogORM:
        """Convert domain entity to ORM."""
        return AuditLogORM(
            execution_id=entity.execution_id,
            node_id=entity.node_id,
            timestamp=entity.timestamp,
            event_type=entity.event_type.value,
            severity=entity.severity.value,
            message=entity.message,
            details=json.dumps(entity.details) if entity.details else None,
            error=entity.error,
            duration_ms=entity.duration_ms,
        )
    
    def append_logs(self, execution_id: str, logs: List[WTBAuditEntry]) -> None:
        """
        Append a batch of logs for an execution.
        
        Args:
            execution_id: Execution identifier
            logs: List of audit entries to append
        """
        orms = []
        for log in logs:
            # Ensure execution_id matches
            if not log.execution_id:
                log.execution_id = execution_id
            
            orms.append(self._to_orm(log))
        
        self._session.add_all(orms)
    
    def find_by_execution(self, execution_id: str) -> List[WTBAuditEntry]:
        """
        Get all logs for an execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            List of audit entries
        """
        orms = (
            self._session.query(AuditLogORM)
            .filter(AuditLogORM.execution_id == execution_id)
            .order_by(AuditLogORM.timestamp)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]
    
    def get(self, id: str) -> Optional[WTBAuditEntry]:
        """Get by ID (not typically used for logs, but required by interface)."""
        orm = self._session.query(AuditLogORM).filter(AuditLogORM.id == int(id)).first()
        return self._to_domain(orm) if orm else None
    
    def exists(self, id: str) -> bool:
        """Check if exists."""
        return self._session.query(AuditLogORM).filter(AuditLogORM.id == int(id)).count() > 0
    
    def list(self, limit: int = 100, offset: int = 0) -> List[WTBAuditEntry]:
        """List logs (recent first)."""
        orms = (
            self._session.query(AuditLogORM)
            .order_by(desc(AuditLogORM.timestamp))
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]
    
    def add(self, entity: WTBAuditEntry) -> WTBAuditEntry:
        """Add single log."""
        orm = self._to_orm(entity)
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)
    
    def update(self, entity: WTBAuditEntry) -> WTBAuditEntry:
        """Update log (not supported/needed)."""
        raise NotImplementedError("Audit logs are immutable")
    
    def delete(self, id: str) -> bool:
        """Delete log (not supported/needed)."""
        raise NotImplementedError("Audit logs are immutable")


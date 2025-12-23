"""Node boundary repository implementation."""

import json
from typing import Optional, List
from sqlalchemy.orm import Session

from wtb.domain.interfaces.repositories import INodeBoundaryRepository
from wtb.domain.models import NodeBoundary
from ..models import NodeBoundaryORM


class NodeBoundaryRepository(INodeBoundaryRepository):
    """SQLAlchemy implementation of node boundary repository."""
    
    def __init__(self, session: Session):
        self._session = session
    
    def _to_domain(self, orm: NodeBoundaryORM) -> NodeBoundary:
        """Convert ORM to domain model."""
        error_details = json.loads(orm.error_details) if orm.error_details else None
        
        return NodeBoundary(
            id=orm.id,
            execution_id=orm.execution_id,
            internal_session_id=orm.internal_session_id,
            node_id=orm.node_id,
            entry_checkpoint_id=orm.entry_checkpoint_id,
            exit_checkpoint_id=orm.exit_checkpoint_id,
            node_status=orm.node_status,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            tool_count=orm.tool_count,
            checkpoint_count=orm.checkpoint_count,
            duration_ms=orm.duration_ms,
            error_message=orm.error_message,
            error_details=error_details,
        )
    
    def _to_orm(self, domain: NodeBoundary) -> NodeBoundaryORM:
        """Convert domain model to ORM."""
        return NodeBoundaryORM(
            id=domain.id,
            execution_id=domain.execution_id,
            internal_session_id=domain.internal_session_id,
            node_id=domain.node_id,
            entry_checkpoint_id=domain.entry_checkpoint_id,
            exit_checkpoint_id=domain.exit_checkpoint_id,
            node_status=domain.node_status,
            started_at=domain.started_at,
            completed_at=domain.completed_at,
            tool_count=domain.tool_count,
            checkpoint_count=domain.checkpoint_count,
            duration_ms=domain.duration_ms,
            error_message=domain.error_message,
            error_details=json.dumps(domain.error_details) if domain.error_details else None,
        )
    
    def get(self, id: str) -> Optional[NodeBoundary]:
        """Get by ID (id is actually int for this entity)."""
        orm = self._session.query(NodeBoundaryORM).filter_by(id=int(id)).first()
        return self._to_domain(orm) if orm else None
    
    def list(self, limit: int = 100, offset: int = 0) -> List[NodeBoundary]:
        """List with pagination."""
        orms = (
            self._session.query(NodeBoundaryORM)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]
    
    def exists(self, id: str) -> bool:
        """Check existence."""
        return self._session.query(NodeBoundaryORM).filter_by(id=int(id)).count() > 0
    
    def add(self, entity: NodeBoundary) -> NodeBoundary:
        """Add new entity."""
        orm = self._to_orm(entity)
        # Don't set id if None (auto-increment)
        if entity.id is None:
            orm.id = None
        self._session.add(orm)
        self._session.flush()
        entity.id = orm.id
        return entity
    
    def update(self, entity: NodeBoundary) -> NodeBoundary:
        """Update existing entity."""
        orm = self._session.query(NodeBoundaryORM).filter_by(id=entity.id).first()
        if orm:
            orm.exit_checkpoint_id = entity.exit_checkpoint_id
            orm.node_status = entity.node_status
            orm.completed_at = entity.completed_at
            orm.tool_count = entity.tool_count
            orm.checkpoint_count = entity.checkpoint_count
            orm.duration_ms = entity.duration_ms
            orm.error_message = entity.error_message
            orm.error_details = json.dumps(entity.error_details) if entity.error_details else None
            self._session.flush()
        return entity
    
    def delete(self, id: str) -> bool:
        """Delete entity."""
        orm = self._session.query(NodeBoundaryORM).filter_by(id=int(id)).first()
        if orm:
            self._session.delete(orm)
            self._session.flush()
            return True
        return False
    
    def find_by_session(self, internal_session_id: int) -> List[NodeBoundary]:
        """Find all boundaries for a session."""
        orms = (
            self._session.query(NodeBoundaryORM)
            .filter_by(internal_session_id=internal_session_id)
            .order_by(NodeBoundaryORM.started_at)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]
    
    def find_by_node(self, internal_session_id: int, node_id: str) -> Optional[NodeBoundary]:
        """Find boundary for a specific node."""
        orm = (
            self._session.query(NodeBoundaryORM)
            .filter_by(internal_session_id=internal_session_id, node_id=node_id)
            .first()
        )
        return self._to_domain(orm) if orm else None
    
    def find_completed(self, internal_session_id: int) -> List[NodeBoundary]:
        """Find completed node boundaries."""
        orms = (
            self._session.query(NodeBoundaryORM)
            .filter_by(internal_session_id=internal_session_id, node_status='completed')
            .order_by(NodeBoundaryORM.completed_at)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]


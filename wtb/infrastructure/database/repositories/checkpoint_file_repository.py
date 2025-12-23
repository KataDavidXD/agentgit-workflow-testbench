"""Checkpoint file link repository implementation."""

from typing import Optional, List
from sqlalchemy.orm import Session

from wtb.domain.interfaces.repositories import ICheckpointFileRepository
from wtb.domain.models import CheckpointFile
from ..models import CheckpointFileORM


class CheckpointFileRepository(ICheckpointFileRepository):
    """SQLAlchemy implementation of checkpoint file repository."""
    
    def __init__(self, session: Session):
        self._session = session
    
    def _to_domain(self, orm: CheckpointFileORM) -> CheckpointFile:
        """Convert ORM to domain model."""
        return CheckpointFile(
            id=orm.id,
            checkpoint_id=orm.checkpoint_id,
            file_commit_id=orm.file_commit_id,
            file_count=orm.file_count,
            total_size_bytes=orm.total_size_bytes,
            created_at=orm.created_at,
        )
    
    def _to_orm(self, domain: CheckpointFile) -> CheckpointFileORM:
        """Convert domain model to ORM."""
        return CheckpointFileORM(
            id=domain.id,
            checkpoint_id=domain.checkpoint_id,
            file_commit_id=domain.file_commit_id,
            file_count=domain.file_count,
            total_size_bytes=domain.total_size_bytes,
            created_at=domain.created_at,
        )
    
    def get(self, id: str) -> Optional[CheckpointFile]:
        """Get by ID (id is actually int)."""
        orm = self._session.query(CheckpointFileORM).filter_by(id=int(id)).first()
        return self._to_domain(orm) if orm else None
    
    def list(self, limit: int = 100, offset: int = 0) -> List[CheckpointFile]:
        """List with pagination."""
        orms = (
            self._session.query(CheckpointFileORM)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]
    
    def exists(self, id: str) -> bool:
        """Check existence."""
        return self._session.query(CheckpointFileORM).filter_by(id=int(id)).count() > 0
    
    def add(self, entity: CheckpointFile) -> CheckpointFile:
        """Add new entity."""
        orm = self._to_orm(entity)
        if entity.id is None:
            orm.id = None
        self._session.add(orm)
        self._session.flush()
        entity.id = orm.id
        return entity
    
    def update(self, entity: CheckpointFile) -> CheckpointFile:
        """Update existing entity."""
        orm = self._session.query(CheckpointFileORM).filter_by(id=entity.id).first()
        if orm:
            orm.file_count = entity.file_count
            orm.total_size_bytes = entity.total_size_bytes
            self._session.flush()
        return entity
    
    def delete(self, id: str) -> bool:
        """Delete entity."""
        orm = self._session.query(CheckpointFileORM).filter_by(id=int(id)).first()
        if orm:
            self._session.delete(orm)
            self._session.flush()
            return True
        return False
    
    def find_by_checkpoint(self, checkpoint_id: int) -> Optional[CheckpointFile]:
        """Find file link for a checkpoint."""
        orm = (
            self._session.query(CheckpointFileORM)
            .filter_by(checkpoint_id=checkpoint_id)
            .first()
        )
        return self._to_domain(orm) if orm else None
    
    def find_by_file_commit(self, file_commit_id: str) -> List[CheckpointFile]:
        """Find all checkpoints linked to a file commit."""
        orms = (
            self._session.query(CheckpointFileORM)
            .filter_by(file_commit_id=file_commit_id)
            .all()
        )
        return [self._to_domain(orm) for orm in orms]


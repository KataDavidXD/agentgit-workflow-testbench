"""SQLAlchemy model for environment operations auditing."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Index,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.db_service.connection import Base


class EnvOperation(Base):
    """Records a single environment operation."""

    __tablename__ = "env_operations"

    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(255), nullable=False, index=True)
    node_id = Column(String(255), nullable=False, index=True)
    operation = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)
    operation_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_env_ops_workflow_node", "workflow_id", "node_id"),
        Index("idx_env_ops_node_operation", "node_id", "operation"),
    )


# ============================================================================
# Index Creation with DDL Events
# ============================================================================

@event.listens_for(Base.metadata, "after_create")
def create_indexes(target, connection, **kw):
    """
    Create additional indexes after tables are created.
    """
    # GIN index for JSONB metadata column
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_env_ops_metadata 
        ON env_operations USING GIN (metadata)
    """))

    # Full-text search index for stderr (error messages)
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_env_ops_stderr_fts 
        ON env_operations USING GIN (to_tsvector('english', stderr)) 
        WHERE stderr IS NOT NULL
    """))

    connection.commit()

    print("✓ Created GIN indexes for JSONB columns")
    print("✓ Created full-text search indexes")

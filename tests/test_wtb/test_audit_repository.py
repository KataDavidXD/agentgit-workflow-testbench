"""
Tests for Audit Log Repository.
"""

import pytest
from datetime import datetime
from wtb.infrastructure.database import SQLAlchemyUnitOfWork, InMemoryUnitOfWork
from wtb.infrastructure.events.wtb_audit_trail import (
    WTBAuditEntry,
    WTBAuditEventType,
    WTBAuditSeverity,
)

class TestAuditLogRepository:
    """Test suite for AuditLogRepository."""
    
    @pytest.fixture
    def uow(self):
        """Create a SQLAlchemy UoW with in-memory SQLite."""
        uow = SQLAlchemyUnitOfWork("sqlite:///:memory:")
        with uow:
            yield uow

    def test_add_and_get_log(self, uow):
        """Can add and retrieve a single log."""
        entry = WTBAuditEntry(
            timestamp=datetime.now(),
            event_type=WTBAuditEventType.EXECUTION_STARTED,
            severity=WTBAuditSeverity.INFO,
            message="Test execution started",
            execution_id="exec-1",
            details={"key": "value"}
        )
        
        saved = uow.audit_logs.add(entry)
        uow.commit()
        
        # Verify persistence
        retrieved = uow.audit_logs.list()[0]
        assert retrieved.execution_id == "exec-1"
        assert retrieved.message == "Test execution started"
        assert retrieved.details["key"] == "value"
        assert retrieved.event_type == WTBAuditEventType.EXECUTION_STARTED

    def test_append_logs(self, uow):
        """Can append a batch of logs."""
        logs = [
            WTBAuditEntry(
                timestamp=datetime.now(),
                event_type=WTBAuditEventType.NODE_STARTED,
                severity=WTBAuditSeverity.INFO,
                message=f"Node {i} started",
                execution_id="exec-1",
                node_id=f"node-{i}"
            )
            for i in range(3)
        ]
        
        uow.audit_logs.append_logs("exec-1", logs)
        uow.commit()
        
        retrieved = uow.audit_logs.find_by_execution("exec-1")
        assert len(retrieved) == 3
        assert retrieved[0].node_id == "node-0"
        assert retrieved[2].node_id == "node-2"

    def test_inmemory_repository(self):
        """Test InMemory implementation for parity."""
        uow = InMemoryUnitOfWork()
        
        logs = [
            WTBAuditEntry(
                timestamp=datetime.now(),
                event_type=WTBAuditEventType.EXECUTION_STARTED,
                severity=WTBAuditSeverity.INFO,
                message="InMemory test",
                execution_id="exec-mem"
            )
        ]
        
        uow.audit_logs.append_logs("exec-mem", logs)
        
        retrieved = uow.audit_logs.find_by_execution("exec-mem")
        assert len(retrieved) == 1
        assert retrieved[0].message == "InMemory test"


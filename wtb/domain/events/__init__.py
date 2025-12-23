"""
Domain Events - Events for cross-cutting concerns and external notifications.

These events follow the pattern established in AgentGit's EventBus.
"""

from .execution_events import (
    WTBEvent,
    ExecutionStartedEvent,
    ExecutionPausedEvent,
    ExecutionResumedEvent,
    ExecutionCompletedEvent,
    ExecutionFailedEvent,
    ExecutionCancelledEvent,
)
from .node_events import (
    NodeStartedEvent,
    NodeCompletedEvent,
    NodeFailedEvent,
    NodeSkippedEvent,
)
from .checkpoint_events import (
    CheckpointCreatedEvent,
    RollbackPerformedEvent,
    BranchCreatedEvent,
)

__all__ = [
    # Base
    "WTBEvent",
    # Execution events
    "ExecutionStartedEvent",
    "ExecutionPausedEvent",
    "ExecutionResumedEvent",
    "ExecutionCompletedEvent",
    "ExecutionFailedEvent",
    "ExecutionCancelledEvent",
    # Node events
    "NodeStartedEvent",
    "NodeCompletedEvent",
    "NodeFailedEvent",
    "NodeSkippedEvent",
    # Checkpoint events
    "CheckpointCreatedEvent",
    "RollbackPerformedEvent",
    "BranchCreatedEvent",
]


"""
Workflow Test Bench (WTB) - Testing Framework for Agent Git v0.2

A DDD-based orchestration layer for workflow testing with:
- Execution Controller: Manages workflow lifecycle (run/pause/resume/stop)
- Node Replacer: A/B testing via node variant substitution
- State Adapters: Pluggable persistence (AgentGit, InMemory, etc.)
- Evaluation Engine: Metrics and scoring

Architecture follows:
- SOLID principles
- Domain-Driven Design
- Repository + Unit of Work pattern
- Interface-based abstractions
"""

__version__ = "0.1.0"

# Domain Models
from wtb.domain.models import (
    TestWorkflow,
    WorkflowNode,
    WorkflowEdge,
    Execution,
    ExecutionState,
    ExecutionStatus,
    NodeVariant,
    NodeBoundary,
    CheckpointFile,
    BatchTest,
    BatchTestStatus,
    VariantCombination,
    BatchTestResult,
    EvaluationResult,
    MetricValue,
)

# Domain Interfaces
from wtb.domain.interfaces import (
    IExecutionController,
    INodeReplacer,
    IStateAdapter,
    IUnitOfWork,
    CheckpointTrigger,
    CheckpointInfo,
    NodeBoundaryInfo,
)

# Application Services
from wtb.application import (
    ExecutionController,
    NodeReplacer,
)

# Infrastructure
from wtb.infrastructure import (
    SQLAlchemyUnitOfWork,
    InMemoryStateAdapter,
)

__all__ = [
    # Version
    "__version__",
    # Domain Models
    "TestWorkflow",
    "WorkflowNode",
    "WorkflowEdge",
    "Execution",
    "ExecutionState",
    "ExecutionStatus",
    "NodeVariant",
    "NodeBoundary",
    "CheckpointFile",
    "BatchTest",
    "BatchTestStatus",
    "VariantCombination",
    "BatchTestResult",
    "EvaluationResult",
    "MetricValue",
    # Domain Interfaces
    "IExecutionController",
    "INodeReplacer",
    "IStateAdapter",
    "IUnitOfWork",
    "CheckpointTrigger",
    "CheckpointInfo",
    "NodeBoundaryInfo",
    # Application Services
    "ExecutionController",
    "NodeReplacer",
    # Infrastructure
    "SQLAlchemyUnitOfWork",
    "InMemoryStateAdapter",
]

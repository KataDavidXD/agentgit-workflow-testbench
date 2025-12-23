"""Domain Models - Entities, Value Objects, and Aggregates."""

from .workflow import (
    WorkflowNode,
    WorkflowEdge,
    TestWorkflow,
    ExecutionState,
    Execution,
    ExecutionStatus,
    NodeVariant,
)

from .node_boundary import NodeBoundary
from .checkpoint_file import CheckpointFile
from .batch_test import (
    BatchTest,
    BatchTestStatus,
    VariantCombination,
    BatchTestResult,
)
from .evaluation import (
    EvaluationResult,
    MetricValue,
    ComparisonResult,
)

__all__ = [
    # Workflow models
    "WorkflowNode",
    "WorkflowEdge", 
    "TestWorkflow",
    "ExecutionState",
    "Execution",
    "ExecutionStatus",
    "NodeVariant",
    # Node boundary
    "NodeBoundary",
    # Checkpoint-file link
    "CheckpointFile",
    # Batch test
    "BatchTest",
    "BatchTestStatus",
    "VariantCombination",
    "BatchTestResult",
    # Evaluation
    "EvaluationResult",
    "MetricValue",
    "ComparisonResult",
]

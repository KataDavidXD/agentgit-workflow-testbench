"""
Repository Interfaces.

Defines abstract contracts for data access following the Repository pattern.
Follows Interface Segregation Principle with separate read/write interfaces.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List

T = TypeVar('T')


class IReadRepository(ABC, Generic[T]):
    """
    Read-only repository interface.
    
    Provides query operations without modifying data.
    """
    
    @abstractmethod
    def get(self, id: str) -> Optional[T]:
        """
        Get entity by ID.
        
        Args:
            id: Entity identifier
            
        Returns:
            Entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        List entities with pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    def exists(self, id: str) -> bool:
        """
        Check if entity exists.
        
        Args:
            id: Entity identifier
            
        Returns:
            True if exists, False otherwise
        """
        pass


class IWriteRepository(ABC, Generic[T]):
    """
    Write repository interface.
    
    Provides mutation operations.
    """
    
    @abstractmethod
    def add(self, entity: T) -> T:
        """
        Add a new entity.
        
        Args:
            entity: Entity to add
            
        Returns:
            Added entity (may have ID assigned)
        """
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update an existing entity.
        
        Args:
            entity: Entity with updated values
            
        Returns:
            Updated entity
        """
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        Delete an entity.
        
        Args:
            id: Entity identifier
            
        Returns:
            True if deleted, False if not found
        """
        pass


class IRepository(IReadRepository[T], IWriteRepository[T]):
    """Combined read/write repository interface."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Domain-Specific Repository Interfaces
# ═══════════════════════════════════════════════════════════════════════════════

class IWorkflowRepository(IRepository["TestWorkflow"]):
    """Repository for TestWorkflow aggregates."""
    
    @abstractmethod
    def find_by_name(self, name: str) -> Optional["TestWorkflow"]:
        """
        Find workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            TestWorkflow if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_version(self, name: str, version: str) -> Optional["TestWorkflow"]:
        """
        Find workflow by name and version.
        
        Args:
            name: Workflow name
            version: Workflow version
            
        Returns:
            TestWorkflow if found, None otherwise
        """
        pass


class IExecutionRepository(IRepository["Execution"]):
    """Repository for Execution aggregates."""
    
    @abstractmethod
    def find_by_workflow(self, workflow_id: str) -> List["Execution"]:
        """
        Find all executions for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            List of executions
        """
        pass
    
    @abstractmethod
    def find_by_status(self, status: "ExecutionStatus") -> List["Execution"]:
        """
        Find executions by status.
        
        Args:
            status: Execution status to filter by
            
        Returns:
            List of matching executions
        """
        pass
    
    @abstractmethod
    def find_running(self) -> List["Execution"]:
        """
        Find all currently running executions.
        
        Returns:
            List of running executions
        """
        pass


class INodeVariantRepository(IRepository["NodeVariant"]):
    """Repository for NodeVariant aggregates."""
    
    @abstractmethod
    def find_by_workflow(self, workflow_id: str) -> List["NodeVariant"]:
        """
        Find all variants for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            List of variants
        """
        pass
    
    @abstractmethod
    def find_by_node(self, workflow_id: str, node_id: str) -> List["NodeVariant"]:
        """
        Find variants for a specific node.
        
        Args:
            workflow_id: Workflow identifier
            node_id: Original node identifier
            
        Returns:
            List of variants for the node
        """
        pass
    
    @abstractmethod
    def find_active(self, workflow_id: str) -> List["NodeVariant"]:
        """
        Find active variants for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            List of active variants
        """
        pass


class IBatchTestRepository(IRepository["BatchTest"]):
    """Repository for BatchTest aggregates."""
    
    @abstractmethod
    def find_by_workflow(self, workflow_id: str) -> List["BatchTest"]:
        """
        Find batch tests for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            List of batch tests
        """
        pass
    
    @abstractmethod
    def find_pending(self) -> List["BatchTest"]:
        """
        Find pending batch tests.
        
        Returns:
            List of pending batch tests
        """
        pass


class IEvaluationResultRepository(IRepository["EvaluationResult"]):
    """Repository for EvaluationResult entities."""
    
    @abstractmethod
    def find_by_execution(self, execution_id: str) -> List["EvaluationResult"]:
        """
        Find evaluation results for an execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            List of evaluation results
        """
        pass
    
    @abstractmethod
    def find_by_evaluator(self, evaluator_name: str) -> List["EvaluationResult"]:
        """
        Find results from a specific evaluator.
        
        Args:
            evaluator_name: Name of the evaluator
            
        Returns:
            List of results from that evaluator
        """
        pass


class INodeBoundaryRepository(IRepository["NodeBoundary"]):
    """Repository for NodeBoundary entities (WTB-specific)."""
    
    @abstractmethod
    def find_by_session(self, internal_session_id: int) -> List["NodeBoundary"]:
        """
        Find all boundaries for a session.
        
        Args:
            internal_session_id: AgentGit session ID
            
        Returns:
            List of node boundaries
        """
        pass
    
    @abstractmethod
    def find_by_node(self, internal_session_id: int, node_id: str) -> Optional["NodeBoundary"]:
        """
        Find boundary for a specific node.
        
        Args:
            internal_session_id: AgentGit session ID
            node_id: Workflow node ID
            
        Returns:
            NodeBoundary if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_completed(self, internal_session_id: int) -> List["NodeBoundary"]:
        """
        Find completed node boundaries (for rollback targets).
        
        Args:
            internal_session_id: AgentGit session ID
            
        Returns:
            List of completed node boundaries
        """
        pass


class ICheckpointFileRepository(IRepository["CheckpointFile"]):
    """Repository for CheckpointFile links (WTB-specific)."""
    
    @abstractmethod
    def find_by_checkpoint(self, checkpoint_id: int) -> Optional["CheckpointFile"]:
        """
        Find file link for a checkpoint.
        
        Args:
            checkpoint_id: AgentGit checkpoint ID
            
        Returns:
            CheckpointFile if linked, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_file_commit(self, file_commit_id: str) -> List["CheckpointFile"]:
        """
        Find all checkpoints linked to a file commit.
        
        Args:
            file_commit_id: FileTracker commit UUID
            
        Returns:
            List of checkpoint-file links
        """
        pass


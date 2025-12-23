"""
Execution Controller Implementation.

Orchestrates workflow execution with support for:
- Run/Pause/Resume/Stop lifecycle
- Breakpoint handling
- State persistence via adapters
- Rollback capabilities
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from wtb.domain.interfaces.execution_controller import IExecutionController
from wtb.domain.interfaces.state_adapter import IStateAdapter, CheckpointTrigger
from wtb.domain.interfaces.node_executor import INodeExecutor, INodeExecutorRegistry, NodeExecutionResult
from wtb.domain.interfaces.repositories import IExecutionRepository, IWorkflowRepository
from wtb.domain.models import (
    Execution,
    ExecutionState,
    ExecutionStatus,
    TestWorkflow,
    WorkflowNode,
)


class DefaultNodeExecutor(INodeExecutor):
    """
    Default node executor that runs node logic.
    
    For now, this is a simple pass-through executor.
    In production, this would integrate with ToolManager.
    """
    
    def __init__(self):
        self._supported_types = ['action', 'start', 'end', 'decision']
    
    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any]
    ) -> NodeExecutionResult:
        """Execute a workflow node."""
        start_time = datetime.now()
        
        try:
            # Handle different node types
            if node.type == 'start':
                result = {"started": True}
            elif node.type == 'end':
                result = {"completed": True}
            elif node.type == 'decision':
                # Decision nodes evaluate conditions
                result = self._evaluate_decision(node, context)
            else:
                # Action nodes execute tools or custom logic
                result = self._execute_action(node, context)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            return NodeExecutionResult(
                success=True,
                output=result,
                duration_ms=duration,
                tool_invocations=1 if node.type == 'action' else 0,
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return NodeExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )
    
    def _execute_action(self, node: WorkflowNode, context: Dict[str, Any]) -> Any:
        """Execute an action node."""
        # Default behavior: return node config merged with context
        result = {
            "node_id": node.id,
            "node_name": node.name,
            "tool_name": node.tool_name,
        }
        
        # Apply any configured transformations
        if node.config:
            result.update(node.config)
        
        return result
    
    def _evaluate_decision(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a decision node."""
        condition = node.config.get("condition", "True")
        
        try:
            result = eval(condition, {"__builtins__": {}}, context)
            return {"decision": bool(result), "condition": condition}
        except Exception:
            return {"decision": False, "condition": condition, "error": "evaluation_failed"}
    
    def can_execute(self, node: WorkflowNode) -> bool:
        """Check if this executor can handle the given node."""
        return node.type in self._supported_types
    
    def get_supported_node_types(self) -> list:
        """Get list of supported node types."""
        return self._supported_types


class ExecutionController(IExecutionController):
    """
    Main execution controller implementation.
    
    Orchestrates the execution of workflows with full lifecycle management:
    - Creates executions from workflow definitions
    - Manages run/pause/resume/stop operations
    - Handles breakpoints
    - Supports rollback to checkpoints
    - Persists state through IStateAdapter
    """
    
    def __init__(
        self,
        execution_repository: IExecutionRepository,
        workflow_repository: IWorkflowRepository,
        state_adapter: IStateAdapter,
        node_executor: Optional[INodeExecutor] = None,
    ):
        """
        Initialize the execution controller.
        
        Args:
            execution_repository: Repository for executions
            workflow_repository: Repository for workflows
            state_adapter: Adapter for state persistence
            node_executor: Optional node executor (defaults to DefaultNodeExecutor)
        """
        self._exec_repo = execution_repository
        self._workflow_repo = workflow_repository
        self._state_adapter = state_adapter
        self._node_executor = node_executor or DefaultNodeExecutor()
    
    def create_execution(
        self, 
        workflow: TestWorkflow,
        initial_state: Optional[Dict[str, Any]] = None,
        breakpoints: Optional[List[str]] = None
    ) -> Execution:
        """Create a new execution for a workflow."""
        # Validate workflow
        errors = workflow.validate()
        if errors:
            raise ValueError(f"Invalid workflow: {', '.join(errors)}")
        
        # Create initial state
        state = ExecutionState(
            current_node_id=workflow.entry_point,
            workflow_variables=initial_state or {},
            execution_path=[],
            node_results={},
        )
        
        # Create execution
        execution = Execution(
            workflow_id=workflow.id,
            status=ExecutionStatus.PENDING,
            state=state,
            breakpoints=breakpoints or [],
        )
        
        # Initialize state adapter session
        session_id = self._state_adapter.initialize_session(
            execution_id=execution.id,
            initial_state=state,
        )
        execution.agentgit_session_id = session_id
        
        # Persist execution
        self._exec_repo.add(execution)
        
        return execution
    
    def run(self, execution_id: str) -> Execution:
        """Start or continue execution."""
        execution = self._get_execution(execution_id)
        workflow = self._get_workflow(execution.workflow_id)
        
        # Start execution if pending
        if execution.status == ExecutionStatus.PENDING:
            execution.start()
        elif execution.status == ExecutionStatus.PAUSED:
            execution.resume()
        else:
            raise RuntimeError(f"Cannot run execution in status {execution.status.value}")
        
        # Ensure state adapter session is set
        if execution.agentgit_session_id:
            self._state_adapter.set_current_session(execution.agentgit_session_id)
        
        # Main execution loop
        try:
            while execution.status == ExecutionStatus.RUNNING:
                current_node_id = execution.state.current_node_id
                
                if not current_node_id:
                    # No more nodes - execution complete
                    execution.complete()
                    break
                
                # Check for breakpoint
                if current_node_id in execution.breakpoints:
                    self._create_checkpoint(
                        execution, 
                        current_node_id,
                        f"Breakpoint: {current_node_id}"
                    )
                    execution.pause()
                    break
                
                # Get node
                node = workflow.get_node(current_node_id)
                if not node:
                    raise ValueError(f"Node {current_node_id} not found in workflow")
                
                # Create checkpoint before node execution
                entry_cp_id = self._create_checkpoint(
                    execution,
                    current_node_id,
                    f"Before: {current_node_id}"
                )
                
                # Mark node as started
                self._state_adapter.mark_node_started(current_node_id, entry_cp_id)
                
                # Execute node
                result = self._node_executor.execute(
                    node=node,
                    context=execution.state.workflow_variables,
                )
                
                if not result.success:
                    # Node failed
                    self._state_adapter.mark_node_failed(current_node_id, result.error or "Unknown error")
                    execution.fail(result.error or "Node execution failed", current_node_id)
                    break
                
                # Update state
                execution.state.execution_path.append(current_node_id)
                execution.state.node_results[current_node_id] = result.output
                
                if isinstance(result.output, dict):
                    execution.state.workflow_variables.update(result.output)
                
                # Create checkpoint after node execution
                exit_cp_id = self._create_checkpoint(
                    execution,
                    current_node_id,
                    f"After: {current_node_id}"
                )
                
                # Mark node as completed
                checkpoint_count = 2  # entry + exit
                self._state_adapter.mark_node_completed(
                    current_node_id,
                    exit_cp_id,
                    tool_count=result.tool_invocations,
                    checkpoint_count=checkpoint_count,
                )
                
                # Determine next node
                next_node_id = self._determine_next_node(workflow, execution, result.output)
                execution.state.current_node_id = next_node_id
        
        except Exception as e:
            execution.fail(str(e), execution.state.current_node_id)
        
        # Persist final state
        self._exec_repo.update(execution)
        
        return execution
    
    def pause(self, execution_id: str) -> Execution:
        """Pause execution at current position."""
        execution = self._get_execution(execution_id)
        
        if not execution.can_pause():
            raise ValueError(f"Cannot pause execution in status {execution.status.value}")
        
        # Create checkpoint
        self._create_checkpoint(
            execution,
            execution.state.current_node_id or "unknown",
            "Manual Pause"
        )
        
        execution.pause()
        self._exec_repo.update(execution)
        
        return execution
    
    def resume(
        self, 
        execution_id: str, 
        modified_state: Optional[Dict[str, Any]] = None
    ) -> Execution:
        """Resume paused execution."""
        execution = self._get_execution(execution_id)
        
        if not execution.can_resume():
            raise ValueError(f"Cannot resume execution in status {execution.status.value}")
        
        # Apply modified state if provided
        if modified_state:
            execution.state.workflow_variables.update(modified_state)
        
        # Run will handle the resume
        return self.run(execution_id)
    
    def stop(self, execution_id: str) -> Execution:
        """Stop and cancel execution."""
        execution = self._get_execution(execution_id)
        
        execution.cancel()
        self._exec_repo.update(execution)
        
        return execution
    
    def rollback(self, execution_id: str, checkpoint_id: int) -> Execution:
        """Rollback to a previous checkpoint."""
        execution = self._get_execution(execution_id)
        
        if not execution.can_rollback():
            raise ValueError(f"Cannot rollback execution in status {execution.status.value}")
        
        # Perform rollback via state adapter
        restored_state = self._state_adapter.rollback(checkpoint_id)
        
        # Update execution
        execution.state = restored_state
        execution.status = ExecutionStatus.PAUSED
        execution.agentgit_checkpoint_id = checkpoint_id
        
        self._exec_repo.update(execution)
        
        return execution
    
    def get_state(self, execution_id: str) -> ExecutionState:
        """Get current execution state."""
        execution = self._get_execution(execution_id)
        return execution.state
    
    def get_status(self, execution_id: str) -> Execution:
        """Get execution with current status."""
        return self._get_execution(execution_id)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Private Methods
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _get_execution(self, execution_id: str) -> Execution:
        """Get execution or raise ValueError."""
        execution = self._exec_repo.get(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        return execution
    
    def _get_workflow(self, workflow_id: str) -> TestWorkflow:
        """Get workflow or raise ValueError."""
        workflow = self._workflow_repo.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        return workflow
    
    def _create_checkpoint(
        self, 
        execution: Execution,
        node_id: str,
        name: str
    ) -> int:
        """Create a checkpoint via state adapter."""
        checkpoint_id = self._state_adapter.save_checkpoint(
            state=execution.state,
            node_id=node_id,
            trigger=CheckpointTrigger.AUTO,
            name=name,
            metadata={
                "execution_id": execution.id,
            }
        )
        execution.agentgit_checkpoint_id = checkpoint_id
        return checkpoint_id
    
    def _determine_next_node(
        self, 
        workflow: TestWorkflow,
        execution: Execution,
        last_result: Any
    ) -> Optional[str]:
        """Determine the next node based on edges and conditions."""
        current_node_id = execution.state.current_node_id
        if not current_node_id:
            return None
        
        edges = workflow.get_outgoing_edges(current_node_id)
        
        for edge in edges:
            if edge.condition is None:
                # Unconditional edge
                return edge.target_id
            
            # Evaluate condition
            condition_result = self._evaluate_condition(
                edge.condition,
                execution.state.workflow_variables,
                last_result
            )
            
            if condition_result:
                return edge.target_id
        
        return None  # No outgoing edge found - end of workflow
    
    def _evaluate_condition(
        self, 
        condition: str,
        variables: Dict[str, Any],
        last_result: Any
    ) -> bool:
        """Evaluate an edge condition."""
        context = {**variables, "_last_result": last_result}
        try:
            return bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            return False


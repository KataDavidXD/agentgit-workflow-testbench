"""
ThreadPool Batch Test Runner.

Local multithreaded implementation of IBatchTestRunner for development
and single-node execution.

Usage:
    from wtb.application.services.batch_test_runner import ThreadPoolBatchTestRunner
    
    runner = ThreadPoolBatchTestRunner(
        uow_factory=UnitOfWorkFactory,
        state_adapter_factory=lambda: InMemoryStateAdapter(),
        max_workers=4,
    )
    
    result = runner.run_batch_test(batch_test)
"""

from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from threading import Lock
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
import time
import uuid
import logging

from wtb.domain.models.batch_test import (
    BatchTest,
    BatchTestResult,
    BatchTestStatus,
    VariantCombination,
)
from wtb.domain.models.workflow import Execution, ExecutionStatus
from wtb.domain.interfaces.batch_runner import (
    IBatchTestRunner,
    BatchRunnerStatus,
    BatchRunnerProgress,
    BatchRunnerError,
    BatchRunnerExecutionError,
)
from wtb.domain.interfaces.state_adapter import IStateAdapter
from wtb.domain.interfaces.unit_of_work import IUnitOfWork

logger = logging.getLogger(__name__)


@dataclass
class _RunningTest:
    """Internal state for a running batch test."""
    batch_test_id: str
    futures: List[Future]
    started_at: datetime
    completed: int = 0
    failed: int = 0
    cancelled: bool = False


class ThreadPoolBatchTestRunner(IBatchTestRunner):
    """
    ThreadPool-based batch test runner for local execution.
    
    Key Design Decisions:
    - ThreadPoolExecutor for I/O-bound operations (DB, LLM calls)
    - Application-level isolation: each thread gets own UoW + StateAdapter
    - Progress tracking via internal state
    - Graceful cancellation support
    
    Thread Safety:
    - Uses Lock for internal state updates
    - Each worker thread has isolated dependencies
    
    Usage:
        runner = ThreadPoolBatchTestRunner(
            uow_factory=lambda: InMemoryUnitOfWork(),
            state_adapter_factory=lambda: InMemoryStateAdapter(),
            max_workers=4,
        )
        
        batch_test = BatchTest(...)
        result = runner.run_batch_test(batch_test)
    """
    
    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        state_adapter_factory: Callable[[], IStateAdapter],
        max_workers: int = 4,
        execution_timeout_seconds: float = 300.0,
    ):
        """
        Initialize the runner.
        
        Args:
            uow_factory: Factory to create isolated UnitOfWork per thread
            state_adapter_factory: Factory to create isolated StateAdapter per thread
            max_workers: Maximum concurrent workers
            execution_timeout_seconds: Timeout for each variant execution
        """
        self._uow_factory = uow_factory
        self._state_adapter_factory = state_adapter_factory
        self._max_workers = max_workers
        self._execution_timeout = execution_timeout_seconds
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running_tests: Dict[str, _RunningTest] = {}
        self._lock = Lock()
        self._shutdown = False
    
    # ═══════════════════════════════════════════════════════════════
    # IBatchTestRunner Implementation
    # ═══════════════════════════════════════════════════════════════
    
    def run_batch_test(self, batch_test: BatchTest) -> BatchTest:
        """
        Execute batch test with ThreadPool parallelism.
        
        Flow:
        1. Create ThreadPoolExecutor if needed
        2. Submit all variants as separate tasks
        3. Wait for completion with progress tracking
        4. Aggregate results and build comparison matrix
        """
        if self._shutdown:
            raise BatchRunnerError("Runner has been shut down")
        
        # Validate batch test
        if not batch_test.variant_combinations:
            raise BatchRunnerError("No variant combinations to execute")
        
        batch_test.start()
        
        # Ensure executor exists
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        
        # Track running state
        running_test = _RunningTest(
            batch_test_id=batch_test.id,
            futures=[],
            started_at=datetime.now(),
        )
        
        with self._lock:
            self._running_tests[batch_test.id] = running_test
        
        try:
            # Submit all variants
            futures_to_combo: Dict[Future, VariantCombination] = {}
            
            for combo in batch_test.variant_combinations:
                future = self._executor.submit(
                    self._execute_variant,
                    batch_test.workflow_id,
                    combo,
                    batch_test.initial_state.copy(),
                )
                futures_to_combo[future] = combo
                running_test.futures.append(future)
            
            # Process results as they complete
            for future in as_completed(futures_to_combo.keys()):
                combo = futures_to_combo[future]
                
                # Check for cancellation
                if running_test.cancelled:
                    break
                
                try:
                    result = future.result(timeout=self._execution_timeout)
                    batch_test.add_result(result)
                    
                    with self._lock:
                        if result.success:
                            running_test.completed += 1
                        else:
                            running_test.failed += 1
                            
                except Exception as e:
                    logger.error(f"Variant {combo.name} failed: {e}")
                    
                    error_result = BatchTestResult(
                        combination_name=combo.name,
                        execution_id="",
                        success=False,
                        error_message=str(e),
                    )
                    batch_test.add_result(error_result)
                    
                    with self._lock:
                        running_test.failed += 1
            
            # Finalize
            if running_test.cancelled:
                batch_test.cancel()
            elif running_test.failed == len(batch_test.variant_combinations):
                batch_test.fail("All variants failed")
            else:
                batch_test.complete()
                batch_test.build_comparison_matrix()
            
            return batch_test
            
        finally:
            with self._lock:
                self._running_tests.pop(batch_test.id, None)
    
    def _execute_variant(
        self,
        workflow_id: str,
        combo: VariantCombination,
        initial_state: Dict[str, Any],
    ) -> BatchTestResult:
        """
        Execute a single variant combination.
        
        Creates isolated dependencies (UoW, StateAdapter) for thread safety.
        
        Args:
            workflow_id: Workflow to execute
            combo: Variant combination to apply
            initial_state: Initial state for execution
            
        Returns:
            BatchTestResult with execution outcome
        """
        start_time = time.time()
        execution_id = str(uuid.uuid4())
        
        try:
            # Create isolated dependencies
            uow = self._uow_factory()
            state_adapter = self._state_adapter_factory()
            
            with uow:
                # Get workflow
                workflow = uow.workflows.get(workflow_id)
                if workflow is None:
                    raise BatchRunnerExecutionError(
                        f"Workflow {workflow_id} not found",
                        batch_test_id="",
                        failed_variant=combo.name,
                    )
                
                # Create execution
                execution = Execution(
                    id=execution_id,
                    workflow_id=workflow_id,
                    initial_state=initial_state,
                    metadata={
                        "variant_combination": combo.to_dict(),
                        "batch_test_variant": combo.name,
                    },
                )
                
                # Apply variants to workflow graph
                modified_definition = self._apply_variants(
                    workflow.definition,
                    combo.variants,
                )
                
                # Execute the workflow
                # Note: This is a simplified execution loop
                # Real implementation would use ExecutionController
                execution.start()
                
                # Simulate execution (placeholder for real node execution)
                # In production, this would:
                # 1. Get the execution controller
                # 2. Run through each node with variants applied
                # 3. Track checkpoints via state_adapter
                result_metrics = self._run_workflow_nodes(
                    execution,
                    modified_definition,
                    state_adapter,
                    uow,
                )
                
                execution.complete({"result": "success"})
                uow.executions.add(execution)
                uow.commit()
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return BatchTestResult(
                    combination_name=combo.name,
                    execution_id=execution_id,
                    success=True,
                    duration_ms=duration_ms,
                    metrics=result_metrics,
                    overall_score=result_metrics.get("overall_score", 0.0),
                )
                
        except Exception as e:
            logger.error(f"Execution failed for {combo.name}: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            
            return BatchTestResult(
                combination_name=combo.name,
                execution_id=execution_id,
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
    
    def _apply_variants(
        self,
        definition: Dict[str, Any],
        variants: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Apply variant substitutions to workflow definition.
        
        Args:
            definition: Original workflow definition
            variants: node_id -> variant_id mapping
            
        Returns:
            Modified workflow definition
        """
        # Deep copy to avoid mutation
        import copy
        modified = copy.deepcopy(definition)
        
        # Apply each variant
        for node_id, variant_id in variants.items():
            if "nodes" in modified and node_id in modified["nodes"]:
                modified["nodes"][node_id]["variant_id"] = variant_id
        
        return modified
    
    def _run_workflow_nodes(
        self,
        execution: Execution,
        definition: Dict[str, Any],
        state_adapter: IStateAdapter,
        uow: IUnitOfWork,
    ) -> Dict[str, float]:
        """
        Execute workflow nodes and collect metrics.
        
        This is a placeholder implementation. Real execution would:
        1. Traverse the workflow graph
        2. Execute each node with the appropriate variant
        3. Track state via checkpoints
        4. Collect evaluation metrics
        
        Returns:
            Dictionary of collected metrics
        """
        # Placeholder: Return mock metrics
        # In production, this integrates with ExecutionController
        metrics = {
            "overall_score": 0.8,
            "latency_ms": 100.0,
            "accuracy": 0.9,
        }
        
        return metrics
    
    def get_status(self, batch_test_id: str) -> BatchRunnerStatus:
        """Get status of a batch test."""
        with self._lock:
            if batch_test_id in self._running_tests:
                running = self._running_tests[batch_test_id]
                if running.cancelled:
                    return BatchRunnerStatus.CANCELLING
                return BatchRunnerStatus.RUNNING
        return BatchRunnerStatus.IDLE
    
    def get_progress(self, batch_test_id: str) -> Optional[BatchRunnerProgress]:
        """Get progress for a running batch test."""
        with self._lock:
            running = self._running_tests.get(batch_test_id)
            if running is None:
                return None
            
            total = len(running.futures)
            completed = running.completed + running.failed
            elapsed = (datetime.now() - running.started_at).total_seconds() * 1000
            
            # Estimate remaining time
            estimated_remaining = None
            if completed > 0:
                avg_time = elapsed / completed
                remaining = total - completed
                estimated_remaining = avg_time * remaining
            
            return BatchRunnerProgress(
                batch_test_id=batch_test_id,
                total_variants=total,
                completed_variants=running.completed,
                failed_variants=running.failed,
                in_progress_variants=total - completed,
                elapsed_ms=elapsed,
                estimated_remaining_ms=estimated_remaining,
            )
    
    def cancel(self, batch_test_id: str) -> bool:
        """Cancel a running batch test."""
        with self._lock:
            running = self._running_tests.get(batch_test_id)
            if running is None:
                return False
            
            running.cancelled = True
            
            # Cancel pending futures
            for future in running.futures:
                future.cancel()
            
            return True
    
    def shutdown(self) -> None:
        """Shutdown the executor."""
        self._shutdown = True
        
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
        
        with self._lock:
            self._running_tests.clear()


"""
Application Factories.

Factory pattern for creating application services with proper dependency injection.
Simplifies service creation while maintaining flexibility for testing.
"""

from typing import Optional, Callable

from wtb.domain.interfaces.state_adapter import IStateAdapter
from wtb.domain.interfaces.unit_of_work import IUnitOfWork
from wtb.domain.interfaces.node_executor import INodeExecutor
from wtb.domain.interfaces.batch_runner import IBatchTestRunner
from wtb.config import WTBConfig, get_config
from wtb.infrastructure.database import (
    UnitOfWorkFactory,
    SQLAlchemyUnitOfWork,
    InMemoryUnitOfWork,
)
from wtb.infrastructure.adapters import InMemoryStateAdapter

from .services.execution_controller import ExecutionController, DefaultNodeExecutor
from .services.node_replacer import NodeReplacer


class ExecutionControllerFactory:
    """
    Factory for creating ExecutionController with proper dependencies.
    
    Handles dependency injection based on configuration:
    - Testing: In-memory UoW and InMemoryStateAdapter
    - Development: SQLAlchemy UoW and AgentGitStateAdapter
    - Production: Same as development with production URLs
    
    Usage:
        # Using config
        config = WTBConfig.for_development()
        controller = ExecutionControllerFactory.create(config)
        
        # With custom dependencies
        controller = ExecutionControllerFactory.create_with_dependencies(
            uow=my_uow,
            state_adapter=my_adapter,
        )
        
        # Quick test setup
        controller = ExecutionControllerFactory.create_for_testing()
    """
    
    @staticmethod
    def create(config: Optional[WTBConfig] = None) -> ExecutionController:
        """
        Create ExecutionController based on configuration.
        
        Args:
            config: WTB configuration (uses global config if None)
            
        Returns:
            ExecutionController with configured dependencies
        """
        if config is None:
            config = get_config()
        
        # Create UoW
        uow = UnitOfWorkFactory.create(
            mode=config.wtb_storage_mode,
            db_url=config.wtb_db_url,
            echo=config.log_sql,
        )
        
        # Create state adapter
        state_adapter = ExecutionControllerFactory._create_state_adapter(config, uow)
        
        # Get repositories from UoW
        # Note: For a real UoW, we need to enter the context first
        # For now, we pass the UoW and let the controller manage the context
        return ExecutionControllerFactory._create_controller(uow, state_adapter)
    
    @staticmethod
    def _create_state_adapter(config: WTBConfig, uow: IUnitOfWork) -> IStateAdapter:
        """Create state adapter based on config."""
        if config.state_adapter_mode == "inmemory":
            return InMemoryStateAdapter()
        
        elif config.state_adapter_mode == "agentgit":
            # Import conditionally to avoid hard dependency
            try:
                from wtb.infrastructure.adapters import AgentGitStateAdapter
                if AgentGitStateAdapter is None:
                    raise ImportError("AgentGit not installed")
                
                return AgentGitStateAdapter(
                    agentgit_db_path=config.agentgit_db_path,
                    wtb_db_url=config.wtb_db_url,
                )
            except ImportError:
                # Fall back to in-memory if AgentGit not available
                import warnings
                warnings.warn(
                    "AgentGit not available, falling back to InMemoryStateAdapter",
                    RuntimeWarning,
                )
                return InMemoryStateAdapter()
        
        else:
            raise ValueError(f"Unknown state adapter mode: {config.state_adapter_mode}")
    
    @staticmethod
    def _create_controller(
        uow: IUnitOfWork,
        state_adapter: IStateAdapter,
        node_executor: Optional[INodeExecutor] = None,
    ) -> ExecutionController:
        """Create controller with given dependencies."""
        # Enter UoW context to get repositories
        with uow:
            return ExecutionController(
                execution_repository=uow.executions,
                workflow_repository=uow.workflows,
                state_adapter=state_adapter,
                node_executor=node_executor or DefaultNodeExecutor(),
            )
    
    @staticmethod
    def create_with_dependencies(
        uow: IUnitOfWork,
        state_adapter: IStateAdapter,
        node_executor: Optional[INodeExecutor] = None,
    ) -> ExecutionController:
        """
        Create controller with explicit dependencies.
        
        Useful for testing with custom mock/fake implementations.
        
        Args:
            uow: Unit of Work providing repositories
            state_adapter: State adapter for checkpointing
            node_executor: Optional custom node executor
            
        Returns:
            ExecutionController with provided dependencies
        """
        return ExecutionControllerFactory._create_controller(
            uow, state_adapter, node_executor
        )
    
    @staticmethod
    def create_for_testing(
        node_executor: Optional[INodeExecutor] = None,
    ) -> ExecutionController:
        """
        Create controller for unit tests.
        
        Uses in-memory storage for speed and isolation.
        
        Args:
            node_executor: Optional custom node executor
            
        Returns:
            ExecutionController with in-memory dependencies
        """
        config = WTBConfig.for_testing()
        uow = InMemoryUnitOfWork()
        state_adapter = InMemoryStateAdapter()
        
        return ExecutionControllerFactory._create_controller(
            uow, state_adapter, node_executor
        )
    
    @staticmethod
    def create_for_development(
        data_dir: str = "data",
        node_executor: Optional[INodeExecutor] = None,
    ) -> ExecutionController:
        """
        Create controller for development.
        
        Uses SQLite persistence with optional AgentGit integration.
        
        Args:
            data_dir: Directory for database files
            node_executor: Optional custom node executor
            
        Returns:
            ExecutionController with SQLite persistence
        """
        config = WTBConfig.for_development(data_dir)
        return ExecutionControllerFactory.create(config)


class NodeReplacerFactory:
    """
    Factory for creating NodeReplacer with proper dependencies.
    
    Usage:
        # Using config
        replacer = NodeReplacerFactory.create()
        
        # For testing
        replacer = NodeReplacerFactory.create_for_testing()
    """
    
    @staticmethod
    def create(config: Optional[WTBConfig] = None) -> NodeReplacer:
        """
        Create NodeReplacer based on configuration.
        
        Args:
            config: WTB configuration (uses global config if None)
            
        Returns:
            NodeReplacer with configured dependencies
        """
        if config is None:
            config = get_config()
        
        uow = UnitOfWorkFactory.create(
            mode=config.wtb_storage_mode,
            db_url=config.wtb_db_url,
        )
        
        with uow:
            return NodeReplacer(variant_repository=uow.variants)
    
    @staticmethod
    def create_with_dependencies(uow: IUnitOfWork) -> NodeReplacer:
        """
        Create NodeReplacer with explicit UoW.
        
        Args:
            uow: Unit of Work providing repositories
            
        Returns:
            NodeReplacer with provided dependencies
        """
        with uow:
            return NodeReplacer(variant_repository=uow.variants)
    
    @staticmethod
    def create_for_testing() -> NodeReplacer:
        """
        Create NodeReplacer for unit tests.
        
        Returns:
            NodeReplacer with in-memory storage
        """
        uow = InMemoryUnitOfWork()
        return NodeReplacerFactory.create_with_dependencies(uow)


class BatchTestRunnerFactory:
    """
    Factory for creating batch test runners.
    
    Supports two implementations:
    - ThreadPoolBatchTestRunner: Local multithreaded execution
    - RayBatchTestRunner: Distributed execution via Ray cluster
    
    Usage:
        # Auto-select based on config
        runner = BatchTestRunnerFactory.create(config)
        
        # Explicit ThreadPool
        runner = BatchTestRunnerFactory.create_threadpool(max_workers=4)
        
        # Explicit Ray
        runner = BatchTestRunnerFactory.create_ray(config)
        
        # For testing
        runner = BatchTestRunnerFactory.create_for_testing()
    """
    
    @staticmethod
    def create(config: Optional[WTBConfig] = None) -> IBatchTestRunner:
        """
        Create batch test runner based on configuration.
        
        Selects Ray if ray_enabled=True in config, otherwise ThreadPool.
        
        Args:
            config: WTB configuration (uses global config if None)
            
        Returns:
            IBatchTestRunner implementation
        """
        if config is None:
            config = get_config()
        
        # Check if Ray is enabled and available
        ray_enabled = getattr(config, 'ray_enabled', False)
        ray_config = getattr(config, 'ray_config', None)
        
        if ray_enabled and ray_config is not None:
            return BatchTestRunnerFactory.create_ray(config)
        else:
            return BatchTestRunnerFactory.create_threadpool(config)
    
    @staticmethod
    def create_threadpool(
        config: Optional[WTBConfig] = None,
        max_workers: int = 4,
        execution_timeout_seconds: float = 300.0,
    ) -> IBatchTestRunner:
        """
        Create ThreadPool-based batch test runner.
        
        Args:
            config: WTB configuration for UoW and StateAdapter factories
            max_workers: Maximum concurrent workers
            execution_timeout_seconds: Timeout per variant execution
            
        Returns:
            ThreadPoolBatchTestRunner instance
        """
        from .services.batch_test_runner import ThreadPoolBatchTestRunner
        
        if config is None:
            config = get_config()
        
        # Create factory functions for isolated dependencies
        def uow_factory() -> IUnitOfWork:
            return UnitOfWorkFactory.create(
                mode=config.wtb_storage_mode,
                db_url=config.wtb_db_url,
            )
        
        def state_adapter_factory() -> IStateAdapter:
            if config.state_adapter_mode == "inmemory":
                return InMemoryStateAdapter()
            else:
                try:
                    from wtb.infrastructure.adapters import AgentGitStateAdapter
                    return AgentGitStateAdapter(
                        agentgit_db_path=config.agentgit_db_path,
                        wtb_db_url=config.wtb_db_url,
                    )
                except ImportError:
                    return InMemoryStateAdapter()
        
        return ThreadPoolBatchTestRunner(
            uow_factory=uow_factory,
            state_adapter_factory=state_adapter_factory,
            max_workers=max_workers,
            execution_timeout_seconds=execution_timeout_seconds,
        )
    
    @staticmethod
    def create_ray(config: Optional[WTBConfig] = None) -> IBatchTestRunner:
        """
        Create Ray-based batch test runner.
        
        Args:
            config: WTB configuration with ray_config
            
        Returns:
            RayBatchTestRunner instance
            
        Raises:
            ImportError: If Ray is not installed
        """
        from .services.ray_batch_runner import RayBatchTestRunner, RayConfig
        
        if config is None:
            config = get_config()
        
        ray_config = getattr(config, 'ray_config', None)
        if ray_config is None:
            ray_config = RayConfig.for_local_development()
        
        return RayBatchTestRunner(
            config=ray_config,
            agentgit_db_url=config.agentgit_db_path,
            wtb_db_url=config.wtb_db_url or f"sqlite:///{config.data_dir}/wtb.db",
        )
    
    @staticmethod
    def create_for_testing(max_workers: int = 2) -> IBatchTestRunner:
        """
        Create batch test runner for unit tests.
        
        Uses in-memory storage for speed and isolation.
        
        Args:
            max_workers: Maximum concurrent workers
            
        Returns:
            ThreadPoolBatchTestRunner with in-memory dependencies
        """
        from .services.batch_test_runner import ThreadPoolBatchTestRunner
        
        return ThreadPoolBatchTestRunner(
            uow_factory=lambda: InMemoryUnitOfWork(),
            state_adapter_factory=lambda: InMemoryStateAdapter(),
            max_workers=max_workers,
            execution_timeout_seconds=60.0,
        )

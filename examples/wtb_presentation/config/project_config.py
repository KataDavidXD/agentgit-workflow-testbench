"""
WorkflowProject Configuration for WTB Presentation Demo.

Defines the main WorkflowProject instances with:
- File tracking configuration
- Environment (venv) configuration
- Execution (Ray) configuration
- Workspace isolation

This is the central configuration that ties together all other configs.

Usage:
    from config.project_config import create_demo_project, DEMO_DATA_DIR
    
    project = create_demo_project()
    wtb = WTBTestBench.create(mode="development", data_dir=DEMO_DATA_DIR)
    wtb.register_project(project)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Import from WTB SDK
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from wtb.sdk import (
    WorkflowProject,
    FileTrackingConfig,
    EnvironmentConfig,
    ExecutionConfig,
    EnvSpec,
    RayConfig,
    WorkspaceIsolationConfig,
    PauseStrategyConfig,
)

# Local config imports
from .venv_specs import NODE_ENVIRONMENTS
from .ray_resources import NODE_RESOURCES, DEFAULT_NODE_RESOURCES, DEFAULT_RAY_CONFIG


# ═══════════════════════════════════════════════════════════════════════════════
# Path Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Base paths
PRESENTATION_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = PRESENTATION_DIR / "workspace"
DEMO_DATA_DIR = PRESENTATION_DIR / "data"

# Workspace subdirectories
DOCUMENTS_DIR = WORKSPACE_DIR / "documents"
SQL_DIR = WORKSPACE_DIR / "sql"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
EMBEDDINGS_DIR = WORKSPACE_DIR / "embeddings"


# ═══════════════════════════════════════════════════════════════════════════════
# Project Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════

def create_demo_project(
    name: str = "wtb_presentation_demo",
    enable_file_tracking: bool = True,
    enable_venv_isolation: bool = False,
    enable_ray: bool = True,
    data_dir: Optional[Path] = None,
    uv_manager_url: Optional[str] = None,
) -> WorkflowProject:
    """
    Create the main demo WorkflowProject with all features configured.
    
    This is the primary project for the presentation demo, featuring:
    - Unified graph (RAG + SQL)
    - File tracking for rollback/branch demos
    - Optional per-node venv isolation (with REAL UV Venv Manager service)
    - Ray distributed execution
    
    Args:
        name: Project name
        enable_file_tracking: Enable file system tracking
        enable_venv_isolation: Enable per-node virtual environments
        enable_ray: Enable Ray distributed execution
        data_dir: Data directory for persistence
        uv_manager_url: URL for UV Venv Manager service (e.g., "http://localhost:10900")
                        If None and venv_isolation is enabled, uses current environment
        
    Returns:
        Configured WorkflowProject instance
        
    Example:
        # With REAL venv service:
        project = create_demo_project(
            enable_venv_isolation=True,
            uv_manager_url="http://localhost:10900"
        )
        
        # Without venv service:
        project = create_demo_project()
        wtb = WTBTestBench.create(mode="development")
        wtb.register_project(project)
        execution = wtb.run(project=project.name, initial_state={"query": "..."})
    """
    # Import graph factory
    from examples.wtb_presentation.graphs.unified_graph import create_unified_graph
    
    # File tracking configuration
    file_tracking = FileTrackingConfig(
        enabled=enable_file_tracking,
        tracked_paths=[
            str(OUTPUTS_DIR),
            str(EMBEDDINGS_DIR),
        ],
        ignore_patterns=[
            "*.pyc",
            "__pycache__/",
            "*.log",
            ".git/",
            "*.tmp",
        ],
        auto_commit=True,
        commit_on="checkpoint",
        repository_path=str(data_dir / "filetracker") if data_dir else None,
        snapshot_strategy="incremental",
        max_snapshots=100,
    )
    
    # Environment configuration
    # Use REAL UV Venv Manager service when uv_manager_url is provided
    environment = EnvironmentConfig(
        granularity="node" if enable_venv_isolation else "workflow",
        use_current_env=not enable_venv_isolation and uv_manager_url is None,
        default_env=EnvSpec(
            python_version="3.12",
            dependencies=[
                "langgraph>=0.2.0",
                "langchain-core>=0.1.0",
            ],
        ),
        node_environments=NODE_ENVIRONMENTS if enable_venv_isolation else {},
        reuse_existing=True,
        cleanup_on_exit=False,
        uv_manager_url=uv_manager_url,  # REAL venv service URL
    )
    
    # Execution configuration
    execution = ExecutionConfig(
        batch_executor="ray" if enable_ray else "sequential",
        ray_config=DEFAULT_RAY_CONFIG,
        node_resources=NODE_RESOURCES if enable_ray else {},
        default_node_resources=DEFAULT_NODE_RESOURCES,
        checkpoint_strategy="per_node",
        checkpoint_storage="sqlite",
        default_timeout=300,
    )
    
    # Workspace isolation (copy mode for demo)
    workspace_isolation = WorkspaceIsolationConfig(
        enabled=False,  # Disabled for demo visibility
        mode="copy",
        base_path=str(WORKSPACE_DIR),
        cleanup_on_complete=False,
    )
    
    # Pause strategy
    pause_strategy = PauseStrategyConfig(
        mode="before_node",
        timeout=None,  # No timeout for demo
        auto_resume=False,
    )
    
    return WorkflowProject(
        name=name,
        graph_factory=create_unified_graph,
        description="WTB Presentation Demo - Unified RAG + SQL workflow",
        file_tracking=file_tracking,
        environment=environment,
        execution=execution,
        workspace_isolation=workspace_isolation,
        pause_strategy=pause_strategy,
    )


def create_rag_project(
    name: str = "rag_pipeline_demo",
    enable_file_tracking: bool = True,
) -> WorkflowProject:
    """
    Create a RAG-only project (no SQL agent).
    
    Simpler project for demonstrating RAG pipeline features.
    
    Args:
        name: Project name
        enable_file_tracking: Enable file tracking
        
    Returns:
        RAG-only WorkflowProject
    """
    from examples.wtb_presentation.graphs.unified_graph import create_rag_only_graph
    
    return WorkflowProject(
        name=name,
        graph_factory=create_rag_only_graph,
        description="RAG Pipeline Demo - Document retrieval and generation",
        file_tracking=FileTrackingConfig(
            enabled=enable_file_tracking,
            tracked_paths=[str(OUTPUTS_DIR)],
            commit_on="checkpoint",
        ),
        execution=ExecutionConfig(
            batch_executor="sequential",
            checkpoint_strategy="per_node",
        ),
    )


def create_sql_project(name: str = "sql_agent_demo") -> WorkflowProject:
    """
    Create a SQL-only project.
    
    Minimal project for demonstrating SQL agent capabilities.
    
    Args:
        name: Project name
        
    Returns:
        SQL-only WorkflowProject
    """
    from examples.wtb_presentation.graphs.unified_graph import create_sql_only_graph
    
    return WorkflowProject(
        name=name,
        graph_factory=create_sql_only_graph,
        description="SQL Agent Demo - Database query processing",
        file_tracking=FileTrackingConfig(
            enabled=True,
            tracked_paths=[str(OUTPUTS_DIR)],
        ),
    )


def create_batch_test_project(
    name: str = "batch_test_demo",
    enable_ray: bool = True,
) -> WorkflowProject:
    """
    Create a project optimized for batch testing with REAL infrastructure.
    
    Configured for running multiple test cases with variant matrix.
    Uses SQLite for checkpoint persistence and optionally Ray for parallel execution.
    
    Args:
        name: Project name
        enable_ray: Enable Ray distributed execution (requires Ray cluster)
        
    Returns:
        WorkflowProject configured for batch testing
    """
    from examples.wtb_presentation.graphs.unified_graph import create_rag_only_graph
    
    return WorkflowProject(
        name=name,
        graph_factory=create_rag_only_graph,
        description="Batch Test Demo - Variant matrix testing with REAL infrastructure",
        execution=ExecutionConfig(
            batch_executor="ray" if enable_ray else "sequential",
            ray_config=RayConfig(
                address="auto",  # Auto-connect to local Ray cluster
                max_concurrent_workflows=4,
                max_retries=2,
            ),
            checkpoint_strategy="per_node",
            checkpoint_storage="sqlite",  # REAL SQLite persistence
        ),
    )


def create_venv_demo_project(
    name: str = "venv_demo",
    uv_manager_url: str = "http://localhost:10900",
) -> WorkflowProject:
    """
    Create a project demonstrating per-node venv isolation with REAL UV Venv Manager.
    
    Each node runs in its own virtual environment with
    node-specific dependencies, managed by the UV Venv Manager service.
    
    Args:
        name: Project name
        uv_manager_url: URL for UV Venv Manager service (default: "http://localhost:10900")
        
    Returns:
        WorkflowProject with per-node venv isolation
        
    Prerequisites:
        Start UV Venv Manager service:
        cd uv_venv_manager && python -m uvicorn src.api:create_app --port 10900 --factory
    """
    from examples.wtb_presentation.graphs.unified_graph import create_unified_graph
    
    return WorkflowProject(
        name=name,
        graph_factory=create_unified_graph,
        description="Venv Demo - Per-node environment isolation with REAL UV Venv Manager",
        environment=EnvironmentConfig(
            granularity="node",
            use_current_env=False,
            node_environments=NODE_ENVIRONMENTS,
            reuse_existing=True,
            cleanup_on_exit=False,
            uv_manager_url=uv_manager_url,  # REAL venv service
        ),
        execution=ExecutionConfig(
            batch_executor="ray",
            node_resources=NODE_RESOURCES,
            checkpoint_storage="sqlite",  # REAL checkpoint persistence
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_workspace_dirs() -> None:
    """
    Ensure all workspace directories exist.
    
    Creates the directory structure if it doesn't exist.
    """
    for dir_path in [DOCUMENTS_DIR, SQL_DIR, OUTPUTS_DIR, EMBEDDINGS_DIR, DEMO_DATA_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


def get_project_summary(project: WorkflowProject) -> dict:
    """
    Get a summary of project configuration.
    
    Args:
        project: WorkflowProject instance
        
    Returns:
        Dictionary with configuration summary
    """
    return {
        "name": project.name,
        "description": project.description,
        "file_tracking_enabled": project.file_tracking.enabled,
        "environment_granularity": project.environment.granularity,
        "batch_executor": project.execution.batch_executor,
        "checkpoint_strategy": project.execution.checkpoint_strategy,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Factory functions
    "create_demo_project",
    "create_rag_project",
    "create_sql_project",
    "create_batch_test_project",
    "create_venv_demo_project",
    # Path constants
    "PRESENTATION_DIR",
    "WORKSPACE_DIR",
    "DEMO_DATA_DIR",
    "DOCUMENTS_DIR",
    "SQL_DIR",
    "OUTPUTS_DIR",
    "EMBEDDINGS_DIR",
    # Helpers
    "ensure_workspace_dirs",
    "get_project_summary",
]

"""
Configuration for WTB Presentation Demo.

Contains:
- project_config: WorkflowProject definitions
- venv_specs: Per-node environment specifications
- ray_resources: Per-node Ray resource allocations
- variants: Node variant definitions
"""

from .project_config import (
    create_demo_project,
    create_rag_project,
    DEMO_DATA_DIR,
    WORKSPACE_DIR,
)
from .venv_specs import NODE_ENVIRONMENTS, get_env_for_node
from .ray_resources import NODE_RESOURCES, get_resources_for_node
from .variants import register_all_variants

__all__ = [
    "create_demo_project",
    "create_rag_project",
    "DEMO_DATA_DIR",
    "WORKSPACE_DIR",
    "NODE_ENVIRONMENTS",
    "get_env_for_node",
    "NODE_RESOURCES",
    "get_resources_for_node",
    "register_all_variants",
]

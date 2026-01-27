# Workflow Submission Design

> **Document Version**: 1.0  
> **Created**: 2026-01-15  
> **Status**: Design Discussion  
> **Author**: Senior Architect

---

## 1. Executive Summary

本文档定义用户如何将 LangGraph workflow 提交给 WTB (Workflow Test Bench) 系统进行测试、调试和批量执行。

### 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 提交方式 | **SDK Registration** | 原生 Python，类型安全，IDE 支持 |
| Variant 颗粒度 | **Workflow + Node** | 支持架构对比 + 组件 A/B 测试 |
| Environment 颗粒度 | **Workflow + Node + Variant** | 灵活的依赖隔离 |
| Ray 资源分配 | **Node 级分配，Workflow 级集成** | 精细资源控制 + 整体调度 |
| 默认执行器 | **Ray** | 更好的 CPU/进程/线程资源管理 |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     WORKFLOW SUBMISSION ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  User Code Space                                                                 │
│  ═══════════════                                                                 │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  WorkflowProject                                                         │   │
│  │  ├── Workflow Definition (Graph + State Schema)                         │   │
│  │  ├── Workflow Variants (Alternative Graph Structures)                   │   │
│  │  ├── Node Variants (Alternative Node Implementations)                   │   │
│  │  ├── File Tracking Config (FileTracker Integration)                     │   │
│  │  ├── Environment Config (UV Venv Manager Integration)                   │   │
│  │  └── Execution Config (Ray Resource Allocation)                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                         │
│                                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        WTBTestBench                                      │   │
│  │                                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │   │
│  │  │  Project     │  │  Execution   │  │  Results     │                   │   │
│  │  │  Registry    │  │  Engine      │  │  Collector   │                   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                         │
│                                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    INFRASTRUCTURE LAYER                                  │   │
│  │                                                                          │   │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐        │   │
│  │  │   FileTracker   │   │  UV Venv Mgr    │   │      Ray        │        │   │
│  │  │                 │   │                 │   │                 │        │   │
│  │  │  • Track files  │   │  • Create env   │   │  • Distribute   │        │   │
│  │  │  • Snapshot     │   │  • Install deps │   │  • Parallelize  │        │   │
│  │  │  • Commit       │   │  • Isolate      │   │  • Scale        │        │   │
│  │  │  • Rollback     │   │  • Audit        │   │  • Object Store │        │   │
│  │  └─────────────────┘   └─────────────────┘   └─────────────────┘        │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. WorkflowProject - Core Configuration Object

### 3.1 Complete Example

```python
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel
from wtb import WorkflowProject, WTBTestBench
from wtb.config import (
    FileTrackingConfig, 
    EnvironmentConfig, 
    ExecutionConfig,
    RayConfig,
    NodeResourceConfig,
)

# ════════════════════════════════════════════════════════════════════════════════
# Step 1: Define LangGraph Workflow
# ════════════════════════════════════════════════════════════════════════════════

class RAGState(BaseModel):
    query: str
    documents: list[str] = []
    answer: str = ""

def retriever(state: RAGState) -> dict:
    return {"documents": ["doc1", "doc2"]}

def generator(state: RAGState) -> dict:
    return {"answer": f"Answer based on {state.documents}"}

def create_rag_graph():
    graph = StateGraph(RAGState)
    graph.add_node("retriever", retriever)
    graph.add_node("generator", generator)
    graph.add_edge(START, "retriever")
    graph.add_edge("retriever", "generator")
    graph.add_edge("generator", END)
    return graph.compile()


# ════════════════════════════════════════════════════════════════════════════════
# Step 2: Create WorkflowProject with Full Configuration
# ════════════════════════════════════════════════════════════════════════════════

project = WorkflowProject(
    name="rag_pipeline",
    description="RAG Pipeline for Q&A",
    
    # ─────────────────────────────────────────────────────────────────────────
    # Workflow Definition
    # ─────────────────────────────────────────────────────────────────────────
    graph_factory=create_rag_graph,
    state_schema=RAGState,
    
    # ─────────────────────────────────────────────────────────────────────────
    # File Tracking Configuration
    # ─────────────────────────────────────────────────────────────────────────
    file_tracking=FileTrackingConfig(
        enabled=True,
        tracked_paths=["./data/", "./outputs/"],
        ignore_patterns=["*.pyc", "__pycache__/", "*.log"],
        auto_commit=True,
        commit_on="checkpoint",  # "checkpoint" | "node_complete" | "manual"
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # Environment Configuration (3 Granularities)
    # ─────────────────────────────────────────────────────────────────────────
    environment=EnvironmentConfig(
        # Granularity: "workflow" | "node" | "variant"
        granularity="node",
        
        # Default environment (workflow level)
        default_env=EnvSpec(
            python_version="3.12",
            dependencies=["langchain>=0.1.0"],
        ),
        
        # Node-specific environments
        node_environments={
            "retriever": EnvSpec(
                dependencies=["faiss-cpu>=1.7", "sentence-transformers"],
            ),
            "generator": EnvSpec(
                dependencies=["openai>=1.0", "tiktoken"],
            ),
        },
        
        # Variant-specific environments (for dependency version testing)
        variant_environments={
            "retriever:bm25_retriever": EnvSpec(
                dependencies=["rank-bm25>=0.2"],
            ),
        },
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # Execution Configuration (Ray with Node-level Resources)
    # ─────────────────────────────────────────────────────────────────────────
    execution=ExecutionConfig(
        # Default executor
        batch_executor="ray",  # "ray" | "threadpool" | "sequential"
        
        # Workflow-level Ray integration
        ray_config=RayConfig(
            address="auto",
            max_concurrent_workflows=10,
            object_store_memory=2 * 1024 * 1024 * 1024,  # 2GB
        ),
        
        # Node-level resource allocation
        node_resources={
            "retriever": NodeResourceConfig(
                num_cpus=2,
                num_gpus=0,
                memory="2GB",
            ),
            "generator": NodeResourceConfig(
                num_cpus=1,
                num_gpus=1,  # GPU for LLM inference
                memory="8GB",
            ),
            "reranker": NodeResourceConfig(
                num_cpus=4,
                num_gpus=0,
                memory="4GB",
            ),
        },
        
        # Default for nodes without explicit config
        default_node_resources=NodeResourceConfig(
            num_cpus=1,
            num_gpus=0,
            memory="1GB",
        ),
    ),
)


# ════════════════════════════════════════════════════════════════════════════════
# Step 3: Register Variants (2 Granularities)
# ════════════════════════════════════════════════════════════════════════════════

# ─── Node-Level Variants (Component A/B Testing) ───

project.register_variant(
    node="retriever",
    name="bm25_retriever",
    implementation=bm25_retriever_func,
    description="BM25-based sparse retriever",
)

project.register_variant(
    node="retriever",
    name="hybrid_retriever",
    implementation=hybrid_retriever_func,
    description="Hybrid dense + sparse retriever",
)

project.register_variant(
    node="generator",
    name="gpt4_generator",
    implementation=gpt4_generator_func,
    description="GPT-4 based generator",
)

# ─── Workflow-Level Variants (Architecture Comparison) ───

def create_rag_with_reranker():
    """V2: Added reranker node"""
    graph = StateGraph(RAGState)
    graph.add_node("retriever", retriever)
    graph.add_node("reranker", reranker_func)
    graph.add_node("generator", generator)
    graph.add_edge(START, "retriever")
    graph.add_edge("retriever", "reranker")
    graph.add_edge("reranker", "generator")
    graph.add_edge("generator", END)
    return graph.compile()

project.register_workflow_variant(
    name="rag_with_reranker",
    graph_factory=create_rag_with_reranker,
    description="RAG pipeline with reranker for better relevance",
)


# ════════════════════════════════════════════════════════════════════════════════
# Step 4: Register to WTB and Run Tests
# ════════════════════════════════════════════════════════════════════════════════

wtb = WTBTestBench()
wtb.register_project(project)

# Single run
result = wtb.run(
    project="rag_pipeline",
    initial_state={"query": "What is LangGraph?"},
)

# Batch test with variant matrix
batch_result = wtb.run_batch_test(
    project="rag_pipeline",
    variant_matrix=[
        # Test different node combinations
        {"retriever": "default", "generator": "default"},
        {"retriever": "bm25_retriever", "generator": "default"},
        {"retriever": "hybrid_retriever", "generator": "gpt4_generator"},
        # Test workflow variants
        {"_workflow": "rag_with_reranker", "generator": "default"},
    ],
    test_cases=[
        {"query": "What is LangGraph?"},
        {"query": "How does RAG work?"},
        {"query": "Explain vector search"},
    ],
)
```

---

## 4. Configuration Objects Specification

### 4.1 FileTrackingConfig

```python
@dataclass
class FileTrackingConfig:
    """FileTracker integration configuration"""
    
    # Enable/disable file tracking
    enabled: bool = False
    
    # Paths to track (relative to project root)
    tracked_paths: List[str] = field(default_factory=list)
    
    # Ignore patterns (gitignore style)
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.pyc", "__pycache__/", "*.log", ".git/", "*.tmp"
    ])
    
    # Auto-commit strategy
    auto_commit: bool = True
    commit_on: Literal["checkpoint", "node_complete", "manual"] = "checkpoint"
    
    # Storage location
    repository_path: Optional[str] = None  # None = auto in project dir
    
    # Snapshot strategy
    snapshot_strategy: Literal["full", "incremental"] = "incremental"
    max_snapshots: int = 100
```

### 4.2 EnvironmentConfig (3 Granularities)

```python
@dataclass
class EnvSpec:
    """Environment specification"""
    python_version: str = "3.12"
    dependencies: List[str] = field(default_factory=list)
    requirements_file: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class EnvironmentConfig:
    """UV Venv Manager integration configuration"""
    
    # Granularity: workflow | node | variant
    granularity: Literal["workflow", "node", "variant"] = "workflow"
    
    # Use current environment (skip isolation)
    use_current_env: bool = False
    
    # Default environment (workflow level)
    default_env: Optional[EnvSpec] = None
    
    # Node-specific environments (node level)
    # Key: node_id
    node_environments: Dict[str, EnvSpec] = field(default_factory=dict)
    
    # Variant-specific environments (variant level)
    # Key: "node_id:variant_name" or "_workflow:variant_name"
    variant_environments: Dict[str, EnvSpec] = field(default_factory=dict)
    
    # Environment management
    reuse_existing: bool = True
    cleanup_on_exit: bool = False
    
    # UV Venv Manager connection
    uv_manager_url: Optional[str] = None  # None = embedded mode
```

### 4.3 ExecutionConfig (Ray with Node-level Resources)

```python
@dataclass
class NodeResourceConfig:
    """Per-node Ray resource allocation"""
    num_cpus: float = 1.0
    num_gpus: float = 0.0
    memory: str = "1GB"  # Parsed to bytes
    
    # Custom resources
    custom_resources: Dict[str, float] = field(default_factory=dict)


@dataclass
class RayConfig:
    """Ray cluster configuration (Workflow-level integration)"""
    
    # Connection
    address: str = "auto"  # "auto" | "local" | "ray://host:port"
    
    # Workflow-level concurrency
    max_concurrent_workflows: int = 10
    
    # Object store
    object_store_memory: Optional[int] = None  # bytes
    
    # Fault tolerance
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class ExecutionConfig:
    """Execution configuration"""
    
    # Executor selection
    batch_executor: Literal["ray", "threadpool", "sequential"] = "ray"
    
    # Ray configuration (workflow-level)
    ray_config: RayConfig = field(default_factory=RayConfig)
    
    # Node-level resource allocation
    node_resources: Dict[str, NodeResourceConfig] = field(default_factory=dict)
    default_node_resources: NodeResourceConfig = field(
        default_factory=NodeResourceConfig
    )
    
    # Checkpoint strategy
    checkpoint_strategy: Literal["per_node", "per_step", "manual"] = "per_node"
    checkpoint_storage: Literal["memory", "sqlite", "postgres"] = "sqlite"
    
    # Timeout
    default_timeout: int = 300  # seconds
```

---

## 5. Variant System Design

### 5.1 Two Granularities

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        VARIANT GRANULARITIES                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Granularity 1: NODE-LEVEL VARIANT                                              │
│  ═════════════════════════════════                                               │
│                                                                                  │
│  Purpose: A/B test individual components                                         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Workflow: rag_pipeline                                                  │   │
│  │                                                                          │   │
│  │  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │   │
│  │  │  retriever   │ ───► │   reranker   │ ───► │  generator   │           │   │
│  │  └──────────────┘      └──────────────┘      └──────────────┘           │   │
│  │         │                                            │                   │   │
│  │         ▼                                            ▼                   │   │
│  │  ┌────────────────────┐                    ┌────────────────────┐       │   │
│  │  │ Variants:          │                    │ Variants:          │       │   │
│  │  │ • default          │                    │ • default          │       │   │
│  │  │ • bm25_retriever   │                    │ • gpt4_generator   │       │   │
│  │  │ • hybrid_retriever │                    │ • claude_generator │       │   │
│  │  └────────────────────┘                    └────────────────────┘       │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  API:                                                                            │
│  project.register_variant(node="retriever", name="bm25", impl=func)             │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Granularity 2: WORKFLOW-LEVEL VARIANT                                          │
│  ═════════════════════════════════════                                           │
│                                                                                  │
│  Purpose: Compare different architectures                                        │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  Variant A: rag_pipeline (default)                                       │   │
│  │  ┌──────────────┐      ┌──────────────┐                                  │   │
│  │  │  retriever   │ ───► │  generator   │                                  │   │
│  │  └──────────────┘      └──────────────┘                                  │   │
│  │                                                                          │   │
│  │  Variant B: rag_with_reranker                                            │   │
│  │  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │   │
│  │  │  retriever   │ ───► │   reranker   │ ───► │  generator   │           │   │
│  │  └──────────────┘      └──────────────┘      └──────────────┘           │   │
│  │                                                                          │   │
│  │  Variant C: rag_with_query_expansion                                     │   │
│  │  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │   │
│  │  │  expander    │ ───► │  retriever   │ ───► │  generator   │           │   │
│  │  └──────────────┘      └──────────────┘      └──────────────┘           │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  API:                                                                            │
│  project.register_workflow_variant(name="with_reranker", graph_factory=func)    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Variant Operations API

```python
class WorkflowProject:
    """Workflow Project with variant management"""
    
    # ─── Node-Level Variants ───
    
    def register_variant(
        self,
        node: str,
        name: str,
        implementation: Callable,
        description: str = "",
        environment: Optional[EnvSpec] = None,  # Variant-specific env
        resources: Optional[NodeResourceConfig] = None,  # Variant-specific resources
    ) -> None:
        """Register a node-level variant for A/B testing"""
        ...
    
    def list_variants(self, node: Optional[str] = None) -> Dict[str, List[str]]:
        """List all registered variants, optionally filtered by node"""
        ...
    
    def remove_variant(self, node: str, name: str) -> None:
        """Remove a registered variant"""
        ...
    
    # ─── Workflow-Level Variants ───
    
    def register_workflow_variant(
        self,
        name: str,
        graph_factory: Callable[[], CompiledStateGraph],
        description: str = "",
        state_schema: Optional[Type[BaseModel]] = None,  # If different from default
    ) -> None:
        """Register a workflow-level variant for architecture comparison"""
        ...
    
    def list_workflow_variants(self) -> List[str]:
        """List all registered workflow variants"""
        ...
    
    def remove_workflow_variant(self, name: str) -> None:
        """Remove a registered workflow variant"""
        ...
    
    # ─── Node Updates (Permanent) ───
    
    def update_node(
        self,
        node: str,
        new_implementation: Callable,
        reason: str = "",
    ) -> None:
        """
        Permanently update a node implementation.
        Creates a new version, preserves history for rollback.
        """
        ...
    
    # ─── Workflow Updates (Permanent) ───
    
    def update_workflow(
        self,
        graph_factory: Callable[[], CompiledStateGraph],
        version: str,
        changelog: str = "",
    ) -> None:
        """
        Update the main workflow graph structure.
        Creates a new major version.
        """
        ...
```

---

## 6. Ray Resource Allocation Model

### 6.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    RAY RESOURCE ALLOCATION MODEL                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  WORKFLOW LEVEL (Logical Integration)                                            │
│  ════════════════════════════════════                                            │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  RayConfig (Workflow-level)                                              │   │
│  │  • address: "auto" | "ray://cluster:port"                               │   │
│  │  • max_concurrent_workflows: 10                                         │   │
│  │  • object_store_memory: 2GB                                             │   │
│  │  • max_retries: 3                                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                         │
│                            Orchestrates │                                        │
│                                        ▼                                         │
│  NODE LEVEL (Resource Allocation)                                                │
│  ════════════════════════════════                                                │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │   node_resources = {                                                     │   │
│  │       "retriever": NodeResourceConfig(                                   │   │
│  │           num_cpus=2,                                                    │   │
│  │           num_gpus=0,                                                    │   │
│  │           memory="2GB",                                                  │   │
│  │       ),                                                                 │   │
│  │       "generator": NodeResourceConfig(                                   │   │
│  │           num_cpus=1,                                                    │   │
│  │           num_gpus=1,      # GPU for LLM                                │   │
│  │           memory="8GB",                                                  │   │
│  │       ),                                                                 │   │
│  │   }                                                                      │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                         │
│                                        ▼                                         │
│  EXECUTION (Ray Scheduler Manages Resources)                                     │
│  ═══════════════════════════════════════════                                     │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │   Ray Cluster Resources: 16 CPU, 4 GPU, 64GB Memory                     │   │
│  │                                                                          │   │
│  │   Workflow 1 ─┬─ retriever (2 CPU) ─► generator (1 CPU, 1 GPU)          │   │
│  │               │                                                          │   │
│  │   Workflow 2 ─┼─ retriever (2 CPU) ─► generator (1 CPU, 1 GPU)          │   │
│  │               │                                                          │   │
│  │   Workflow 3 ─┼─ retriever (2 CPU) ─► generator (1 CPU, 1 GPU)          │   │
│  │               │                                                          │   │
│  │   Workflow 4 ─┴─ [QUEUED - waiting for GPU]                             │   │
│  │                                                                          │   │
│  │   Ray Scheduler:                                                         │   │
│  │   • Respects node resource requirements                                 │   │
│  │   • Queues tasks when resources unavailable                             │   │
│  │   • Optimizes placement for data locality                               │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Ray Task Generation

```python
# Internal WTB implementation

@ray.remote
def execute_node(
    node_id: str,
    node_func: Callable,
    state: dict,
    resources: NodeResourceConfig,
) -> dict:
    """Ray remote task for node execution"""
    return node_func(state)


class RayBatchRunner:
    """Executes batch tests using Ray"""
    
    def _create_node_task(
        self,
        node_id: str,
        node_func: Callable,
        state: dict,
    ) -> ray.ObjectRef:
        """Create Ray task with node-specific resources"""
        
        resources = self.execution_config.node_resources.get(
            node_id,
            self.execution_config.default_node_resources,
        )
        
        # Apply resource requirements to Ray task
        task = execute_node.options(
            num_cpus=resources.num_cpus,
            num_gpus=resources.num_gpus,
            memory=self._parse_memory(resources.memory),
            **resources.custom_resources,
        )
        
        return task.remote(node_id, node_func, state, resources)
```

---

## 7. Environment Granularity

### 7.1 Three Levels

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ENVIRONMENT GRANULARITY LEVELS                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Level 1: WORKFLOW GRANULARITY                                                   │
│  ═════════════════════════════                                                   │
│                                                                                  │
│  • One environment for entire workflow                                           │
│  • Simplest, least overhead                                                      │
│  • Use when all nodes share same dependencies                                    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Environment: rag_pipeline_env (Python 3.12)                            │   │
│  │  Dependencies: langchain, openai, faiss-cpu, tiktoken                   │   │
│  │                                                                          │   │
│  │  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │   │
│  │  │  retriever   │ ───► │   reranker   │ ───► │  generator   │           │   │
│  │  └──────────────┘      └──────────────┘      └──────────────┘           │   │
│  │         │                     │                     │                    │   │
│  │         └─────────────────────┴─────────────────────┘                    │   │
│  │                          Same Environment                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Level 2: NODE GRANULARITY                                                       │
│  ═════════════════════════                                                       │
│                                                                                  │
│  • Separate environment per node                                                 │
│  • Use for ML pipelines with conflicting dependencies                           │
│  • Higher isolation, more overhead                                              │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐                     │   │
│  │  │ retriever_env        │  │ generator_env        │                     │   │
│  │  │ • faiss-cpu          │  │ • openai             │                     │   │
│  │  │ • sentence-transform │  │ • tiktoken           │                     │   │
│  │  │                      │  │ • vllm (optional)    │                     │   │
│  │  │  ┌──────────────┐    │  │  ┌──────────────┐    │                     │   │
│  │  │  │  retriever   │────┼──┼─►│  generator   │    │                     │   │
│  │  │  └──────────────┘    │  │  └──────────────┘    │                     │   │
│  │  └──────────────────────┘  └──────────────────────┘                     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Level 3: VARIANT GRANULARITY                                                    │
│  ════════════════════════════                                                    │
│                                                                                  │
│  • Separate environment per variant                                              │
│  • Use for testing different dependency versions                                 │
│  • Highest isolation, highest overhead                                          │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  retriever node variants:                                                │   │
│  │                                                                          │   │
│  │  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐   │   │
│  │  │ default_env        │ │ bm25_env           │ │ hybrid_env         │   │   │
│  │  │ • faiss-cpu==1.7   │ │ • rank-bm25==0.2   │ │ • faiss-cpu==1.7   │   │   │
│  │  │                    │ │                    │ │ • rank-bm25==0.2   │   │   │
│  │  │ ┌────────────────┐ │ │ ┌────────────────┐ │ │ ┌────────────────┐ │   │   │
│  │  │ │ dense_retriever│ │ │ │ bm25_retriever │ │ │ │hybrid_retriever│ │   │   │
│  │  │ └────────────────┘ │ │ └────────────────┘ │ │ └────────────────┘ │   │   │
│  │  └────────────────────┘ └────────────────────┘ └────────────────────┘   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Configuration Example

```python
environment=EnvironmentConfig(
    granularity="variant",  # Most flexible
    
    default_env=EnvSpec(
        python_version="3.12",
        dependencies=["langchain>=0.1.0"],
    ),
    
    node_environments={
        "retriever": EnvSpec(dependencies=["faiss-cpu>=1.7"]),
        "generator": EnvSpec(dependencies=["openai>=1.0"]),
    },
    
    variant_environments={
        # Node variants
        "retriever:bm25_retriever": EnvSpec(
            dependencies=["rank-bm25>=0.2"],
        ),
        "retriever:hybrid_retriever": EnvSpec(
            dependencies=["faiss-cpu>=1.7", "rank-bm25>=0.2"],
        ),
        # Workflow variants
        "_workflow:rag_with_reranker": EnvSpec(
            dependencies=["sentence-transformers>=2.0"],
        ),
    },
)
```

---

## 8. Update Operations

### 8.1 Variant vs Update Comparison

| Operation | Purpose | Persistence | Versioning | Use Case |
|-----------|---------|-------------|------------|----------|
| `register_variant()` | A/B testing | Temporary | Branch | Compare implementations |
| `register_workflow_variant()` | Architecture comparison | Temporary | Branch | Compare structures |
| `update_node()` | Bug fix / Optimization | Permanent | New version | Improve component |
| `update_workflow()` | Structural change | Permanent | Major version | Add/remove nodes |

### 8.2 Update Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          UPDATE OPERATIONS FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  VARIANT (Temporary - A/B Testing)                                              │
│  ═════════════════════════════════                                               │
│                                                                                  │
│  ┌────────────────┐                                                             │
│  │ Original Graph │                                                             │
│  │   v1.0         │                                                             │
│  └───────┬────────┘                                                             │
│          │                                                                       │
│          ├──► [variant: bm25] ──► Execute ──► Compare Results                   │
│          │                                                                       │
│          ├──► [variant: hybrid] ──► Execute ──► Compare Results                 │
│          │                                                                       │
│          └──► [default] ──► Execute ──► Compare Results                         │
│                                                                                  │
│  (Original graph unchanged, variants are temporary branches)                     │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  UPDATE (Permanent - Version Control)                                            │
│  ════════════════════════════════════                                            │
│                                                                                  │
│  ┌────────────────┐      ┌────────────────┐      ┌────────────────┐             │
│  │ Original Graph │ ───► │  update_node() │ ───► │ Updated Graph  │             │
│  │   v1.0         │      │  retriever     │      │   v1.1         │             │
│  └────────────────┘      └────────────────┘      └────────────────┘             │
│          │                                               │                       │
│          │  (Preserved in version history)               │                       │
│          └───────────────────────────────────────────────┘                       │
│                                                                                  │
│  ┌────────────────┐      ┌───────────────────┐   ┌────────────────┐             │
│  │ Graph v1.1     │ ───► │ update_workflow() │ ─►│ Graph v2.0     │             │
│  │                │      │ Add reranker node │   │ + reranker     │             │
│  └────────────────┘      └───────────────────┘   └────────────────┘             │
│          │                                               │                       │
│          │  (Preserved in version history)               │                       │
│          └───────────────────────────────────────────────┘                       │
│                                                                                  │
│  Version History (AgentGit):                                                     │
│  • v1.0 → v1.1 → v2.0                                                           │
│  • Can rollback to any previous version                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. WTBTestBench Complete API

```python
class WTBTestBench:
    """Main entry point for WTB"""
    
    # ─── Project Management ───
    
    def register_project(self, project: WorkflowProject) -> None:
        """Register a workflow project"""
        ...
    
    def get_project(self, name: str) -> WorkflowProject:
        """Get a registered project"""
        ...
    
    def list_projects(self) -> List[str]:
        """List all registered projects"""
        ...
    
    # ─── Execution ───
    
    def run(
        self,
        project: str,
        initial_state: dict,
        variant_config: Optional[Dict[str, str]] = None,  # {node: variant}
        workflow_variant: Optional[str] = None,  # Use workflow variant
    ) -> ExecutionResult:
        """Run a single workflow execution"""
        ...
    
    def run_batch_test(
        self,
        project: str,
        variant_matrix: List[Dict[str, str]],
        test_cases: List[dict],
        parallelism: Optional[int] = None,  # None = use Ray config
    ) -> BatchTestResult:
        """Run batch tests with variant combinations"""
        ...
    
    # ─── Control ───
    
    def pause(self, execution_id: str) -> None:
        """Pause a running execution"""
        ...
    
    def resume(self, execution_id: str) -> None:
        """Resume a paused execution"""
        ...
    
    def rollback(self, execution_id: str, checkpoint_id: str) -> None:
        """Rollback to a previous checkpoint"""
        ...
    
    # ─── Inspection ───
    
    def get_state(self, execution_id: str) -> dict:
        """Get current state of an execution"""
        ...
    
    def get_checkpoints(self, execution_id: str) -> List[Checkpoint]:
        """Get all checkpoints for an execution"""
        ...
    
    def get_file_snapshots(self, execution_id: str) -> List[FileSnapshot]:
        """Get file tracking snapshots"""
        ...
```

---

## 10. Summary

### Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Submission Method | SDK Registration | Native Python, type-safe, IDE support |
| Variant Granularity | Workflow + Node | Support both architecture and component testing |
| Environment Granularity | Workflow + Node + Variant | Flexible dependency isolation |
| Ray Resources | Node-level allocation, Workflow-level integration | Fine resource control with unified orchestration |
| Default Executor | Ray | Better CPU/process/thread resource management |

### Integration Points

| Component | Integration |
|-----------|-------------|
| FileTracker | Auto-snapshot on checkpoint, rollback support |
| UV Venv Manager | Environment creation at configured granularity |
| Ray | Distributed execution with per-node resources |
| AgentGit | State versioning, time-travel |
| OpenTelemetry | Distributed tracing across Ray workers |

---

## Appendix A: Alternative Submission Methods

For CI/CD scenarios where SDK registration is not possible:

### A.1 Module Path Import

```python
# Submit via API (Server Mode)
POST /api/v1/projects
{
    "name": "rag_pipeline",
    "module_path": "myapp.workflows:create_rag_graph",
    "state_schema_path": "myapp.schemas:RAGState",
    "dependencies": ["langchain>=0.1.0", "openai>=1.0"],
}
```

### A.2 Configuration File

```yaml
# wtb_project.yaml
name: rag_pipeline
description: RAG Pipeline for Q&A

workflow:
  module: myapp.workflows
  factory: create_rag_graph
  state_schema: myapp.schemas.RAGState

variants:
  nodes:
    retriever:
      - name: bm25_retriever
        module: myapp.retrievers
        function: bm25_retriever
  workflows:
    - name: rag_with_reranker
      module: myapp.workflows
      factory: create_rag_with_reranker

file_tracking:
  enabled: true
  paths:
    - ./data/
    - ./outputs/

environment:
  granularity: node
  default:
    python: "3.12"
    dependencies:
      - langchain>=0.1.0

execution:
  batch_executor: ray
  ray:
    address: auto
  node_resources:
    retriever:
      num_cpus: 2
    generator:
      num_cpus: 1
      num_gpus: 1
```

```python
# Load from config
wtb = WTBTestBench()
project = WorkflowProject.from_yaml("wtb_project.yaml")
wtb.register_project(project)
```

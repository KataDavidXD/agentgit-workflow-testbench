# WTB Integration Architecture Summary

**Created:** 2026-01-28  
**Purpose:** Explain how File System, Ray, and UV Venv Manager integrate

---

## 1. 架构概览 (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           WTB (Workflow Test Bench)                                 │
│                           主项目 (Main Project)                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────┐      ┌─────────────────────┐      ┌──────────────────────┐│
│   │  wtb/domain/        │      │  wtb/application/   │      │  wtb/infrastructure/ ││
│   │  - 领域模型          │◀────▶│  - ExecutionController│◀────▶│  - LangGraphAdapter  ││
│   │  - 接口定义          │      │  - RayBatchRunner   │      │  - FileTracking      ││
│   │  - 事件定义          │      │  - BatchTestRunner  │      │  - GrpcEnvProvider   ││
│   └─────────────────────┘      └─────────────────────┘      └──────────┬───────────┘│
│                                                                         │            │
│                                        gRPC                            │            │
│                               ┌────────────────────────────────────────┘            │
│                               ▼                                                      │
├───────────────────────────────┼──────────────────────────────────────────────────────┤
│ EXTERNAL                      │                                                      │
│                               ▼                                                      │
│   ┌─────────────────────────────────────────┐        ┌─────────────────────────────┐│
│   │    uv_venv_manager/ (独立服务)           │        │  file_processing/ (示例项目) ││
│   │    UV Virtual Environment Manager       │        │  Example/Demo Project       ││
│   │                                         │        │  (NOT used by WTB core)     ││
│   │    - gRPC API (port 50051)              │        │                             ││
│   │    - REST API (port 10900)              │        │  仅用于演示文件处理功能       ││
│   │    - 独立的 pyproject.toml              │        └─────────────────────────────┘│
│   │    - 独立的数据库 (env_audit.db)         │                                       │
│   │    - 独立的环境存储 (data/envs/)         │                                       │
│   └─────────────────────────────────────────┘                                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 组件关系说明

### 2.1 File System (文件处理)

**WTB 内置的文件跟踪系统:**

| 组件 | 位置 | 说明 |
|------|------|------|
| `IFileTrackingService` | `wtb/domain/interfaces/file_tracking.py` | 接口定义 |
| `AsyncFileTrackerService` | `wtb/infrastructure/file_tracking/` | 异步实现 |
| `SQLAlchemyBlobRepository` | `wtb/infrastructure/database/repositories/` | Blob存储 |
| `SQLAlchemyFileCommitRepository` | 同上 | Commit管理 |

**❌ `file_processing/file_processing/` 是什么？**
```
file_processing/
└── file_processing/        ← 这是一个独立的示例/演示项目！
    ├── config.json         ← 演示用配置
    ├── data.csv            ← 示例数据
    └── use.py              ← 使用示例
```

**这个目录 NOT 被 WTB 核心使用**，它只是一个演示如何使用文件处理功能的示例项目。

**WTB 实际使用的文件存储:**
```python
# WTB 的 blob 存储位置由 Unit of Work 配置
SQLAlchemyUnitOfWork(
    db_url="sqlite:///data/wtb.db",
    blob_storage_path="./data/blobs"  # ← 实际的 blob 存储位置
)
```

### 2.2 UV Venv Manager (虚拟环境管理)

**`uv_venv_manager/` 是一个完全独立的微服务:**

```
uv_venv_manager/
├── src/
│   ├── api.py              # REST API (FastAPI)
│   ├── grpc_servicer.py    # gRPC 服务
│   ├── services/
│   │   ├── env_manager.py  # 环境生命周期管理
│   │   ├── uv_executor.py  # UV CLI 执行器
│   │   └── dep_manager.py  # 依赖管理
│   └── domain/
│       └── interfaces.py   # SOLID 接口
├── data/
│   ├── envs/               # 虚拟环境存储
│   └── env_audit.db        # 审计数据库
└── pyproject.toml          # 独立的依赖管理
```

**WTB 如何集成:**
```python
# wtb/infrastructure/environment/providers.py

class GrpcEnvironmentProvider(IEnvironmentProvider):
    """
    通过 gRPC 调用 UV Venv Manager 服务
    
    职责: 环境创建/删除
    NOT 职责: 代码执行 (那是 Ray 的工作)
    """
    
    def __init__(self, grpc_address: str = "localhost:50051"):
        self._grpc_address = grpc_address
        self._init_grpc()  # 连接到 uv_venv_manager 的 gRPC 服务
    
    def create_environment(self, variant_id: str, config: Dict):
        # 通过 gRPC 调用 uv_venv_manager 创建环境
        request = pb2.CreateEnvRequest(
            workflow_id=config["workflow_id"],
            node_id=config["node_id"],
            packages=config["packages"],
        )
        response = self._stub.CreateEnv(request)
        return {"env_path": response.env_path, "python_path": ...}
```

### 2.3 Ray (分布式执行)

**Ray 在 WTB 中的集成:**

```python
# wtb/application/services/ray_batch_runner.py

class RayBatchTestRunner(IBatchTestRunner):
    """
    使用 Ray ActorPool 进行并行批量测试
    
    架构:
    - RayBatchTestRunner: 编排器，管理 ActorPool
    - VariantExecutionActor: Ray Actor，执行单个变体
    """
    
    def __init__(
        self,
        config: RayConfig,
        environment_provider: IEnvironmentProvider,  # ← 可以是 GrpcEnvironmentProvider
    ):
        self._config = config
        self._env_provider = environment_provider

class VariantExecutionActor:
    """
    Ray Actor - 每个 Actor 有独立的 UoW 和 StateAdapter (ACID 隔离)
    """
    
    def execute(self, combination: VariantCombination) -> VariantExecutionResult:
        # 1. 从 environment_provider 获取运行时环境
        runtime_env = self._env_provider.get_runtime_env(variant_id)
        
        # 2. 在隔离环境中执行工作流
        with self._uow:  # ACID 事务
            controller = ExecutionController(...)
            execution = controller.start_execution(workflow, state)
            # ...
```

---

## 3. 数据流 (Data Flow)

### 3.1 文件跟踪流程

```
                    WTB Execution
                         │
                         ▼
    ┌─────────────────────────────────────────────┐
    │    IFileTrackingService.track_files()       │
    │    (内置于 WTB infrastructure)               │
    └─────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌─────────────┐
    │ Blob    │    │ Commit   │    │ Checkpoint  │
    │ Repo    │    │ Repo     │    │ Link Repo   │
    └────┬────┘    └────┬─────┘    └──────┬──────┘
         │              │                 │
         ▼              ▼                 ▼
    ┌─────────────────────────────────────────────┐
    │          SQLite: data/wtb.db                │
    │          Blobs: data/blobs/objects/         │
    └─────────────────────────────────────────────┘
```

### 3.2 Venv + Ray 执行流程

```
    WTB SDK (create_batch_test)
              │
              ▼
    ┌─────────────────────────────────┐
    │     RayBatchTestRunner          │
    │     (wtb/application/services)  │
    └─────────────────────────────────┘
              │
              │ for each variant
              ▼
    ┌─────────────────────────────────┐          gRPC           ┌───────────────────┐
    │   GrpcEnvironmentProvider       │─────────────────────────▶│  uv_venv_manager  │
    │   create_environment()          │                          │  (独立服务)        │
    └─────────────────────────────────┘                          │                   │
              │                                                  │  - 创建 venv      │
              │ returns python_path                              │  - 安装依赖        │
              ▼                                                  └───────────────────┘
    ┌─────────────────────────────────┐
    │   Ray ActorPool                 │
    │   VariantExecutionActor.remote( │
    │       runtime_env={             │
    │         "py_executable": ...    │  ← 使用 venv 的 python
    │       }                         │
    │   )                             │
    └─────────────────────────────────┘
```

---

## 4. 常见问题解答

### Q1: WTB 是否依赖 `file_processing/file_processing/`？

**否。** 这个目录是一个独立的示例项目，用于演示文件处理功能。

WTB 核心的文件跟踪功能在:
- `wtb/infrastructure/file_tracking/`
- `wtb/infrastructure/database/repositories/file_processing_repository.py`
- `wtb/domain/models/file_processing/`

### Q2: Ray 是否集成在 `uv_venv_manager` 项目中？

**否。** Ray 集成在 WTB 主项目中:
- `wtb/application/services/ray_batch_runner.py`
- `wtb/config.py` (RayConfig)

`uv_venv_manager` 只负责**环境创建**，不负责代码执行。

### Q3: 如何启动完整系统？

```bash
# 1. 启动 UV Venv Manager (独立服务)
cd uv_venv_manager
uvicorn src.api:app --host 0.0.0.0 --port 10900

# 2. (可选) 启动 gRPC 服务
python -m src.grpc_server --port 50051

# 3. 在 WTB 中使用
from wtb.sdk import WTBTestBench
from wtb.infrastructure.environment.providers import GrpcEnvironmentProvider

provider = GrpcEnvironmentProvider("localhost:50051")
bench = WTBTestBench(environment_provider=provider)
```

### Q4: 数据存储在哪里？

| 数据类型 | 存储位置 | 说明 |
|----------|----------|------|
| WTB 执行数据 | `data/wtb.db` | SQLite 主数据库 |
| File blobs | `data/blobs/objects/` | Content-addressable 存储 |
| UV Venv 审计 | `uv_venv_manager/data/env_audit.db` | 独立数据库 |
| 虚拟环境 | `uv_venv_manager/data/envs/` | 实际的 venv 目录 |

---

## 5. 架构决策总结

| 决策 | 说明 |
|------|------|
| **UV Venv Manager = 独立服务** | 通过 gRPC/REST 与 WTB 通信，有自己的数据库和存储 |
| **Ray = WTB 内置** | 在 WTB application 层实现，使用 UV Venv Manager 提供的环境 |
| **File Tracking = WTB 内置** | 完全在 WTB infrastructure 层实现，不依赖外部 file_processing 项目 |
| **职责分离** | UV Venv Manager 创建环境，Ray 执行代码，WTB 编排整个流程 |

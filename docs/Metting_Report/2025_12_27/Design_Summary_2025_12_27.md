# WTB  Design Summary by 2025-12-27

本文档提炼了 Workflow Test Bench (WTB) 目前架构设计的核心思想，涵盖一致性、存储抽象、事件驱动及审计机制。

## 1. 核心架构模式 (Core Architecture Patterns)

### 1.1 双数据库模式 (Dual Database Pattern)

WTB 采用"双库并存"策略，明确职责边界：

- **AgentGit DB (SQLite)**: 负责底层状态快照 (Checkpoints)、工具执行历史。作为"已验证的基础设施"被复用。
- **WTB DB (SQLite/PostgreSQL)**: 负责 WTB 领域业务数据 (Workflows, Executions, NodeBoundaries, EvaluationResults)。
- **FileTracker DB (PostgreSQL)**: 负责大文件/制品的高效去重存储（独立服务）。

### 1.2 Unit of Work (UoW) & Repository

为了隔离领域层与基础设施层，并支持高效测试：

- **接口抽象**: `IUnitOfWork` 和 `IRepository` 定义标准数据访问接口。
- **双重实现**:
  - `InMemoryUnitOfWork`: 纯内存实现，无 I/O，用于单元测试（秒级反馈）。
  - `SQLAlchemyUnitOfWork`: 基于 SQLAlchemy ORM，支持 SQLite（开发）和 PostgreSQL（生产），管理数据库事务。
- **工厂模式**: 通过 `UnitOfWorkFactory` 按需注入具体实现。

---

## 2. 跨系统一致性 (Cross-System Consistency)

鉴于 WTB 需要协调三个独立数据库（WTB, AgentGit, FileTracker），为了保证数据一致性，引入以下机制：

### 2.1 Outbox Pattern (发件箱模式) - P0 级修复

解决 "业务数据写入" 与 "跨系统调用" 的原子性问题。

- **事务中心**: WTB DB 作为事务中心。
- **原子写入**: 业务操作（如 `NodeBoundary` 创建）与 `OutboxEvent`（跨库同步请求）在**同一个数据库事务**中提交。
- **异步处理**: 后台 `OutboxProcessor` 轮询 Outbox 表，可靠地执行对 AgentGit 和 FileTracker 的操作及验证。
- **最终一致性**: 保证至少一次投递 (At-Least-Once)，失败可重试。

### 2.2 Integrity Checker (完整性检查器) - 【to finish】

- **三库巡检**: 定期检查 WTB ↔ AgentGit ↔ FileTracker 之间的引用完整性。
- **检测项**: 悬空引用 (Dangling References)、孤儿检查点 (Orphan Checkpoints)、文件丢失。
- **修复能力**: 支持生成报告，并对部分问题（如清理孤儿数据）进行自动修复。[*]

---

## 3. 事件驱动与审计 (Event Bus & Audit Trail)

### 3.1 Event Bus 策略

- **复用与封装**: WTB 不重造轮子，而是**包装 (Wrap)** AgentGit 的 `EventBus`。
- **WTB Event Facade**: 提供线程安全的 `WTBEventBus`，既支持 WTB 专有事件（`ExecutionStarted`, `NodeCompleted`），也兼容 AgentGit 事件。
- **桥接机制 (Bridge)**: 通过 Anti-Corruption Layer (ACL)，将 AgentGit 的底层事件（如 `CheckpointCreated`）自动转换为 WTB 的领域事件，实现系统解耦。

### 3.2 Audit Trail 分离设计

- **AgentGit Audit**: 关注**工具级 (Tool-level)** 细节（LLM 调用、Token 消耗、工具参数）。存储于 Checkpoint Metadata。
- **WTB Audit**: 关注**执行级 (Execution-level)** 生命周期（节点流转、断点命中、回滚操作）。存储于 WTB DB。
- **集成视图**: WTB Audit 可在需要调试时"导入" AgentGit Audit 快照，提供从高层流程到底层调用的完整视图。

---

## 4. 技术栈关键决策 (Key Tech Decisions)

- **SQLAlchemy**: 选定为 WTB DB 的 ORM 框架。
  - **理由**: 成熟的 Unit of Work 模式支持，强大的模型映射，以及对 SQLite/PostgreSQL 的无缝切换能力。
- **SQLite (WAL Mode)**: 开发环境默认数据库。
  - **理由**: 单文件部署简单，WAL 模式提供较好的并发读写性能，适合单用户场景。
- **PostgreSQL**: 生产环境推荐数据库。
  - **理由**: 支持 FileTracker 和 WTB DB 的高并发、高可靠存储。

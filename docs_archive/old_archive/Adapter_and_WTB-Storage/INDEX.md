# Adapter & WTB Storage - Documentation Index

**Last Updated:** 2026-01-15

## ⚠️ Architecture Update (2026-01-15)

> **LangGraph is now the PRIMARY state adapter.** AgentGit adapter design is **DEFERRED**.
> 
> See [../LangGraph/INDEX.md](../LangGraph/INDEX.md) for the primary state persistence documentation.

## Documents in This Folder

| Document | Purpose | Status |
|----------|---------|--------|
| [AGENTGIT_STATE_ADAPTER_DESIGN.md](./AGENTGIT_STATE_ADAPTER_DESIGN.md) | AgentGit state adapter - bridges WTB ↔ AgentGit | ⏸️ **DEFERRED** |
| [WTB_PERSISTENCE_DESIGN.md](./WTB_PERSISTENCE_DESIGN.md) | WTB storage abstraction (InMemory + SQLAlchemy) | ✅ Implemented |
| [ARCHITECTURE_FIX_DESIGN.md](./ARCHITECTURE_FIX_DESIGN.md) | **架构修复设计** - Outbox Pattern, IntegrityChecker, 充血模型 | 📋 Designed |

## Key Concepts

### State Adapter (IStateAdapter) - Updated Priority

| Priority | Adapter | Purpose | Status |
|----------|---------|---------|--------|
| **1** | `LangGraphStateAdapter` | Production - uses LangGraph checkpointers | 🆕 **PRIMARY** |
| **2** | `InMemoryStateAdapter` | Unit tests - no persistence | ✅ Available |
| **3** | `AgentGitStateAdapter` | Future - uses AgentGit checkpoints | ⏸️ **DEFERRED** |

> **Why LangGraph?** Production-proven (LangSmith uses it), built-in time travel, thread isolation, PostgreSQL support, encryption.

### WTB Persistence (IUnitOfWork)
- **InMemoryUnitOfWork**: For unit tests, Dict-based storage
- **SQLAlchemyUnitOfWork**: Production, SQLite or PostgreSQL

## Selection

```python
# Testing (with LangGraph InMemorySaver)
state_adapter = LangGraphStateAdapter(config=LangGraphConfig(checkpointer_type="memory"))
uow = UnitOfWorkFactory.create(mode="inmemory")

# Production (with LangGraph PostgresSaver)
state_adapter = LangGraphStateAdapter(config=LangGraphConfig(
    checkpointer_type="postgres",
    connection_string="postgresql://..."
))
uow = UnitOfWorkFactory.create(mode="sqlalchemy", db_url="postgresql://...")

# Development (with LangGraph SqliteSaver) 
state_adapter = LangGraphStateAdapter(config=LangGraphConfig(
    checkpointer_type="sqlite",
    connection_string="data/langgraph.db"
))
uow = UnitOfWorkFactory.create(mode="sqlalchemy", db_url="sqlite:///data/wtb.db")
```

## Architecture Fixes

基于架构审查发现的关键问题，设计了以下修复方案：

| 优先级 | 问题 | 解决方案 | 文档 |
|--------|------|----------|------|
| **P0** | 跨库事务一致性 | Outbox Pattern | [ARCHITECTURE_FIX_DESIGN.md](./ARCHITECTURE_FIX_DESIGN.md#2-p0-outbox-pattern-实现设计) |
| **P0** | 数据完整性 | IntegrityChecker | [ARCHITECTURE_FIX_DESIGN.md](./ARCHITECTURE_FIX_DESIGN.md#3-p0-integritychecker-设计) |
| **P1** | 领域模型贫血 | Rich Domain Model | [ARCHITECTURE_FIX_DESIGN.md](./ARCHITECTURE_FIX_DESIGN.md#4-p1-充血领域模型设计) |

### Outbox Pattern 概述

```
┌─────────────────────────────────────────────────────────────────────┐
│  业务数据 + Outbox 事件 ────────► 同一事务写入 WTB DB                │
│                                        │                            │
│                                   Outbox Processor (后台)           │
│                                        │                            │
│                                        ▼                            │
│                              LangGraph / FileTracker               │
│                                   (验证/同步)                        │
└─────────────────────────────────────────────────────────────────────┘
```

> **Note:** With LangGraph as primary, Outbox pattern primarily handles FileTracker integration.
> LangGraph's built-in persistence reduces cross-database coordination complexity.

## See Also

| Document | Purpose |
|----------|---------|
| [../LangGraph/INDEX.md](../LangGraph/INDEX.md) | 🆕 **LangGraph integration (PRIMARY)** |
| [../Project_Init/INDEX.md](../Project_Init/INDEX.md) | Main documentation index |
| [../Project_Init/DATABASE_DESIGN.md](../Project_Init/DATABASE_DESIGN.md) | Database schemas & storage strategy |


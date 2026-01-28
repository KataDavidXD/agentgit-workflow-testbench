# WTB Built-in File Processing vs Standalone file_processing 对比分析

**Created**: 2026-01-28  
**Purpose**: 比较两个文件处理实现的设计差异

---

## 📊 概览对比表

| 维度 | file_processing/file_processing | WTB Built-in |
|------|--------------------------------|--------------|
| **数据库** | PostgreSQL (psycopg2) | SQLAlchemy (支持多DB) |
| **架构层次** | ORM → Repository → App | Domain → Repository Interface → ORM → Mapper |
| **异步支持** | ❌ 仅同步 | ✅ sync + async |
| **DDD 实践** | ❌ 基础 | ✅ 完整 DDD |
| **事务管理** | 手动 conn.commit() | UoW Pattern (自动) |
| **Value Objects** | ❌ 原始类型 | ✅ BlobId, CommitId |
| **生命周期管理** | ❌ 无状态 | ✅ PENDING→FINALIZED→VERIFIED |
| **与 Checkpoint 集成** | ❌ | ✅ CheckpointFileLink |
| **引用计数** | ❌ | ✅ reference_count |
| **代码复用** | 无共享 | BlobStorageCore (DRY) |

---

## 🏗️ 架构对比

### 1. file_processing/file_processing (独立项目)

```
┌─────────────────────────────────────────────────────────┐
│                    Application (use.py)                  │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  Repository Layer                        │
│  ┌─────────────────┐ ┌──────────────────┐              │
│  │ CommitRepository │ │  BlobRepository  │              │
│  └────────┬────────┘ └────────┬─────────┘              │
└───────────┼────────────────────┼────────────────────────┘
            │                    │
┌───────────▼────────────────────▼────────────────────────┐
│                      ORM Layer                           │
│  ┌─────────────────┐ ┌──────────────────┐              │
│  │   CommitORM     │ │    BlobORM       │              │
│  └────────┬────────┘ └────────┬─────────┘              │
└───────────┼────────────────────┼────────────────────────┘
            │                    │
┌───────────▼────────────────────▼────────────────────────┐
│                    PostgreSQL + Filesystem               │
└─────────────────────────────────────────────────────────┘
```

**特点**:
- 2层架构: ORM → Repository
- psycopg2 直接操作
- 无抽象接口
- 简单直接

### 2. WTB Built-in File Processing

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Services                        │
│                  (AsyncFileTrackerService)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     Domain Layer (DDD)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Entities: FileCommit (Aggregate Root), FileMemento      │   │
│  │  Value Objects: BlobId, CommitId                         │   │
│  │  Enums: CommitStatus (PENDING/FINALIZED/VERIFIED)        │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                 Domain Interfaces (DIP)                          │
│  ┌─────────────────┐ ┌───────────────────┐ ┌───────────────┐   │
│  │ IBlobRepository │ │ IFileCommitRepo   │ │ ICheckpointLnk│   │
│  └─────────────────┘ └───────────────────┘ └───────────────┘   │
│         + Async versions: IAsyncBlobRepository, etc.            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     Mapper Layer (DRY)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  BlobStorageCore: Shared sync/async logic               │    │
│  │  FileCommitMapper: ORM ↔ Domain                        │    │
│  │  CheckpointFileLinkMapper: ORM ↔ Domain                │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     ORM Layer (SQLAlchemy)                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐     │
│  │ FileBlobORM  │ │ FileCommitORM │ │ CheckpointFileLinkORM │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│            Infrastructure (Unit of Work)                         │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  SQLAlchemyUnitOfWork / AsyncSQLAlchemyUnitOfWork      │     │
│  │  - Transaction boundary management                      │     │
│  │  - Repository coordination                              │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**特点**:
- 4-5 层架构: Domain → Interface → Mapper → ORM → UoW
- SQLAlchemy 支持多数据库
- 抽象接口 + DIP
- SOLID + ACID 合规

---

## 🔍 代码设计详细对比

### Entity 设计

#### Standalone: FileMemento (简单类)

```python
# file_processing/FileTracker/FileMemento.py
class FileMemento:
    def __init__(self, file_path, blob_orm=None):
        self.file_path = file_path
        content = Path(file_path).read_bytes()
        self.file_hash = hashlib.sha256(content).hexdigest()
        self.file_size = len(content)
        if blob_orm:
            blob_orm.save(content)  # 直接在构造函数中保存！
```

**问题**:
- 构造函数中有副作用 (保存到DB)
- 无类型验证
- 无不可变保证

#### WTB: FileMemento (Value Object)

```python
# wtb/domain/models/file_processing/entities.py
@dataclass(frozen=True)  # ← 不可变
class FileMemento:
    file_path: str
    file_hash: BlobId     # ← Value Object, 类型安全
    file_size: int
    
    def __post_init__(self):  # ← 验证
        if not self.file_path:
            raise ValueError("file_path cannot be empty")
        if self.file_size < 0:
            raise ValueError(f"file_size cannot be negative")
    
    @classmethod
    def from_file(cls, file_path: str) -> tuple["FileMemento", bytes]:
        """创建 memento 但不保存，返回 content 让调用者决定"""
        content = Path(file_path).read_bytes()
        blob_id = BlobId.from_content(content)
        return cls(...), content  # ← 无副作用
```

**优势**:
- `frozen=True`: 线程安全
- `BlobId` Value Object: 类型安全
- Factory method: 分离创建和保存
- 验证逻辑在实体内

### Value Objects

#### Standalone: 原始类型

```python
# 直接使用 str
file_hash = "a1b2c3..."  # 可能是任意字符串
commit_id = "uuid-here"   # 无验证
```

#### WTB: BlobId Value Object

```python
@dataclass(frozen=True)
class BlobId:
    value: str
    
    def __post_init__(self):
        if len(self.value) != 64:
            raise InvalidBlobIdError(
                f"BlobId must be 64 hex characters (SHA-256)"
            )
        if not all(c in '0123456789abcdef' for c in self.value.lower()):
            raise InvalidBlobIdError(f"BlobId must be hexadecimal")
    
    @property
    def storage_path(self) -> str:
        """Git-like: objects/{hash[:2]}/{hash[2:]}"""
        return f"objects/{self.value[:2]}/{self.value[2:]}"
    
    @classmethod
    def from_content(cls, content: bytes) -> "BlobId":
        hash_value = hashlib.sha256(content).hexdigest()
        return cls(value=hash_value)
```

**优势**:
- 类型安全: 编译时类型检查
- 自验证: 无效值无法构造
- 丰富 API: `storage_path`, `short`

### Commit 生命周期

#### Standalone: 无状态管理

```python
commit = Commit(message="msg")
commit.add_memento(memento)
commit_repo.save(commit)  # 直接保存，无状态检查
```

#### WTB: 状态机

```python
class CommitStatus(Enum):
    PENDING = "pending"     # 构建中
    FINALIZED = "finalized" # 已保存
    VERIFIED = "verified"   # 已验证

@dataclass
class FileCommit:
    status: CommitStatus = CommitStatus.PENDING
    
    def add_memento(self, memento: FileMemento) -> None:
        if self.is_finalized:
            raise CommitAlreadyFinalized(...)  # 不可变约束
        if memento.file_path in self.file_paths:
            raise DuplicateFileError(...)      # 业务规则
        self._mementos.append(memento)
    
    def finalize(self) -> None:
        if not self._mementos:
            raise ValueError("Cannot finalize empty commit")
        self.status = CommitStatus.FINALIZED
    
    def mark_verified(self) -> None:
        """Outbox processor 验证后调用"""
        if self.status != CommitStatus.FINALIZED:
            raise ValueError("Can only verify finalized commits")
        self.status = CommitStatus.VERIFIED
```

**优势**:
- 强制业务规则
- 与 Outbox pattern 集成
- 清晰的状态流转

---

## 🔗 WTB 集成特性

### Checkpoint-File Link

```python
# WTB 独有: 关联 Checkpoint 和 FileCommit
@dataclass(frozen=True)
class CheckpointFileLink:
    checkpoint_id: int      # WTB checkpoint
    commit_id: CommitId     # FileTracker commit
    linked_at: datetime
    file_count: int
    total_size_bytes: int
```

**用途**:
- Checkpoint 回滚时恢复文件
- 审计文件历史
- 跨系统一致性

### ORM 表结构

```sql
-- WTB 独有: checkpoint_file_links 表
CREATE TABLE checkpoint_file_links (
    checkpoint_id INTEGER PRIMARY KEY,
    commit_id VARCHAR(64) REFERENCES file_commits(commit_id),
    linked_at TIMESTAMP,
    file_count INTEGER,
    total_size_bytes BIGINT
);
```

---

## 🔄 DRY: BlobStorageCore

### 问题: Sync/Async 重复代码

```python
# 之前: sync 和 async 各自实现
class SQLAlchemyBlobRepository:
    def _compute_path(self, blob_id): ...  # 重复
    
class AsyncSQLAlchemyBlobRepository:
    def _compute_path(self, blob_id): ...  # 重复
```

### 解决: 提取共享逻辑

```python
# wtb/infrastructure/database/mappers/blob_storage_core.py
class BlobStorageCore:
    @staticmethod
    def compute_blob_id(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
    
    @staticmethod
    def compute_storage_path(blob_id: str, objects_path: Path) -> Path:
        return objects_path / blob_id[:2] / blob_id[2:]
    
    @staticmethod
    def create_orm_dict(blob_id, storage_location, size): ...
```

**使用**:

```python
# Sync repository
class SQLAlchemyBlobRepository(IBlobRepository):
    def save(self, content: bytes) -> BlobId:
        blob_id = BlobId.from_content(content)
        storage_location = BlobStorageCore.compute_storage_path(
            blob_id.value, self._objects_path
        )
        # ...

# Async repository
class AsyncSQLAlchemyBlobRepository(IAsyncBlobRepository):
    async def asave(self, content: bytes) -> BlobId:
        blob_id = BlobId.from_content(content)
        storage_location = BlobStorageCore.compute_storage_path(
            blob_id.value, self._objects_path
        )
        # ...
```

---

## 📋 总结

### file_processing/file_processing 适用场景

- ✅ 简单独立的文件版本控制
- ✅ 学习 Memento 和 Repository 模式
- ✅ PostgreSQL 单数据库项目
- ❌ 不适合需要事务一致性的复杂系统

### WTB Built-in 适用场景

- ✅ 需要与 Workflow/Checkpoint 集成
- ✅ 需要 ACID 事务保证
- ✅ 需要 async 支持
- ✅ 多数据库支持 (SQLite, PostgreSQL)
- ✅ 需要 Outbox pattern 跨系统一致性
- ❌ 对于简单项目可能过度设计

### 关系

```
file_processing/file_processing
        │
        │ (原型/概念验证)
        │
        ▼
WTB Built-in File Processing
        │
        │ (重构 + DDD + SOLID)
        │
        ├── 添加 Value Objects (BlobId, CommitId)
        ├── 添加状态生命周期 (PENDING → FINALIZED → VERIFIED)
        ├── 添加 Interface 抽象 (IBlobRepository)
        ├── 添加 Mapper 层 (BlobStorageCore)
        ├── 添加 Async 支持
        └── 添加 WTB 集成 (CheckpointFileLink)
```

**结论**: WTB Built-in 是 `file_processing/file_processing` 的 **企业级重构版本**，遵循 DDD、SOLID、ACID 原则，专为与 WTB workflow 系统集成设计。

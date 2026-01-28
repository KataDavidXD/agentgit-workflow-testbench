# Architecture Review Report - 2026-01-28

**Reviewer:** Senior Software Architect + Agent Systems Architect  
**Scope:** File System, Checkpoints, Async/API Services, Outbox Pattern  
**Status:** ⚠️ Issues Found - Action Required

---

## Executive Summary

| Category | Status | Critical | High | Medium | Low |
|----------|--------|----------|------|--------|-----|
| File System Duplicate Logic | ⚠️ | 0 | 2 | 1 | 0 |
| Checkpoint Entry/Exit Consistency | ⚠️ | 1 | 1 | 0 | 0 |
| Async/API Services Quality | ✅ | 0 | 0 | 2 | 1 |
| Outbox Pattern Effectiveness | ✅ | 0 | 0 | 1 | 1 |
| SOLID Compliance | ✅ | 0 | 0 | 1 | 2 |
| ACID/Transaction Consistency | ✅ | 0 | 1 | 0 | 0 |
| **Total** | ⚠️ | **1** | **4** | **5** | **4** |

---

## 1. File System Duplicate Logic Analysis

### 1.1 ISSUE-FS-001: Sync/Async Repository Code Duplication (HIGH)

**Location:** 
- `wtb/infrastructure/database/repositories/file_processing_repository.py`
- `wtb/infrastructure/database/async_repositories/async_file_processing_repository.py`

**Problem:** 
The sync `SQLAlchemyBlobRepository` and async `AsyncSQLAlchemyBlobRepository` contain nearly identical business logic with only synchronous vs asynchronous syntax differences. This violates the DRY principle.

**Evidence:**

```python
# Sync version (file_processing_repository.py:94)
def save(self, content: bytes) -> BlobId:
    blob_id = BlobId.from_content(content)
    existing = self._session.get(FileBlobORM, blob_id.value)
    if existing:
        existing.reference_count += 1
        return blob_id
    # ... write to filesystem, create DB record

# Async version (async_file_processing_repository.py:80)
async def asave(self, content: bytes) -> BlobId:
    blob_id = BlobId.from_content(content)
    existing = await self._session.get(FileBlobORM, blob_id.value)
    if existing:
        existing.reference_count += 1
        return blob_id
    # ... identical logic, just async
```

**Impact:** 
- Maintenance burden (changes must be made in two places)
- Risk of divergent behavior between sync/async paths
- ~500 lines of duplicated logic

**Recommended Fix:**
Extract shared business logic into a `BlobStorageCore` class that handles pure logic (hash computation, path resolution), and have both sync/async repositories delegate to it.

```python
# Proposed: wtb/infrastructure/database/repositories/blob_storage_core.py
class BlobStorageCore:
    """Pure logic, no I/O - shared between sync and async repositories."""
    
    @staticmethod
    def compute_storage_path(blob_id: BlobId, base_path: Path) -> Path:
        return base_path / "objects" / blob_id.value[:2] / blob_id.value[2:]
    
    @staticmethod
    def compute_blob_id(content: bytes) -> BlobId:
        return BlobId.from_content(content)
```

---

### 1.2 ISSUE-FS-002: Outbox Repository Duplication (HIGH)

**Location:**
- `wtb/infrastructure/database/repositories/outbox_repository.py` (sync)
- `wtb/infrastructure/database/async_repositories/async_outbox_repository.py` (async)

**Problem:**
ORM ↔ Domain conversion logic (`_to_domain`, `_to_orm`) is duplicated between sync and async repositories.

**Evidence:**

```python
# Sync version (outbox_repository.py:29)
def _to_domain(self, orm: OutboxEventORM) -> OutboxEvent:
    return OutboxEvent(
        id=orm.id,
        event_id=orm.event_id,
        event_type=OutboxEventType(orm.event_type),
        # ... 10+ fields
    )

# Async version (async_outbox_repository.py:83)
def _to_domain(self, orm: OutboxEventORM) -> OutboxEvent:
    event = OutboxEvent(
        event_type=OutboxEventType(orm.event_type),
        # ... same logic, slightly different structure
    )
```

**Impact:**
- Inconsistent conversion (async version uses different field assignment pattern)
- Bug risk if one is updated but not the other

**Recommended Fix:**
Create `OutboxMapper` utility class for domain ↔ ORM conversion.

---

### 1.3 ISSUE-FS-003: Async Core Repositories Incomplete (MEDIUM)

**Location:** `wtb/infrastructure/database/async_repositories/async_core_repositories.py`

**Problem:**
The async core repositories are stub implementations with `TODO: Implement mapping` comments.

**Evidence:**

```python
class AsyncWorkflowRepository(BaseAsyncRepository):
    def _to_domain(self, orm):
        # TODO: Implement mapping
        return orm  # Returns ORM, not domain object!
    def _to_orm(self, domain):
        # TODO: Implement mapping
        return domain
```

**Impact:**
- Leaks ORM objects to domain layer (architectural violation)
- Tests may pass with incorrect abstraction boundaries
- SOLID violation (Domain depends on Infrastructure)

**Recommended Fix:**
Implement proper mapping or document these as intentionally simplified for specific use cases.

---

## 2. Checkpoint Entry/Exit Design Consistency

### 2.1 ISSUE-CP-001: Domain vs ORM Inconsistency (CRITICAL)

**Location:**
- Domain: `wtb/domain/models/node_boundary.py`
- ORM: `wtb/infrastructure/database/models.py` (NodeBoundaryORM)

**Problem:**
The domain model `NodeBoundary` was refactored for DDD compliance (2026-01-15) but the ORM model still contains deprecated fields and inconsistent types.

**Domain Model (Updated 2026-01-15):**
```python
@dataclass
class NodeBoundary:
    # DDD Changes (2026-01-15):
    # - entry_checkpoint_id: Now Optional[str] (LangGraph UUID format)
    # - exit_checkpoint_id: Now Optional[str] (LangGraph UUID format)
    # - Removed: internal_session_id, tool_count, checkpoint_count
    
    entry_checkpoint_id: Optional[str] = None
    exit_checkpoint_id: Optional[str] = None
    # NO internal_session_id, tool_count, checkpoint_count
```

**ORM Model (Still has deprecated fields):**
```python
class NodeBoundaryORM(Base):
    # Session Reference (v1.6: now String UUID, previously Integer AgentGit ref)
    internal_session_id = Column(String(128), nullable=False)  # STILL EXISTS!
    
    # Metrics (should be removed per DDD changes)
    tool_count = Column(Integer, default=0)  # STILL EXISTS!
    checkpoint_count = Column(Integer, default=0)  # STILL EXISTS!
```

**Impact:**
- ORM-Domain mapping silently drops `internal_session_id`, `tool_count`, `checkpoint_count`
- Database schema diverged from domain model
- Migration not applied or incomplete
- Data integrity risk

**Recommended Fix:**
1. Create migration to remove deprecated columns from `wtb_node_boundaries` table
2. Update `NodeBoundaryORM` to match domain model
3. Update repository mapping to handle transition

```sql
-- Migration: 005_node_boundary_cleanup.sql
ALTER TABLE wtb_node_boundaries DROP COLUMN internal_session_id;
ALTER TABLE wtb_node_boundaries DROP COLUMN tool_count;
ALTER TABLE wtb_node_boundaries DROP COLUMN checkpoint_count;
```

---

### 2.2 ISSUE-CP-002: Repository Mapping Type Mismatch (HIGH)

**Location:** `wtb/infrastructure/database/repositories/node_boundary_repository.py`

**Problem:**
The repository converts `entry_checkpoint_id` and `exit_checkpoint_id` to `CheckpointId` value objects, but the domain model expects `Optional[str]`.

**Evidence:**

```python
# Repository (line 37-38)
entry_cp_id = CheckpointId(str(orm.entry_checkpoint_id)) if orm.entry_checkpoint_id else None
exit_cp_id = CheckpointId(str(orm.exit_checkpoint_id)) if orm.exit_checkpoint_id else None

return NodeBoundary(
    entry_checkpoint_id=entry_cp_id,  # This is CheckpointId, not str!
    exit_checkpoint_id=exit_cp_id,    # This is CheckpointId, not str!
)
```

**Domain Model:**
```python
entry_checkpoint_id: Optional[str] = None  # Expects str, not CheckpointId
exit_checkpoint_id: Optional[str] = None   # Expects str, not CheckpointId
```

**Impact:**
- Type mismatch may cause runtime errors
- Inconsistent behavior when comparing checkpoint IDs
- Tests may mask this if they use mocks

**Recommended Fix:**
Either:
1. Update domain model to use `Optional[CheckpointId]`, OR
2. Update repository to pass raw strings

---

## 3. Async and API Services Code Quality

### 3.1 ISSUE-API-001: ExecutionAPIService list_executions() Returns Empty (MEDIUM)

**Location:** `wtb/application/services/api_services.py:111-130`

**Problem:**
The `list_executions()` method always returns empty results because `all_executions` is never populated.

**Evidence:**

```python
async def list_executions(...) -> PaginatedResultDTO:
    try:
        all_executions = []  # Always empty!
        
        # These filters operate on empty list
        if workflow_id:
            all_executions = [e for e in all_executions if e.workflow_id == workflow_id]
        if status:
            all_executions = [e for e in all_executions if e.status.value == status]
        
        # Always returns empty
        return PaginatedResultDTO(items=[], total=0, ...)
```

**Impact:**
- REST endpoint `/api/v1/executions` always returns empty list
- Tests pass because mocks don't exercise this path

**Recommended Fix:**

```python
async def list_executions(...) -> PaginatedResultDTO:
    try:
        # Actually fetch from repository
        async with self._uow:
            all_executions = await self._uow.executions.alist_all(limit=1000)
        
        # Then filter...
```

---

### 3.2 ISSUE-API-002: Sync Context Manager in Async Methods (MEDIUM)

**Location:** `wtb/application/services/api_services.py`

**Problem:**
Several async methods use sync `with self._uow:` instead of async `async with self._uow:`.

**Evidence:**

```python
# Line 214: Using sync context manager in async method
async def pause_execution(...) -> ControlResultDTO:
    try:
        with self._uow:  # SYNC! Should be "async with"
            execution = self._controller.pause(execution_id)
            # ...
```

**Impact:**
- In async context, sync UoW may block event loop
- Mixed async/sync patterns reduce performance
- Transaction boundaries may not work correctly with async session

**Recommended Fix:**
Update all API service methods to use async UoW pattern:

```python
async def pause_execution(...) -> ControlResultDTO:
    async with self._uow:
        execution = await self._controller.apause(execution_id)
        # ...
```

---

### 3.3 ISSUE-API-003: Missing Input Validation (LOW)

**Location:** `wtb/application/services/api_services.py`

**Problem:**
Input parameters like `execution_id`, `checkpoint_id` are not validated before use.

**Evidence:**

```python
async def rollback_execution(
    self,
    execution_id: str,  # Not validated
    checkpoint_id: str,  # Not validated - could be empty string
    create_branch: bool = False,
) -> RollbackResultDTO:
    try:
        with self._uow:
            # Direct use without validation
            execution = self._controller.rollback(execution_id, checkpoint_id)
```

**Recommended Fix:**
Add domain validation:

```python
async def rollback_execution(...) -> RollbackResultDTO:
    if not execution_id or not execution_id.strip():
        return RollbackResultDTO(success=False, error="execution_id required")
    if not checkpoint_id or not checkpoint_id.strip():
        return RollbackResultDTO(success=False, error="checkpoint_id required")
```

---

## 4. Outbox Pattern Effectiveness

### 4.1 ISSUE-OB-001: Outbox Events Not Actually Processed (MEDIUM)

**Location:** Throughout API services

**Problem:**
Outbox events are created and committed, but there's no evidence of an active processor consuming them.

**Evidence:**
The tests verify events are *created* but don't verify they are *processed*.

```python
# test_api_transaction_consistency.py:169
assert len(uow._outbox_events) == 1  # Created
# No test for actual processing/publishing
```

**Impact:**
- Outbox events accumulate in database
- External systems never receive notifications
- "Eventual consistency" never achieved

**Recommended Fix:**
1. Verify `OutboxLifecycleManager` is started in production
2. Add integration test that verifies end-to-end event flow
3. Add monitoring for outbox queue depth

---

### 4.2 ISSUE-OB-002: Missing Idempotency Keys in API Events (LOW)

**Location:** `wtb/domain/models/outbox.py`

**Problem:**
API-related outbox events don't include idempotency keys in payload, making retry logic harder.

**Evidence:**

```python
# api_services.py:220
outbox_event = OutboxEvent.create(
    event_type=OutboxEventType.EXECUTION_PAUSED,
    aggregate_id=execution_id,
    payload={
        "execution_id": execution_id,
        "reason": reason,
        "at_node": at_node,
        "checkpoint_id": str(execution.checkpoint_id) if execution.checkpoint_id else None,
        # Missing: "idempotency_key": str(uuid4())
    },
)
```

**Recommended Fix:**
Add idempotency key to all outbox event payloads:

```python
payload={
    "idempotency_key": str(uuid.uuid4()),
    "execution_id": execution_id,
    # ...
}
```

---

## 5. SOLID Compliance Analysis

### 5.1 Overall SOLID Assessment

| Principle | Status | Notes |
|-----------|--------|-------|
| **S** - Single Responsibility | ✅ | API services well-separated |
| **O** - Open/Closed | ✅ | New adapters via interfaces |
| **L** - Liskov Substitution | ⚠️ | Type mismatch in node boundary |
| **I** - Interface Segregation | ✅ | ISP well-implemented |
| **D** - Dependency Inversion | ⚠️ | Async repos leak ORM |

### 5.2 ISSUE-SOLID-001: Interface Segregation Gap (MEDIUM)

**Location:** `wtb/domain/interfaces/repositories.py`

**Problem:**
`IWorkflowRepository` requires both sync and async methods, violating ISP for sync-only consumers.

**Recommended Fix:**
Already addressed in architecture (separate `IAsyncWorkflowRepository`).

### 5.3 ISSUE-SOLID-002: Dependency Leak in Async Repos (LOW)

**Location:** `wtb/infrastructure/database/async_repositories/async_core_repositories.py`

**Problem:**
`_to_domain()` returns ORM objects directly, leaking infrastructure to domain.

### 5.4 ISSUE-SOLID-003: API Service Factory Uses Concrete Types (LOW)

**Location:** `wtb/application/services/api_services.py:980-1031`

**Problem:**
`APIServiceFactory` methods return concrete types instead of interfaces.

**Evidence:**

```python
@staticmethod
def create_execution_service(...) -> ExecutionAPIService:  # Concrete type
    return ExecutionAPIService(...)
```

**Recommended Fix:**

```python
@staticmethod
def create_execution_service(...) -> IExecutionAPIService:  # Interface type
    return ExecutionAPIService(...)
```

---

## 6. ACID/Transaction Consistency Analysis

### 6.1 Overall ACID Assessment

| Property | Status | Notes |
|----------|--------|-------|
| **A** - Atomicity | ⚠️ | Mixed sync/async UoW usage |
| **C** - Consistency | ✅ | DTOs enforce valid state |
| **I** - Isolation | ✅ | Per-request UoW instances |
| **D** - Durability | ✅ | SQLite WAL, fsync |

### 6.2 ISSUE-ACID-001: Mixed Sync/Async Transaction Boundaries (HIGH)

**Location:** `wtb/application/services/api_services.py`

**Problem:**
Async methods use sync `with self._uow:` context manager, which may not properly manage async transactions.

**Evidence:**

```python
async def pause_execution(...) -> ControlResultDTO:
    try:
        with self._uow:  # SYNC context manager in async method!
            execution = self._controller.pause(execution_id)
            # Controller.pause() is also sync
            
            # Creates outbox event
            outbox_event = OutboxEvent.create(...)
            self._uow.outbox.add(outbox_event)  # Sync add()
            self._uow.commit()  # Sync commit()
```

**Impact:**
- Event loop blocking on database operations
- Transaction may not rollback correctly on async exceptions
- Inconsistent behavior under load

**Recommended Fix:**
1. Create async-aware `ExecutionAPIService` or
2. Ensure controller and UoW are truly async-compatible

---

## 7. Recommendations Summary

### Critical (Must Fix)

| ID | Issue | Action | Effort |
|----|-------|--------|--------|
| CP-001 | Domain/ORM inconsistency | Create migration, update ORM | Medium |

### High Priority

| ID | Issue | Action | Effort |
|----|-------|--------|--------|
| FS-001 | Sync/async repository duplication | Extract shared logic | High |
| FS-002 | Outbox mapper duplication | Create shared mapper | Low |
| CP-002 | Type mismatch in repository | Fix repository mapping | Low |
| ACID-001 | Mixed sync/async transactions | Audit and fix UoW usage | Medium |

### Medium Priority

| ID | Issue | Action | Effort |
|----|-------|--------|--------|
| FS-003 | Incomplete async repos | Implement or document | Medium |
| API-001 | Empty list_executions | Fix repository call | Low |
| API-002 | Sync context in async | Update to async UoW | Medium |
| OB-001 | Outbox not processed | Verify lifecycle manager | Low |
| SOLID-001 | Interface segregation | Already addressed | Done |

### Low Priority

| ID | Issue | Action | Effort |
|----|-------|--------|--------|
| API-003 | Missing input validation | Add validation | Low |
| OB-002 | Missing idempotency keys | Add to payloads | Low |
| SOLID-002 | ORM leak in async repos | Fix _to_domain | Low |
| SOLID-003 | Concrete return types | Return interfaces | Low |

---

## 8. Action Items

### Immediate (This Sprint)

- [ ] **CP-001**: Create migration `005_node_boundary_cleanup.sql`
- [ ] **CP-002**: Fix `NodeBoundaryRepository._to_domain()` type handling
- [ ] **ACID-001**: Audit sync/async context manager usage in API services

### Short-term (Next 2 Weeks)

- [ ] **FS-001**: Create `BlobStorageCore` for shared logic
- [ ] **FS-002**: Create `OutboxMapper` utility
- [ ] **API-001**: Fix `list_executions()` to actually query repository
- [ ] **API-002**: Update API services to use async UoW consistently

### Long-term (Next Month)

- [ ] **FS-003**: Complete async repository implementations
- [ ] **OB-001**: Add outbox processor health monitoring
- [ ] **OB-002**: Add idempotency keys to all outbox events

---

## 9. Test Coverage Recommendations

### New Unit Tests Needed

| Test File | Test Case | Priority |
|-----------|-----------|----------|
| `test_node_boundary_consistency.py` | Domain/ORM field alignment | Critical |
| `test_node_boundary_consistency.py` | Checkpoint ID type consistency | High |
| `test_api_services_unit.py` | list_executions returns data | Medium |
| `test_async_repositories.py` | ORM→Domain conversion correct | Medium |

### New Integration Tests Needed

| Test File | Test Case | Priority |
|-----------|-----------|----------|
| `test_outbox_integration.py` | End-to-end event processing | High |
| `test_async_transaction_integration.py` | Async UoW rollback on error | High |

---

## 10. Documentation Updates Required

| Document | Update |
|----------|--------|
| `PROGRESS_TRACKER.md` | Add architecture review findings |
| `WORKFLOW_TEST_BENCH_ARCHITECTURE.md` | Update §13 with decisions |
| `INDEX.md` | Link to this review document |

---

## Appendix A: Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `wtb/domain/interfaces/api_services.py` | 647 | ✅ Reviewed |
| `wtb/application/services/api_services.py` | 1043 | ✅ Reviewed |
| `wtb/domain/models/outbox.py` | 370 | ✅ Reviewed |
| `wtb/domain/models/checkpoint.py` | 421 | ✅ Reviewed |
| `wtb/domain/models/node_boundary.py` | 181 | ✅ Reviewed |
| `wtb/domain/models/file_processing/entities.py` | 455 | ✅ Reviewed |
| `wtb/infrastructure/database/models.py` | 291+ | ✅ Reviewed |
| `wtb/infrastructure/database/repositories/outbox_repository.py` | 159 | ✅ Reviewed |
| `wtb/infrastructure/database/async_repositories/*.py` | ~700 | ✅ Reviewed |
| `tests/test_api/test_api_transaction_consistency.py` | 448 | ✅ Reviewed |

---

**Report Generated:** 2026-01-28  
**Next Review:** 2026-02-15 (Post-fix verification)

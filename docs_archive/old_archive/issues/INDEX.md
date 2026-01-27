# Issues & Gap Analysis Index

**Last Updated:** 2026-01-15

## Overview

This folder tracks architectural issues, gap analyses, and their resolutions. Issues are prioritized using standard severity levels (P0-P3).

## Active Issues

| ID | Title | Priority | Status | Date |
|----|-------|----------|--------|------|
| GAP-001 | [State Adapter ID Mismatch](./GAP_ANALYSIS_2026_01_15_STATE_ADAPTER_ID_MISMATCH.md) | **P0** | Open | 2026-01-15 |
| GAP-002 | [Workspace Isolation Design](./WORKSPACE_ISOLATION_DESIGN.md) | **P0** | Design | 2026-01-16 |

## Design Documents

| ID | Title | Scope | Status |
|----|-------|-------|--------|
| DESIGN-001 | [Workspace Isolation Design](./WORKSPACE_ISOLATION_DESIGN.md) | File & Venv isolation for parallel/fork/rollback | Design Phase |

### DESIGN-001: Workspace Isolation Summary

**Problem:** No automatic file/venv isolation when forking for parallel execution.

**Key Topics Addressed:**
- File system auto-copy on fork → Workspace per variant
- LangGraph rollback (same graph, different thread_id)
- Workspace for rollback/time-travel → Required for file consistency
- Venv management for fork/rollback/parallel/node-update

**Critical Gaps Identified:**
1. Parallel execution shares file system → Race conditions
2. Fork doesn't clone venv → Package conflicts
3. Rollback doesn't restore venv → Dependency mismatch
4. Node update doesn't invalidate venv → Stale packages

## Issue Severity Definitions

| Priority | Definition | Response Time |
|----------|------------|---------------|
| **P0** | Architectural blocker, blocks critical path | Immediate |
| **P1** | Significant issue affecting development | 1-2 days |
| **P2** | Technical debt, non-blocking | 1 week |
| **P3** | Enhancement, future consideration | Backlog |

## Issue Template

When creating new issues, use this structure:

```markdown
# Gap Analysis: [Title]

**Date:** YYYY-MM-DD
**Status:** Open | In Progress | Resolved | Deferred
**Priority:** P0 | P1 | P2 | P3

## 1. Issue Description
[Clear description of the gap/issue]

## 2. Impact Analysis
[What is blocked? What are the risks?]

## 3. Root Cause
[Why did this happen?]

## 4. Proposed Solution
[Technical approach]

## 5. Action Items
[Checklist of tasks]
```

## Resolved Issues

| ID | Title | Resolution | Date |
|----|-------|------------|------|
| - | - | - | - |

## Related Documents

| Document | Location | Description |
|----------|----------|-------------|
| Progress Tracker | [PROGRESS_TRACKER.md](../Project_Init/PROGRESS_TRACKER.md) | Implementation status |
| Architecture | [WORKFLOW_TEST_BENCH_ARCHITECTURE.md](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Technical decisions |
| LangGraph Integration | [LangGraph/INDEX.md](../LangGraph/INDEX.md) | LangGraph persistence design |

# WTB External API & Observability Architecture

**Version:** 1.0  
**Date:** 2026-01-15  
**Status:** APPROVED

---

## Executive Summary

This document defines how external users/services control the WTB system and how the event audit system is exposed externally. The design follows SOLID and ACID principles while maintaining clear patterns and transaction consistency.

### Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **External Control** | REST + gRPC + WebSocket | REST for simplicity; gRPC for performance; WebSocket for real-time |
| **Primary Protocol** | REST (FastAPI) | Developer-friendly, auto-docs, wide tooling support |
| **Internal Protocol** | gRPC | High-throughput, streaming, type-safe, Ray integration |
| **Real-time Events** | WebSocket + gRPC Streams | UI updates, live audit trail, execution progress |
| **Observability** | OpenTelemetry → Prometheus → Grafana | Vendor-neutral, industry standard, cloud-native |
| **Audit Exposure** | REST API + gRPC Stream + Prometheus Metrics | Query, subscribe, aggregate |
| **Transaction Safety** | Outbox Pattern + Event Sourcing | ACID compliance across bounded contexts |

---

## 1. Protocol Architecture

### 1.1 Protocol Selection: When to Use What (DEFINITIVE GUIDE)

> **关键决策**: 三种协议**同时运行**，客户端根据需求选择合适的协议。不是二选一，而是根据场景选最优。

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PROTOCOL SELECTION DECISION TREE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  问题: 你的客户端是什么?                                                          │
│  ════════════════════════                                                        │
│                                                                                  │
│  浏览器/Web UI?                                                                  │
│  ├─ 需要实时更新 (执行进度、审计事件)?                                            │
│  │   └─► WebSocket (订阅 topic, 接收推送)                                        │
│  ├─ CRUD 操作 (创建workflow, 查询状态)?                                          │
│  │   └─► REST (简单, 易调试)                                                     │
│  └─ 交互式调试 (inspect state, step through)?                                   │
│      └─► WebSocket (双向通信)                                                    │
│                                                                                  │
│  后端服务/微服务?                                                                 │
│  ├─ 高频调用 (Ray worker 汇报进度)?                                              │
│  │   └─► gRPC (高性能, 低延迟)                                                   │
│  ├─ 流式数据 (实时audit stream)?                                                 │
│  │   └─► gRPC streaming (服务端推送)                                             │
│  └─ 偶发调用 (触发执行, 查询结果)?                                                │
│      └─► REST (简单集成)                                                         │
│                                                                                  │
│  CLI 工具?                                                                       │
│  ├─ 简单命令 (wtb run, wtb pause)?                                              │
│  │   └─► REST (curl 友好)                                                        │
│  └─ 监控模式 (wtb watch)?                                                        │
│      └─► gRPC streaming 或 WebSocket                                             │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════════│
│                                                                                  │
│  ⚠️ 重要: 三种协议同时运行! 客户端可以混合使用:                                    │
│                                                                                  │
│  Web UI 典型模式:                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  1. REST: 加载页面数据 (GET /workflows, GET /executions)                  │   │
│  │  2. REST: 发起操作 (POST /executions/{id}/pause)                          │   │
│  │  3. WebSocket: 订阅实时更新 (subscribe execution:{id})                    │   │
│  │  4. WebSocket: 接收进度推送 (onmessage: NodeCompleted, StateChanged)      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  Ray Worker 典型模式:                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  1. gRPC: 获取任务 (GetTask)                                              │   │
│  │  2. gRPC streaming: 汇报进度 (StreamProgress)                             │   │
│  │  3. gRPC: 提交结果 (SubmitResult)                                         │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1.1 Protocol Comparison Matrix

| Dimension | REST | gRPC | WebSocket |
|-----------|------|------|-----------|
| **请求模式** | Request/Response | Request/Response + Streaming | Bidirectional |
| **数据格式** | JSON | Protobuf (binary) | JSON/Binary |
| **浏览器支持** | ✅ 原生 | ❌ 需要 grpc-web | ✅ 原生 |
| **延迟** | 中等 | 低 | 低 |
| **调试难度** | 简单 (curl) | 中等 (grpcurl) | 中等 |
| **连接管理** | 无状态 | 可复用连接 | 长连接 |
| **适合场景** | CRUD, 外部API | 内部服务, 高频 | 实时推送, UI |

### 1.1.2 Which Protocol for Which Operation?

| 操作类型 | 推荐协议 | 原因 |
|----------|----------|------|
| **Workflow CRUD** | REST | 低频, 需要易读性 |
| **Start Execution** | REST 或 gRPC | 一次性操作 |
| **Pause/Resume/Stop** | REST | 低频控制操作 |
| **Execute Single Node** | REST 或 gRPC | 一次性操作 |
| **Modify State** | REST | 需要人工检查 JSON |
| **Create Branch** | REST | 低频操作 |
| **Stream Execution Progress** | **WebSocket** (UI) / **gRPC** (服务) | 需要实时推送 |
| **Stream Audit Events** | **WebSocket** (UI) / **gRPC** (服务) | 需要实时推送 |
| **Batch Test Progress** | **gRPC streaming** | 高频更新 |
| **Ray Worker Communication** | **gRPC** | 高性能需求 |
| **Interactive Debug Session** | **WebSocket** | 双向交互 |

### 1.1.3 Can I Use Multiple Protocols Simultaneously?

**YES! 这是设计意图!**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-PROTOCOL ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  同一个 WTB 服务器同时监听三个端口:                                                │
│                                                                                  │
│  Port 8000 ───────────────────────────────────────────────────────────────────  │
│  │                                                                              │
│  ├── /api/v1/*     → REST endpoints (FastAPI)                                  │
│  └── /ws           → WebSocket endpoint (FastAPI)                              │
│                                                                                  │
│  Port 50051 ──────────────────────────────────────────────────────────────────  │
│  │                                                                              │
│  └── WTBService    → gRPC server (grpc-aio)                                    │
│                                                                                  │
│  所有协议共享同一个 Application Service Layer:                                    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       Application Services                               │   │
│  │                                                                          │   │
│  │   ExecutionService  │  BatchTestService  │  AuditService  │  ...        │   │
│  │                                                                          │   │
│  │   (所有协议调用同一套 service, 保证行为一致)                               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**典型混合使用场景:**

```python
# Web UI: REST + WebSocket 混合
async def dashboard():
    # 1. REST: 获取初始数据
    executions = await fetch("/api/v1/executions")
    
    # 2. WebSocket: 订阅实时更新
    ws = await connect("/ws")
    await ws.send({"action": "subscribe", "topics": ["execution:*"]})
    
    # 3. REST: 用户点击按钮
    await fetch("/api/v1/executions/123/pause", method="POST")
    
    # 4. WebSocket: 自动收到状态更新
    # onmessage: {"type": "ExecutionPaused", "execution_id": "123", ...}

# 后端服务: REST + gRPC 混合
async def backend_service():
    # 1. REST: 触发批量测试 (外部 API)
    await http_client.post("/api/v1/batch-tests", data=config)
    
    # 2. gRPC: 订阅进度 (内部高频)
    async for progress in grpc_client.StreamBatchProgress(request):
        update_internal_state(progress)
```

### 1.2 Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         WTB EXTERNAL API ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                          EXTERNAL CLIENTS                                  │  │
│  │                                                                            │  │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │   │   Web UI    │  │   CLI Tool  │  │   IDE Plugin│  │ External Service│  │  │
│  │   │  (Browser)  │  │             │  │ (VS Code)   │  │  (LangSmith)    │  │  │
│  │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │  │
│  │          │                │                │                  │           │  │
│  └──────────┼────────────────┼────────────────┼──────────────────┼───────────┘  │
│             │                │                │                  │              │
│             │ WebSocket      │ REST           │ gRPC             │ REST/gRPC   │
│             │ + REST         │                │                  │              │
│             ▼                ▼                ▼                  ▼              │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                          API GATEWAY LAYER                                 │  │
│  │                                                                            │  │
│  │   Port 8000 (REST)     Port 50051 (gRPC)      Port 8000/ws (WebSocket)   │  │
│  │   ┌─────────────────┐  ┌─────────────────┐    ┌─────────────────────────┐ │  │
│  │   │  FastAPI        │  │  gRPC Server    │    │  WebSocket Handler      │ │  │
│  │   │  ┌───────────┐  │  │  ┌───────────┐  │    │  ┌───────────────────┐  │ │  │
│  │   │  │ /api/v1/  │  │  │  │ WTBService│  │    │  │ ConnectionManager │  │ │  │
│  │   │  │ workflows │  │  │  │ .Execute  │  │    │  │ • subscribe       │  │ │  │
│  │   │  │ executions│  │  │  │ .Stream   │  │    │  │ • broadcast       │  │ │  │
│  │   │  │ audit     │  │  │  │ .Control  │  │    │  │ • heartbeat       │  │ │  │
│  │   │  │ batch     │  │  │  │           │  │    │  │                   │  │ │  │
│  │   │  └───────────┘  │  │  └───────────┘  │    │  └───────────────────┘  │ │  │
│  │   └────────┬────────┘  └────────┬────────┘    └───────────┬─────────────┘ │  │
│  │            │                    │                         │               │  │
│  └────────────┼────────────────────┼─────────────────────────┼───────────────┘  │
│               │                    │                         │                  │
│               └────────────────────┴─────────────────────────┘                  │
│                                    │                                            │
│                                    ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                       APPLICATION SERVICE LAYER                            │  │
│  │                                                                            │  │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐   │  │
│  │   │ ExecutionService│  │ WorkflowService │  │ AuditService            │   │  │
│  │   │ ├─ start()      │  │ ├─ create()     │  │ ├─ get_trail()          │   │  │
│  │   │ ├─ pause()      │  │ ├─ update()     │  │ ├─ stream_events()      │   │  │
│  │   │ ├─ resume()     │  │ ├─ delete()     │  │ ├─ query()              │   │  │
│  │   │ ├─ stop()       │  │ └─ list()       │  │ └─ get_metrics_summary()│   │  │
│  │   │ └─ rollback()   │  │                 │  │                         │   │  │
│  │   └─────────────────┘  └─────────────────┘  └─────────────────────────┘   │  │
│  │                                                                            │  │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐   │  │
│  │   │ BatchTestService│  │ EnvironmentSvc  │  │ MetricsService          │   │  │
│  │   │ ├─ run_batch()  │  │ (via gRPC to    │  │ ├─ get_prometheus()     │   │  │
│  │   │ ├─ compare()    │  │  UV Venv Mgr)   │  │ ├─ record_custom()      │   │  │
│  │   │ └─ get_matrix() │  │                 │  │ └─ get_dashboard_data() │   │  │
│  │   └─────────────────┘  └─────────────────┘  └─────────────────────────┘   │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                         DOMAIN LAYER                                       │  │
│  │                                                                            │  │
│  │   ExecutionController  │  NodeReplacer  │  RayBatchTestRunner             │  │
│  │   LangGraphStateAdapter│  WTBEventBus   │  WTBAuditTrail                  │  │
│  │                                                                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. REST API Design

### 2.1 Resource Structure (Fine-Grained Control)

```yaml
/api/v1:
  # ═══════════════════════════════════════════════════════════════
  # Workflow Definition Management
  # ═══════════════════════════════════════════════════════════════
  /workflows:
    GET     - List all workflows
    POST    - Create workflow
    /{id}:
      GET     - Get workflow details
      PUT     - Update entire workflow
      PATCH   - Partial update (specific fields only)
      DELETE  - Delete workflow
      
      # Node-level modifications (within workflow definition)
      /nodes:
        GET   - List all nodes in workflow
        POST  - Add new node to workflow
        /{node_id}:
          GET     - Get node definition
          PUT     - Update node definition (hot-swap)
          DELETE  - Remove node from workflow
          /variants:
            GET   - List registered variants for this node
            POST  - Register new variant
      
      # Workflow-level batch testing
      /batch-test:
        POST  - Run batch test on entire workflow with variant combinations
      
      # Start execution
      /execute:
        POST  - Start execution (returns execution_id)

  # ═══════════════════════════════════════════════════════════════
  # Execution Control (Fine-Grained)
  # ═══════════════════════════════════════════════════════════════
  /executions:
    GET     - List executions (filter by workflow_id, status)
    /{id}:
      GET     - Get execution status, current state, current node
      
      # Lifecycle Control
      /pause:
        POST  - Pause execution (at current node or specified node)
      /resume:
        POST  - Resume execution (optional: modified_state, from_node)
      /stop:
        POST  - Stop/cancel execution
      
      # Checkpoint & Branching
      /checkpoints:
        GET   - List all checkpoints
        POST  - Create manual checkpoint at current position
        /{checkpoint_id}:
          GET   - Get checkpoint details and state
      /rollback:
        POST  - Rollback to checkpoint (in-place or create branch)
      /branches:
        GET   - List branches from this execution
        POST  - Create new branch from checkpoint
        /{branch_id}:
          GET   - Get branch details
          /switch:
            POST  - Switch to this branch
      
      # State Inspection & Modification
      /state:
        GET   - Get current execution state
        PATCH - Modify state (human-in-the-loop)
      
      # Node-Level Control (within execution)
      /nodes:
        GET   - List nodes with execution status
        /{node_id}:
          GET   - Get node execution details
          /execute:
            POST  - Execute single node (skip to this node)
          /skip:
            POST  - Skip this node
          /retry:
            POST  - Retry failed node
          /batch-test:
            POST  - Run batch test on this single node with variants
      
      # Audit
      /audit:
        GET   - Get audit trail for execution

  # ═══════════════════════════════════════════════════════════════
  # Batch Testing (Workflow-Level & Node-Level)
  # ═══════════════════════════════════════════════════════════════
  /batch-tests:
    GET     - List batch tests
    POST    - Create batch test (workflow or node level)
    /{id}:
      GET     - Get batch test status and progress
      /results:
        GET   - Get comparison matrix
      /stop:
        POST  - Stop batch test
      /variants/{variant_id}:
        GET   - Get specific variant result

  # ═══════════════════════════════════════════════════════════════
  # Node Variants Registry (Global)
  # ═══════════════════════════════════════════════════════════════
  /variants:
    GET     - List all registered variants
    POST    - Register new variant
    /{id}:
      GET     - Get variant details
      PUT     - Update variant
      DELETE  - Delete variant

  # ═══════════════════════════════════════════════════════════════
  # Audit & Observability
  # ═══════════════════════════════════════════════════════════════
  /audit:
    /events:
      GET     - Query audit events (filter by execution_id, type, time_range)
    /summary:
      GET     - Get audit summary statistics
  
  /metrics:
    GET     - Prometheus metrics endpoint (/metrics)
  
  /health:
    GET     - Health check
    /ready:
      GET   - Readiness check
```

### 2.1.1 Fine-Grained Control Operations Summary

| Operation | Level | Endpoint | Description |
|-----------|-------|----------|-------------|
| **Update Node** | Workflow | `PUT /workflows/{id}/nodes/{node_id}` | Hot-swap node definition |
| **Branch** | Execution | `POST /executions/{id}/branches` | Create branch from checkpoint |
| **Switch Branch** | Execution | `POST /executions/{id}/branches/{branch_id}/switch` | Switch to branch |
| **Execute Single Node** | Execution | `POST /executions/{id}/nodes/{node_id}/execute` | Run specific node |
| **Skip Node** | Execution | `POST /executions/{id}/nodes/{node_id}/skip` | Skip node execution |
| **Retry Node** | Execution | `POST /executions/{id}/nodes/{node_id}/retry` | Retry failed node |
| **Pause** | Execution | `POST /executions/{id}/pause` | Pause at current/specified node |
| **Resume** | Execution | `POST /executions/{id}/resume` | Resume with optional state changes |
| **Modify State** | Execution | `PATCH /executions/{id}/state` | Human-in-the-loop state edit |
| **Workflow Batch Test** | Workflow | `POST /workflows/{id}/batch-test` | Test workflow with variant combos |
| **Node Batch Test** | Execution | `POST /executions/{id}/nodes/{node_id}/batch-test` | Test single node with variants |

### 2.2 REST API Implementation Pattern

```python
# wtb/api/rest/routes/executions.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from wtb.api.rest.dependencies import get_execution_service, get_audit_service
from wtb.api.rest.models import (
    ExecutionCreateRequest,
    ExecutionResponse,
    ExecutionListResponse,
    PauseRequest,
    ResumeRequest,
    RollbackRequest,
    CheckpointListResponse,
    AuditTrailResponse,
)
from wtb.application.services import ExecutionService, AuditService

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """List executions with optional filtering."""
    return await execution_service.list_executions(
        workflow_id=workflow_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """Get execution details including current state."""
    execution = await execution_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.post("/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    request: PauseRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """Pause a running execution at the current or specified node."""
    result = await execution_service.pause(
        execution_id=execution_id,
        reason=request.reason,
        at_node=request.at_node,
    )
    return {"status": "paused", "checkpoint_id": result.checkpoint_id}


@router.post("/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    request: ResumeRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """Resume a paused execution, optionally with modified state."""
    result = await execution_service.resume(
        execution_id=execution_id,
        modified_state=request.modified_state,
        from_node=request.from_node,
    )
    return {"status": "resumed", "resumed_from": result.resumed_from_node}


@router.post("/{execution_id}/rollback")
async def rollback_execution(
    execution_id: str,
    request: RollbackRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
):
    """Rollback execution to a specific checkpoint."""
    result = await execution_service.rollback(
        execution_id=execution_id,
        checkpoint_id=request.checkpoint_id,
        create_branch=request.create_branch,
    )
    return {
        "status": "rolled_back",
        "to_checkpoint": request.checkpoint_id,
        "new_session_id": result.new_session_id,
        "tools_reversed": result.tools_reversed,
    }


@router.get("/{execution_id}/audit", response_model=AuditTrailResponse)
async def get_execution_audit(
    execution_id: str,
    include_debug: bool = False,
    limit: int = 100,
    audit_service: AuditService = Depends(get_audit_service),
):
    """Get audit trail for an execution."""
    trail = await audit_service.get_trail_for_execution(
        execution_id=execution_id,
        include_debug=include_debug,
        limit=limit,
    )
    return trail
```

---

## 3. gRPC API Design

### 3.1 Proto Definition

```protobuf
// wtb/api/grpc/protos/wtb_service.proto

syntax = "proto3";

package wtb.v1;

import "google/protobuf/timestamp.proto";
import "google/protobuf/struct.proto";

// ═══════════════════════════════════════════════════════════════
// Main WTB Service
// ═══════════════════════════════════════════════════════════════

service WTBService {
    // Execution Control
    rpc StartExecution(StartExecutionRequest) returns (ExecutionResponse);
    rpc PauseExecution(PauseExecutionRequest) returns (ControlResponse);
    rpc ResumeExecution(ResumeExecutionRequest) returns (ControlResponse);
    rpc StopExecution(StopExecutionRequest) returns (ControlResponse);
    rpc RollbackExecution(RollbackRequest) returns (RollbackResponse);
    
    // Execution Streaming (for Ray workers)
    rpc StreamExecutionEvents(ExecutionStreamRequest) returns (stream ExecutionEvent);
    rpc StreamCheckpoints(CheckpointStreamRequest) returns (stream CheckpointEvent);
    
    // Batch Testing
    rpc RunBatchTest(BatchTestRequest) returns (stream BatchTestProgress);
    rpc GetBatchTestResults(BatchTestResultsRequest) returns (BatchTestResultsResponse);
    
    // Audit Event Streaming
    rpc StreamAuditEvents(AuditStreamRequest) returns (stream AuditEvent);
    
    // Bidirectional Control Stream (for interactive debugging)
    rpc InteractiveSession(stream InteractiveCommand) returns (stream InteractiveResponse);
}

// ═══════════════════════════════════════════════════════════════
// Execution Messages
// ═══════════════════════════════════════════════════════════════

message StartExecutionRequest {
    string workflow_id = 1;
    google.protobuf.Struct initial_state = 2;
    repeated string breakpoints = 3;
    ExecutionConfig config = 4;
}

message ExecutionConfig {
    bool enable_file_tracking = 1;
    bool enable_audit = 2;
    int32 checkpoint_interval = 3;  // 0 = every node, N = every N nodes
    map<string, string> metadata = 4;
}

message ExecutionResponse {
    string execution_id = 1;
    string status = 2;
    string thread_id = 3;  // LangGraph thread_id
    google.protobuf.Timestamp started_at = 4;
}

message PauseExecutionRequest {
    string execution_id = 1;
    string reason = 2;
    string at_node = 3;  // Optional: pause at specific node
}

message ResumeExecutionRequest {
    string execution_id = 1;
    google.protobuf.Struct modified_state = 2;  // Optional state modifications
    string from_node = 3;  // Optional: resume from specific node
}

message StopExecutionRequest {
    string execution_id = 1;
    string reason = 2;
}

message ControlResponse {
    bool success = 1;
    string status = 2;
    string checkpoint_id = 3;
    string message = 4;
}

message RollbackRequest {
    string execution_id = 1;
    string checkpoint_id = 2;
    bool create_branch = 3;  // Create new session or modify in-place
}

message RollbackResponse {
    bool success = 1;
    string new_session_id = 2;  // If branch created
    int32 tools_reversed = 3;
    int32 files_restored = 4;
    google.protobuf.Struct restored_state = 5;
}

// ═══════════════════════════════════════════════════════════════
// Streaming Messages
// ═══════════════════════════════════════════════════════════════

message ExecutionStreamRequest {
    string execution_id = 1;
    repeated string event_types = 2;  // Filter: NODE_START, NODE_END, CHECKPOINT, etc.
}

message ExecutionEvent {
    string event_id = 1;
    string execution_id = 2;
    EventType type = 3;
    google.protobuf.Timestamp timestamp = 4;
    oneof payload {
        NodeStartEvent node_start = 5;
        NodeEndEvent node_end = 6;
        CheckpointEvent checkpoint = 7;
        StateChangeEvent state_change = 8;
        ErrorEvent error = 9;
    }
}

enum EventType {
    EVENT_TYPE_UNSPECIFIED = 0;
    NODE_START = 1;
    NODE_END = 2;
    CHECKPOINT_CREATED = 3;
    EXECUTION_PAUSED = 4;
    EXECUTION_RESUMED = 5;
    EXECUTION_COMPLETED = 6;
    EXECUTION_FAILED = 7;
    STATE_MODIFIED = 8;
    ROLLBACK_PERFORMED = 9;
}

message NodeStartEvent {
    string node_id = 1;
    string node_name = 2;
    string node_type = 3;
    string entry_checkpoint_id = 4;
}

message NodeEndEvent {
    string node_id = 1;
    string node_name = 2;
    bool success = 3;
    int64 duration_ms = 4;
    int32 tool_invocations = 5;
    string exit_checkpoint_id = 6;
    string error = 7;
}

message CheckpointEvent {
    string checkpoint_id = 1;
    string node_id = 2;
    string trigger_type = 3;  // node_entry, node_exit, manual, auto
    bool has_file_commit = 4;
}

message StateChangeEvent {
    string source = 1;  // manual, tool, rollback
    repeated string changed_keys = 2;
}

message ErrorEvent {
    string error_type = 1;
    string message = 2;
    string node_id = 3;
    bool recoverable = 4;
}

// ═══════════════════════════════════════════════════════════════
// Batch Test Messages
// ═══════════════════════════════════════════════════════════════

message BatchTestRequest {
    string workflow_id = 1;
    repeated VariantCombination variants = 2;
    google.protobuf.Struct initial_state = 3;
    int32 parallelism = 4;  // 0 = auto
    bool use_ray = 5;
}

message VariantCombination {
    string name = 1;
    map<string, string> node_variants = 2;  // node_id → variant_id
}

message BatchTestProgress {
    string batch_test_id = 1;
    int32 total_variants = 2;
    int32 completed = 3;
    int32 failed = 4;
    VariantProgress current_variant = 5;
    float estimated_remaining_seconds = 6;
}

message VariantProgress {
    string variant_name = 1;
    string status = 2;  // running, completed, failed
    string current_node = 3;
    float progress_percent = 4;
}

message BatchTestResultsRequest {
    string batch_test_id = 1;
}

message BatchTestResultsResponse {
    string batch_test_id = 1;
    string status = 2;
    ComparisonMatrix matrix = 3;
    google.protobuf.Timestamp completed_at = 4;
}

message ComparisonMatrix {
    repeated string metric_names = 1;
    repeated VariantResult variants = 2;
    string best_variant = 3;
}

message VariantResult {
    string variant_name = 1;
    map<string, double> metrics = 2;
    double overall_score = 3;
    string status = 4;
    string error = 5;
}

// ═══════════════════════════════════════════════════════════════
// Audit Stream Messages
// ═══════════════════════════════════════════════════════════════

message AuditStreamRequest {
    string execution_id = 1;  // Optional: filter by execution
    repeated string event_types = 2;
    google.protobuf.Timestamp since = 3;
    bool include_debug = 4;
}

message AuditEvent {
    string event_id = 1;
    google.protobuf.Timestamp timestamp = 2;
    string event_type = 3;
    string severity = 4;  // info, success, warning, error, debug
    string message = 5;
    string execution_id = 6;
    string node_id = 7;
    google.protobuf.Struct details = 8;
    string error = 9;
    int64 duration_ms = 10;
}

// ═══════════════════════════════════════════════════════════════
// Interactive Session (Bidirectional)
// ═══════════════════════════════════════════════════════════════

message InteractiveCommand {
    string execution_id = 1;
    oneof command {
        InspectStateCommand inspect_state = 2;
        ModifyStateCommand modify_state = 3;
        SetBreakpointCommand set_breakpoint = 4;
        StepCommand step = 5;
        ContinueCommand continue_exec = 6;
    }
}

message InspectStateCommand {
    repeated string keys = 1;  // Empty = all keys
}

message ModifyStateCommand {
    google.protobuf.Struct changes = 1;
}

message SetBreakpointCommand {
    string node_id = 1;
    bool enabled = 2;
}

message StepCommand {
    int32 steps = 1;  // Number of nodes to execute
}

message ContinueCommand {
    string until_node = 1;  // Optional: run until this node
}

message InteractiveResponse {
    bool success = 1;
    string message = 2;
    oneof payload {
        StateInspectionResult state = 3;
        ExecutionStatusResult status = 4;
    }
}

message StateInspectionResult {
    google.protobuf.Struct state = 1;
    string current_node = 2;
}

message ExecutionStatusResult {
    string status = 1;
    string current_node = 2;
    string last_checkpoint_id = 3;
}
```

### 3.2 gRPC Server Implementation Pattern

```python
# wtb/api/grpc/servicer.py

from typing import AsyncIterator
from grpc import aio
from datetime import datetime

from wtb.api.grpc.generated import wtb_service_pb2 as pb2
from wtb.api.grpc.generated import wtb_service_pb2_grpc as pb2_grpc
from wtb.application.services import (
    ExecutionService,
    BatchTestService,
    AuditService,
)
from wtb.infrastructure.events import WTBEventBus


class WTBServicer(pb2_grpc.WTBServiceServicer):
    """
    gRPC servicer for WTB.
    
    Provides:
    - Execution control (start, pause, resume, stop, rollback)
    - Event streaming (execution events, audit events)
    - Batch test management
    - Interactive debugging session
    """
    
    def __init__(
        self,
        execution_service: ExecutionService,
        batch_test_service: BatchTestService,
        audit_service: AuditService,
        event_bus: WTBEventBus,
    ):
        self._execution_service = execution_service
        self._batch_test_service = batch_test_service
        self._audit_service = audit_service
        self._event_bus = event_bus
    
    async def StartExecution(
        self,
        request: pb2.StartExecutionRequest,
        context: aio.ServicerContext,
    ) -> pb2.ExecutionResponse:
        """Start a new workflow execution."""
        result = await self._execution_service.start(
            workflow_id=request.workflow_id,
            initial_state=dict(request.initial_state),
            breakpoints=list(request.breakpoints),
            config={
                "enable_file_tracking": request.config.enable_file_tracking,
                "enable_audit": request.config.enable_audit,
                "checkpoint_interval": request.config.checkpoint_interval,
            },
        )
        
        return pb2.ExecutionResponse(
            execution_id=result.execution_id,
            status=result.status,
            thread_id=result.thread_id,
            started_at=result.started_at,
        )
    
    async def StreamExecutionEvents(
        self,
        request: pb2.ExecutionStreamRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[pb2.ExecutionEvent]:
        """Stream execution events in real-time."""
        execution_id = request.execution_id
        event_types = set(request.event_types) if request.event_types else None
        
        # Subscribe to event bus
        event_queue = asyncio.Queue()
        
        def event_handler(event):
            if event_types is None or event.event_type in event_types:
                if event.execution_id == execution_id:
                    event_queue.put_nowait(event)
        
        # Subscribe to all relevant event types
        self._event_bus.subscribe_all(event_handler)
        
        try:
            while True:
                # Check if client disconnected
                if context.cancelled():
                    break
                
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    yield self._convert_to_proto_event(event)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._event_bus.unsubscribe_all(event_handler)
    
    async def StreamAuditEvents(
        self,
        request: pb2.AuditStreamRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[pb2.AuditEvent]:
        """Stream audit events in real-time."""
        # Implementation similar to StreamExecutionEvents
        # but filtered for audit-specific events
        ...
    
    async def RunBatchTest(
        self,
        request: pb2.BatchTestRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[pb2.BatchTestProgress]:
        """Run batch test with progress streaming."""
        batch_test_id = await self._batch_test_service.create_batch_test(
            workflow_id=request.workflow_id,
            variants=[
                {
                    "name": v.name,
                    "node_variants": dict(v.node_variants),
                }
                for v in request.variants
            ],
            initial_state=dict(request.initial_state),
            parallelism=request.parallelism or None,
            use_ray=request.use_ray,
        )
        
        # Stream progress updates
        async for progress in self._batch_test_service.stream_progress(batch_test_id):
            yield pb2.BatchTestProgress(
                batch_test_id=batch_test_id,
                total_variants=progress.total,
                completed=progress.completed,
                failed=progress.failed,
                current_variant=pb2.VariantProgress(
                    variant_name=progress.current.name if progress.current else "",
                    status=progress.current.status if progress.current else "",
                    current_node=progress.current.node if progress.current else "",
                    progress_percent=progress.current.percent if progress.current else 0,
                ),
                estimated_remaining_seconds=progress.eta_seconds,
            )
    
    async def InteractiveSession(
        self,
        request_iterator: AsyncIterator[pb2.InteractiveCommand],
        context: aio.ServicerContext,
    ) -> AsyncIterator[pb2.InteractiveResponse]:
        """Bidirectional interactive debugging session."""
        async for command in request_iterator:
            if context.cancelled():
                break
            
            response = await self._handle_interactive_command(command)
            yield response
    
    async def _handle_interactive_command(
        self,
        command: pb2.InteractiveCommand,
    ) -> pb2.InteractiveResponse:
        """Handle interactive debugging command."""
        execution_id = command.execution_id
        
        if command.HasField("inspect_state"):
            state = await self._execution_service.inspect_state(
                execution_id=execution_id,
                keys=list(command.inspect_state.keys) or None,
            )
            return pb2.InteractiveResponse(
                success=True,
                state=pb2.StateInspectionResult(
                    state=state.values,
                    current_node=state.current_node,
                ),
            )
        
        elif command.HasField("modify_state"):
            await self._execution_service.modify_state(
                execution_id=execution_id,
                changes=dict(command.modify_state.changes),
            )
            return pb2.InteractiveResponse(
                success=True,
                message="State modified",
            )
        
        elif command.HasField("step"):
            result = await self._execution_service.step(
                execution_id=execution_id,
                steps=command.step.steps,
            )
            return pb2.InteractiveResponse(
                success=True,
                status=pb2.ExecutionStatusResult(
                    status=result.status,
                    current_node=result.current_node,
                    last_checkpoint_id=result.last_checkpoint_id,
                ),
            )
        
        # ... handle other commands
```

---

## 4. WebSocket API Design

### 4.1 WebSocket Endpoint Structure

```python
# wtb/api/websocket/handlers.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json

from wtb.infrastructure.events import WTBEventBus


class ConnectionManager:
    """
    Manages WebSocket connections and subscriptions.
    
    Supports:
    - Topic-based subscriptions (execution:123, audit:*, batch:456)
    - Broadcast to topic subscribers
    - Heartbeat/keepalive
    """
    
    def __init__(self, event_bus: WTBEventBus):
        self._connections: Dict[str, WebSocket] = {}
        self._subscriptions: Dict[str, Set[str]] = {}  # topic → {connection_ids}
        self._event_bus = event_bus
        self._setup_event_bridge()
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept WebSocket connection."""
        await websocket.accept()
        self._connections[client_id] = websocket
    
    async def disconnect(self, client_id: str):
        """Handle WebSocket disconnection."""
        if client_id in self._connections:
            del self._connections[client_id]
        
        # Remove from all subscriptions
        for topic in list(self._subscriptions.keys()):
            self._subscriptions[topic].discard(client_id)
    
    async def subscribe(self, client_id: str, topics: list[str]):
        """Subscribe client to topics."""
        for topic in topics:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = set()
            self._subscriptions[topic].add(client_id)
    
    async def unsubscribe(self, client_id: str, topics: list[str]):
        """Unsubscribe client from topics."""
        for topic in topics:
            if topic in self._subscriptions:
                self._subscriptions[topic].discard(client_id)
    
    async def broadcast_to_topic(self, topic: str, message: dict):
        """Broadcast message to all subscribers of a topic."""
        if topic not in self._subscriptions:
            return
        
        for client_id in self._subscriptions[topic]:
            if client_id in self._connections:
                try:
                    await self._connections[client_id].send_json(message)
                except Exception:
                    # Connection broken, will be cleaned up
                    pass
    
    def _setup_event_bridge(self):
        """Bridge WTB events to WebSocket topics."""
        from wtb.domain.events import (
            ExecutionStartedEvent,
            ExecutionCompletedEvent,
            ExecutionFailedEvent,
            ExecutionPausedEvent,
            NodeStartedEvent,
            NodeCompletedEvent,
            NodeFailedEvent,
        )
        
        async def handle_execution_event(event):
            topic = f"execution:{event.execution_id}"
            await self.broadcast_to_topic(topic, {
                "type": event.__class__.__name__,
                "execution_id": event.execution_id,
                "timestamp": event.timestamp.isoformat(),
                "data": event.to_dict(),
            })
            
            # Also broadcast to wildcard subscribers
            await self.broadcast_to_topic("execution:*", {
                "type": event.__class__.__name__,
                "execution_id": event.execution_id,
                "timestamp": event.timestamp.isoformat(),
                "data": event.to_dict(),
            })
        
        # Subscribe to all execution-related events
        for event_type in [
            ExecutionStartedEvent,
            ExecutionCompletedEvent,
            ExecutionFailedEvent,
            ExecutionPausedEvent,
            NodeStartedEvent,
            NodeCompletedEvent,
            NodeFailedEvent,
        ]:
            self._event_bus.subscribe(
                event_type,
                lambda e: asyncio.create_task(handle_execution_event(e))
            )


# WebSocket endpoint
async def websocket_endpoint(
    websocket: WebSocket,
    connection_manager: ConnectionManager,
):
    """
    WebSocket endpoint for real-time updates.
    
    Protocol:
    - Client sends: {"action": "subscribe", "topics": ["execution:123", "audit:*"]}
    - Client sends: {"action": "unsubscribe", "topics": ["execution:123"]}
    - Server sends: {"type": "NodeCompleted", "execution_id": "123", "data": {...}}
    """
    import uuid
    client_id = str(uuid.uuid4())
    
    await connection_manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "subscribe":
                await connection_manager.subscribe(client_id, data.get("topics", []))
            elif action == "unsubscribe":
                await connection_manager.unsubscribe(client_id, data.get("topics", []))
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        await connection_manager.disconnect(client_id)
```

---

## 5. Observability Architecture

### 5.0 关键澄清: OpenTelemetry / Prometheus / Grafana 不是二选一!

> **这是一个完整的观测栈，三者配合使用，不是替代关系!**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK 角色划分 (不是二选一!)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                             │ │
│  │   OpenTelemetry    =    SDK / 抽象层 / 埋点工具                             │ │
│  │   ═══════════════       ══════════════════════════                         │ │
│  │                                                                             │ │
│  │   作用: 在代码中埋点，收集 traces/metrics/logs                               │ │
│  │   特点: 厂商无关 (vendor-neutral)，一套 SDK 可导出到多个后端                  │ │
│  │   类比: 就像 JDBC - 统一接口，不同数据库实现                                  │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                          │
│                                       │ 导出数据到                               │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                             │ │
│  │   Prometheus       =    Metrics 存储后端 (时序数据库)                        │ │
│  │   ══════════════        ══════════════════════════════                      │ │
│  │                                                                             │ │
│  │   作用: 存储时序指标数据 (counters, gauges, histograms)                      │ │
│  │   特点: Pull 模型, PromQL 查询语言, 自带告警                                 │ │
│  │   WTB 已有: MetricsEventListener 直接导出 Prometheus 格式                    │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                          │
│                                       │ 查询数据                                 │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                             │ │
│  │   Grafana          =    可视化 Dashboard + 告警                              │ │
│  │   ═══════════════       ═══════════════════════════                         │ │
│  │                                                                             │ │
│  │   作用: 连接多个数据源 (Prometheus, Jaeger, Loki), 统一展示                  │ │
│  │   特点: 丰富的图表, 告警规则, 多数据源整合                                    │ │
│  │   输出: 发送告警到 Slack/PagerDuty/Email                                    │ │
│  │                                                                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════════│
│                                                                                  │
│  完整数据流:                                                                     │
│                                                                                  │
│  WTB Code                                                                        │
│      │                                                                           │
│      │ ① OpenTelemetry SDK 埋点                                                 │
│      ▼                                                                           │
│  ┌─────────────┐                                                                │
│  │ OTel SDK    │                                                                │
│  │ • Tracer    │─────┬─────────────────────────────────────────────────────┐    │
│  │ • Meter     │     │                                                     │    │
│  │ • Logger    │     │ ② 导出到各个后端                                     │    │
│  └─────────────┘     │                                                     │    │
│                      ▼                           ▼                         ▼    │
│              ┌─────────────┐           ┌─────────────┐           ┌─────────────┐│
│              │  Jaeger     │           │ Prometheus  │           │    Loki     ││
│              │  (Traces)   │           │ (Metrics)   │           │   (Logs)    ││
│              └──────┬──────┘           └──────┬──────┘           └──────┬──────┘│
│                     │                         │                         │       │
│                     └─────────────────────────┼─────────────────────────┘       │
│                                               │                                  │
│                                               │ ③ Grafana 统一查询展示          │
│                                               ▼                                  │
│                                       ┌─────────────┐                           │
│                                       │   Grafana   │                           │
│                                       │ Dashboards  │                           │
│                                       └─────────────┘                           │
│                                               │                                  │
│                                               │ ④ 告警                          │
│                                               ▼                                  │
│                                       ┌─────────────┐                           │
│                                       │   Slack /   │                           │
│                                       │  PagerDuty  │                           │
│                                       └─────────────┘                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.0.1 WTB 观测栈最终决策

| 层级 | 技术选择 | 原因 |
|------|----------|------|
| **埋点层 (SDK)** | **OpenTelemetry** | 厂商无关, 未来可换后端 |
| **Metrics 后端** | **Prometheus** | 已有 `MetricsEventListener` 集成, 成熟稳定 |
| **Traces 后端** | **Jaeger** 或 **Tempo** | 分布式追踪, 可选 |
| **Logs 后端** | **Loki** 或 **CloudWatch** | 可选, 按需启用 |
| **可视化** | **Grafana** | 统一 dashboard, 多数据源 |

**最小可行观测栈 (MVP):**

```
WTB App  →  Prometheus (直接导出, 已有)  →  Grafana
```

**完整观测栈:**

```
WTB App  →  OpenTelemetry SDK  →  ┬─ Prometheus (metrics)  ─→  Grafana
                                  ├─ Jaeger (traces)       ─┘
                                  └─ Loki (logs)           ─┘
```

### 5.1 OpenTelemetry Integration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         OBSERVABILITY STACK                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        WTB APPLICATION                                      │ │
│  │                                                                             │ │
│  │   ┌─────────────────────────────────────────────────────────────────────┐  │ │
│  │   │                  OpenTelemetry SDK                                   │  │ │
│  │   │                                                                      │  │ │
│  │   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │  │ │
│  │   │  │   Tracer    │  │   Meter     │  │    Logger                   │  │  │ │
│  │   │  │             │  │             │  │                             │  │  │ │
│  │   │  │ • Spans     │  │ • Counter   │  │ • Structured logs           │  │  │ │
│  │   │  │ • Traces    │  │ • Histogram │  │ • Correlation IDs           │  │  │ │
│  │   │  │ • Context   │  │ • Gauge     │  │ • Log levels                │  │  │ │
│  │   │  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────┘  │  │ │
│  │   │         │                │                        │                 │  │ │
│  │   │         └────────────────┴────────────────────────┘                 │  │ │
│  │   │                          │                                          │  │ │
│  │   │                          ▼                                          │  │ │
│  │   │  ┌──────────────────────────────────────────────────────────────┐  │  │ │
│  │   │  │              OpenTelemetry Collector (OTel)                   │  │  │ │
│  │   │  │              (Optional - can export directly)                │  │  │ │
│  │   │  └──────────────────────────┬───────────────────────────────────┘  │  │ │
│  │   │                             │                                       │  │ │
│  │   └─────────────────────────────┼───────────────────────────────────────┘  │ │
│  │                                 │                                          │ │
│  └─────────────────────────────────┼──────────────────────────────────────────┘ │
│                                    │                                            │
│            ┌───────────────────────┼───────────────────────────┐               │
│            │                       │                           │               │
│            ▼                       ▼                           ▼               │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────┐  │
│  │     Jaeger/Tempo    │ │     Prometheus      │ │       Loki              │  │
│  │     (Traces)        │ │     (Metrics)       │ │       (Logs)            │  │
│  │                     │ │                     │ │                         │  │
│  │  • Distributed      │ │  • Time-series DB   │ │  • Log aggregation      │  │
│  │    tracing          │ │  • PromQL queries   │ │  • Full-text search     │  │
│  │  • Span analysis    │ │  • Alerting         │ │  • Correlation          │  │
│  └─────────┬───────────┘ └─────────┬───────────┘ └───────────┬─────────────┘  │
│            │                       │                         │                 │
│            └───────────────────────┴─────────────────────────┘                 │
│                                    │                                            │
│                                    ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                             GRAFANA                                       │  │
│  │                                                                           │  │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │  │
│  │   │ WTB Executions  │  │ Batch Test      │  │ Audit Events            │  │  │
│  │   │ Dashboard       │  │ Performance     │  │ Dashboard               │  │  │
│  │   │                 │  │ Dashboard       │  │                         │  │  │
│  │   │ • Active        │  │ • Variant       │  │ • Event timeline        │  │  │
│  │   │   executions    │  │   comparison    │  │ • Error rate            │  │  │
│  │   │ • Success rate  │  │ • Parallelism   │  │ • Checkpoint frequency  │  │  │
│  │   │ • Node latency  │  │   efficiency    │  │ • Rollback events       │  │  │
│  │   └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │  │
│  │                                                                           │  │
│  │   ┌─────────────────────────────────────────────────────────────────────┐│  │
│  │   │                        ALERTING                                      ││  │
│  │   │  • Execution failure rate > 5%                                      ││  │
│  │   │  • Checkpoint creation latency > 1s                                 ││  │
│  │   │  • Ray worker pool utilization > 80%                                ││  │
│  │   │  • Audit event buffer overflow                                      ││  │
│  │   └─────────────────────────────────────────────────────────────────────┘│  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Metrics Definition

```python
# wtb/infrastructure/observability/metrics.py

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

# Initialize OpenTelemetry meter
meter = metrics.get_meter(__name__)

# ═══════════════════════════════════════════════════════════════
# Execution Metrics
# ═══════════════════════════════════════════════════════════════

executions_total = meter.create_counter(
    name="wtb_executions_total",
    description="Total number of workflow executions",
    unit="1",
)

executions_active = meter.create_up_down_counter(
    name="wtb_executions_active",
    description="Currently active executions",
    unit="1",
)

execution_duration = meter.create_histogram(
    name="wtb_execution_duration_seconds",
    description="Execution duration in seconds",
    unit="s",
)

# ═══════════════════════════════════════════════════════════════
# Node Metrics
# ═══════════════════════════════════════════════════════════════

node_executions_total = meter.create_counter(
    name="wtb_node_executions_total",
    description="Total node executions",
    unit="1",
)

node_duration = meter.create_histogram(
    name="wtb_node_duration_seconds",
    description="Node execution duration",
    unit="s",
)

# ═══════════════════════════════════════════════════════════════
# Checkpoint Metrics
# ═══════════════════════════════════════════════════════════════

checkpoints_total = meter.create_counter(
    name="wtb_checkpoints_total",
    description="Total checkpoints created",
    unit="1",
)

checkpoint_duration = meter.create_histogram(
    name="wtb_checkpoint_duration_seconds",
    description="Time to create checkpoint",
    unit="s",
)

rollbacks_total = meter.create_counter(
    name="wtb_rollbacks_total",
    description="Total rollback operations",
    unit="1",
)

# ═══════════════════════════════════════════════════════════════
# Batch Test Metrics
# ═══════════════════════════════════════════════════════════════

batch_tests_total = meter.create_counter(
    name="wtb_batch_tests_total",
    description="Total batch tests run",
    unit="1",
)

batch_test_variants = meter.create_histogram(
    name="wtb_batch_test_variants",
    description="Number of variants per batch test",
    unit="1",
)

batch_test_duration = meter.create_histogram(
    name="wtb_batch_test_duration_seconds",
    description="Batch test total duration",
    unit="s",
)

ray_workers_active = meter.create_up_down_counter(
    name="wtb_ray_workers_active",
    description="Active Ray workers",
    unit="1",
)

# ═══════════════════════════════════════════════════════════════
# Audit Metrics
# ═══════════════════════════════════════════════════════════════

audit_events_total = meter.create_counter(
    name="wtb_audit_events_total",
    description="Total audit events recorded",
    unit="1",
)

audit_errors_total = meter.create_counter(
    name="wtb_audit_errors_total",
    description="Total audit error events",
    unit="1",
)

audit_buffer_size = meter.create_observable_gauge(
    name="wtb_audit_buffer_size",
    description="Current audit buffer size",
    callbacks=[lambda: get_audit_buffer_size()],
    unit="1",
)

# ═══════════════════════════════════════════════════════════════
# Event Bus Metrics
# ═══════════════════════════════════════════════════════════════

events_published_total = meter.create_counter(
    name="wtb_events_published_total",
    description="Total events published to event bus",
    unit="1",
)

event_handlers_duration = meter.create_histogram(
    name="wtb_event_handler_duration_seconds",
    description="Event handler execution time",
    unit="s",
)
```

### 5.3 Tracing Integration

```python
# wtb/infrastructure/observability/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient, GrpcInstrumentorServer
from functools import wraps
from typing import Callable, Any

tracer = trace.get_tracer(__name__)


def trace_execution(operation: str):
    """
    Decorator to trace execution operations.
    
    Creates spans with execution context for distributed tracing.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            execution_id = kwargs.get("execution_id", "unknown")
            
            with tracer.start_as_current_span(
                name=f"wtb.execution.{operation}",
                attributes={
                    "wtb.execution_id": execution_id,
                    "wtb.operation": operation,
                },
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("wtb.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("wtb.success", False)
                    span.set_attribute("wtb.error", str(e))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_node_execution(node_id: str, node_name: str):
    """Context manager for tracing node execution."""
    return tracer.start_as_current_span(
        name=f"wtb.node.{node_name}",
        attributes={
            "wtb.node_id": node_id,
            "wtb.node_name": node_name,
        },
    )


def trace_batch_test(batch_test_id: str, variant_count: int):
    """Context manager for tracing batch test."""
    return tracer.start_as_current_span(
        name="wtb.batch_test",
        attributes={
            "wtb.batch_test_id": batch_test_id,
            "wtb.variant_count": variant_count,
        },
    )


# Setup function
def setup_tracing(
    service_name: str = "wtb",
    otlp_endpoint: str = "http://localhost:4317",
):
    """Configure OpenTelemetry tracing."""
    provider = TracerProvider()
    
    # Export to OTLP (Jaeger/Tempo compatible)
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    trace.set_tracer_provider(provider)
    
    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument()
    
    # Auto-instrument gRPC
    GrpcInstrumentorClient().instrument()
    GrpcInstrumentorServer().instrument()
```

### 5.4 Grafana Dashboard Templates

```json
{
  "title": "WTB Executions Dashboard",
  "panels": [
    {
      "title": "Active Executions",
      "type": "stat",
      "targets": [
        {
          "expr": "wtb_executions_active",
          "legendFormat": "Active"
        }
      ]
    },
    {
      "title": "Execution Rate (5m)",
      "type": "timeseries",
      "targets": [
        {
          "expr": "rate(wtb_executions_total{status=\"completed\"}[5m])",
          "legendFormat": "Completed"
        },
        {
          "expr": "rate(wtb_executions_total{status=\"failed\"}[5m])",
          "legendFormat": "Failed"
        }
      ]
    },
    {
      "title": "Execution Duration P95",
      "type": "timeseries",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(wtb_execution_duration_seconds_bucket[5m]))",
          "legendFormat": "P95"
        }
      ]
    },
    {
      "title": "Node Latency Heatmap",
      "type": "heatmap",
      "targets": [
        {
          "expr": "sum(rate(wtb_node_duration_seconds_bucket[5m])) by (le, node_id)"
        }
      ]
    },
    {
      "title": "Checkpoint Rate",
      "type": "timeseries",
      "targets": [
        {
          "expr": "rate(wtb_checkpoints_total[5m])",
          "legendFormat": "Checkpoints/s"
        }
      ]
    },
    {
      "title": "Audit Events by Type",
      "type": "piechart",
      "targets": [
        {
          "expr": "sum(wtb_audit_events_total) by (event_type)"
        }
      ]
    },
    {
      "title": "Ray Worker Utilization",
      "type": "gauge",
      "targets": [
        {
          "expr": "wtb_ray_workers_active / wtb_ray_workers_total * 100",
          "legendFormat": "Utilization %"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "rate(wtb_audit_errors_total[5m]) / rate(wtb_audit_events_total[5m]) * 100",
          "legendFormat": "Error %"
        }
      ]
    }
  ]
}
```

---

## 6. Audit Event Exposure

### 6.1 Audit API Design

```python
# wtb/api/rest/routes/audit.py

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import datetime

from wtb.api.rest.dependencies import get_audit_service
from wtb.api.rest.models import (
    AuditEventListResponse,
    AuditSummaryResponse,
    AuditEventType,
)
from wtb.application.services import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    execution_id: Optional[str] = None,
    event_type: Optional[List[AuditEventType]] = Query(None),
    severity: Optional[List[str]] = Query(None),
    node_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Query audit events with filtering.
    
    Supports filtering by:
    - execution_id: Specific execution
    - event_type: EXECUTION_STARTED, NODE_COMPLETED, CHECKPOINT_CREATED, etc.
    - severity: info, success, warning, error, debug
    - node_id: Specific node
    - time range: since/until
    """
    return await audit_service.query_events(
        execution_id=execution_id,
        event_types=event_type,
        severities=severity,
        node_id=node_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    execution_id: Optional[str] = None,
    time_range: str = "1h",  # 1h, 6h, 24h, 7d
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Get audit summary statistics.
    
    Returns:
    - Total events by type
    - Error rate
    - Checkpoint frequency
    - Rollback count
    - Average execution duration
    """
    return await audit_service.get_summary(
        execution_id=execution_id,
        time_range=time_range,
    )


@router.get("/timeline/{execution_id}")
async def get_execution_timeline(
    execution_id: str,
    include_debug: bool = False,
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Get visual timeline data for an execution.
    
    Returns structured data suitable for timeline visualization:
    - Nodes with start/end times
    - Checkpoints
    - Errors
    - State changes
    """
    return await audit_service.get_timeline(
        execution_id=execution_id,
        include_debug=include_debug,
    )
```

### 6.2 Audit Persistence Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUDIT PERSISTENCE STRATEGY                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Event Source                    Storage                     Consumer            │
│  ────────────                    ───────                     ────────            │
│                                                                                  │
│  ┌─────────────────┐            ┌─────────────────────┐    ┌─────────────────┐  │
│  │   WTBEventBus   │            │  In-Memory Buffer   │    │  REST API       │  │
│  │                 │──────────► │  (WTBAuditTrail)    │───►│  /api/v1/audit  │  │
│  │  • publish()    │            │  • Max 1000 events  │    │                 │  │
│  │                 │            │  • Per execution    │    └─────────────────┘  │
│  └─────────────────┘            └─────────┬───────────┘                         │
│         │                                 │                                      │
│         │                                 │ Flush (batch)                        │
│         │                                 ▼                                      │
│         │                       ┌─────────────────────┐    ┌─────────────────┐  │
│         │                       │  PostgreSQL         │    │  Grafana        │  │
│         │                       │  wtb_audit_events   │───►│  Dashboard      │  │
│         │                       │  • BRIN index on    │    │                 │  │
│         │                       │    created_at       │    └─────────────────┘  │
│         │                       │  • Partitioned by   │                         │
│         │                       │    week/month       │                         │
│         │                       └─────────────────────┘                         │
│         │                                                                        │
│         │ Real-time                                                             │
│         ▼                                                                        │
│  ┌─────────────────┐            ┌─────────────────────┐    ┌─────────────────┐  │
│  │ Metrics Listener│            │  Prometheus         │    │  Alertmanager   │  │
│  │                 │──────────► │  • Counters         │───►│  • Error alerts │  │
│  │  • Counter inc  │            │  • Histograms       │    │  • SLA alerts   │  │
│  │  • Histogram    │            │  • Gauges           │    │                 │  │
│  │    observe      │            │                     │    └─────────────────┘  │
│  └─────────────────┘            └─────────────────────┘                         │
│         │                                                                        │
│         │ Stream                                                                 │
│         ▼                                                                        │
│  ┌─────────────────┐            ┌─────────────────────┐    ┌─────────────────┐  │
│  │ WebSocket Mgr   │            │  Connected Clients  │    │  Web UI         │  │
│  │                 │──────────► │  • topic:exec:123   │───►│  Live Timeline  │  │
│  │  • broadcast    │            │  • topic:audit:*    │    │                 │  │
│  │                 │            │                     │    └─────────────────┘  │
│  └─────────────────┘            └─────────────────────┘                         │
│         │                                                                        │
│         │ gRPC Stream                                                           │
│         ▼                                                                        │
│  ┌─────────────────┐            ┌─────────────────────┐    ┌─────────────────┐  │
│  │ gRPC Servicer   │            │  Ray Workers        │    │  External       │  │
│  │                 │──────────► │  (if subscribed)    │    │  Services       │  │
│  │ StreamAudit()   │            │                     │    │  (LangSmith)    │  │
│  └─────────────────┘            └─────────────────────┘    └─────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. SOLID and ACID Compliance

### 7.1 SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **Single Responsibility** | Each service class has one purpose (ExecutionService, AuditService, MetricsService) |
| **Open/Closed** | New protocols via IAPIProtocol interface; new metric types via composition |
| **Liskov Substitution** | REST/gRPC/WebSocket handlers interchangeable via common service interfaces |
| **Interface Segregation** | Separate interfaces: IExecutionControl, IAuditQuery, IMetricsExport |
| **Dependency Inversion** | API layer depends on abstractions (services), not concrete implementations |

### 7.2 ACID Transaction Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TRANSACTION BOUNDARIES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Operation                       Transaction Boundary         Consistency        │
│  ─────────                       ────────────────────         ───────────        │
│                                                                                  │
│  Start Execution                 Single DB Transaction        Strong             │
│  ├─ Create Execution record      │                                               │
│  ├─ Initialize LangGraph thread  │                                               │
│  └─ Publish ExecutionStarted     └─ Outbox pattern: event stored in same txn    │
│                                                                                  │
│  Create Checkpoint               Single DB Transaction        Strong             │
│  ├─ LangGraph checkpoint         │                                               │
│  ├─ Store in Checkpointer        │                                               │
│  ├─ File commit (if enabled)     │ (FileTracker has own txn)                     │
│  └─ Publish CheckpointCreated    └─ Outbox pattern                               │
│                                                                                  │
│  Rollback                        Multi-step with Saga         Eventual           │
│  ├─ Load checkpoint state        │                                               │
│  ├─ Reverse tools (LIFO)         │ Each tool reverse is atomic                   │
│  ├─ Restore files                │ FileTracker restore is atomic                 │
│  └─ Update execution state       └─ Final state update is atomic                 │
│                                                                                  │
│  Batch Test                      Per-variant isolation        Isolated           │
│  ├─ Each variant has own thread  │                                               │
│  ├─ Results collected via Ray    │                                               │
│  └─ Comparison matrix computed   └─ Read-only aggregation                        │
│                                                                                  │
│  Audit Event Recording           Eventually Consistent        Eventual           │
│  ├─ In-memory buffer (immediate) │                                               │
│  ├─ Batch flush to DB            │ Configurable interval (5s default)            │
│  └─ Prometheus export            └─ Real-time (no persistence guarantee)         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Outbox Pattern for Event Delivery

```python
# wtb/infrastructure/outbox/outbox_publisher.py

from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.orm import Session
from datetime import datetime
import json

class OutboxMessage(Base):
    """Outbox table for reliable event publishing."""
    __tablename__ = "wtb_outbox"
    
    id = Column(String(36), primary_key=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")


class OutboxPublisher:
    """
    Outbox pattern publisher for reliable event delivery.
    
    Events are stored in the same transaction as the business operation,
    then a background worker polls and publishes to the event bus.
    
    This ensures events are never lost even if the event bus is down.
    """
    
    def __init__(self, session: Session, event_bus: WTBEventBus):
        self._session = session
        self._event_bus = event_bus
    
    def store_event(self, event: WTBEvent) -> None:
        """Store event in outbox (called within business transaction)."""
        outbox_msg = OutboxMessage(
            id=str(uuid.uuid4()),
            event_type=event.__class__.__name__,
            payload=event.to_dict(),
        )
        self._session.add(outbox_msg)
    
    async def process_pending(self, batch_size: int = 100) -> int:
        """Process pending outbox messages (called by background worker)."""
        pending = self._session.query(OutboxMessage).filter(
            OutboxMessage.status == "pending"
        ).limit(batch_size).all()
        
        processed = 0
        for msg in pending:
            try:
                event = self._deserialize_event(msg.event_type, msg.payload)
                self._event_bus.publish(event)
                msg.status = "processed"
                msg.processed_at = datetime.utcnow()
                processed += 1
            except Exception as e:
                msg.status = "failed"
                # Log error, will retry later
        
        self._session.commit()
        return processed
```

---

## 8. Security Considerations

### 8.1 Authentication & Authorization

```yaml
# API Authentication Strategy
authentication:
  rest:
    method: JWT Bearer Token
    issuer: WTB Auth Service / External IdP (Auth0, Keycloak)
    audiences:
      - wtb-api
    required_claims:
      - sub (user_id)
      - permissions
  
  grpc:
    method: mTLS + JWT metadata
    client_cert_required: true (production)
    jwt_in_metadata: authorization
  
  websocket:
    method: JWT in connection handshake
    token_param: ?token=xxx or Sec-WebSocket-Protocol header

authorization:
  model: RBAC (Role-Based Access Control)
  roles:
    - admin: Full access
    - developer: Execute, view audit, batch test
    - viewer: Read-only access
  
  permissions:
    - execution:create
    - execution:control  # pause, resume, stop
    - execution:rollback
    - audit:read
    - audit:admin  # delete audit records
    - batch_test:run
    - workflow:manage
```

### 8.2 Rate Limiting

```python
# Rate limits per endpoint category
rate_limits:
  rest_api:
    default: 100/minute
    execution_create: 10/minute
    batch_test: 5/minute
    audit_query: 50/minute
  
  grpc:
    streaming: 10 concurrent streams per client
    unary: 200/minute
  
  websocket:
    connections_per_user: 5
    messages_per_second: 10
```

---

## 9. Deployment Configuration

### 9.1 Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| REST API | 8000 | HTTP/HTTPS |
| gRPC | 50051 | HTTP/2 |
| WebSocket | 8000/ws | WS/WSS |
| Prometheus metrics | 8000/metrics | HTTP |
| Health check | 8000/health | HTTP |

### 9.2 Environment Variables

```bash
# API Configuration
WTB_API_HOST=0.0.0.0
WTB_API_PORT=8000
WTB_GRPC_PORT=50051

# Database
WTB_DATABASE_URL=postgresql://user:pass@localhost:5432/wtb
LANGGRAPH_CHECKPOINTER_URL=postgresql://user:pass@localhost:5432/langgraph

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
GRAFANA_URL=http://localhost:3000

# Security
JWT_SECRET_KEY=...
JWT_ALGORITHM=RS256
JWT_ISSUER=https://auth.wtb.example.com

# Ray (for batch testing)
RAY_ADDRESS=ray://localhost:10001
```

---

## 10. Implementation Priority

| Phase | Component | Priority | Effort |
|-------|-----------|----------|--------|
| **Phase 1** | REST API (FastAPI) | P0 | 3 days |
| **Phase 1** | Prometheus metrics endpoint | P0 | 1 day |
| **Phase 1** | WebSocket for UI updates | P0 | 2 days |
| **Phase 2** | gRPC server + proto compilation | P1 | 3 days |
| **Phase 2** | OpenTelemetry tracing | P1 | 2 days |
| **Phase 2** | Grafana dashboard templates | P1 | 1 day |
| **Phase 3** | Audit persistence layer | P1 | 2 days |
| **Phase 3** | Interactive debugging session (gRPC bidirectional) | P2 | 3 days |
| **Phase 3** | Rate limiting + auth | P2 | 2 days |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [WORKFLOW_TEST_BENCH_ARCHITECTURE.md](../Project_Init/WORKFLOW_TEST_BENCH_ARCHITECTURE.md) | Core architecture, domain models |
| [WTB_EVENTBUS_AUDIT_DESIGN.md](../EventBus_and_Audit_Session/WTB_EVENTBUS_AUDIT_DESIGN.md) | Event bus and audit trail design |
| [DATABASE_DESIGN.md](../Project_Init/DATABASE_DESIGN.md) | Database schema, indexing strategy |
| [RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md](../Ray/RAY_IMPLEMENTATION_COMPLETE_2026_01_14.md) | Ray batch test implementation |

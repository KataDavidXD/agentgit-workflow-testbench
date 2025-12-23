# WTB Project Progress Tracker

**Last Updated:** 2024-12-22 19:50 UTC+8

## Project Structure

```
wtb/
├── domain/
│   ├── models/          [DONE] workflow, execution, node_boundary, checkpoint_file, batch_test, evaluation
│   ├── interfaces/      [DONE] repositories, unit_of_work, state_adapter, execution_controller, node_replacer
│   └── events/          [DONE] execution_events, node_events, checkpoint_events
├── application/
│   └── services/        [DONE] execution_controller, node_replacer
├── infrastructure/
│   ├── database/        [DONE] config, setup, models (ORM), repositories, unit_of_work
│   └── adapters/        [PARTIAL] InMemoryStateAdapter done, AgentGitStateAdapter TODO
├── tests/
│   └── test_wtb/        [DONE] domain_models, state_adapter, execution_controller, node_replacer, integration, rollback_with_llm
└── examples/
    └── ml_pipeline_workflow.py  [DONE] 10-step ML pipeline with LangChain LLM + rollback
```

## Completed ✓

| Component | Status | Notes |
|-----------|--------|-------|
| Domain Models | ✓ | Workflow, Execution, NodeBoundary, CheckpointFile, BatchTest, Evaluation |
| Domain Interfaces | ✓ | IRepository, IStateAdapter, IExecutionController, INodeReplacer |
| Domain Events | ✓ | Execution, Node, Checkpoint events |
| SQLAlchemy ORM | ✓ | All 7 WTB tables defined |
| Repositories | ✓ | All repository implementations |
| Unit of Work | ✓ | SQLAlchemyUnitOfWork |
| Database Config | ✓ | Local data/ folder, redirect AgentGit |
| InMemoryStateAdapter | ✓ | For testing/development |
| ExecutionController | ✓ | run, pause, resume, stop, rollback |
| NodeReplacer | ✓ | variant registry, hot-swap |
| Unit Tests | ✓ | All passing (5/5 with real LLM) |
| ML Pipeline Example | ✓ | LangChain + real rollback demo |

## TODO

| Component | Priority | Description |
|-----------|----------|-------------|
| AgentGitStateAdapter | HIGH | Integrate with real AgentGit checkpoints |
| Persist to WTB DB | HIGH | Save workflow/execution to wtb.db |
| BatchTestRunner | MEDIUM | Parallel A/B testing |
| EvaluationEngine | MEDIUM | Metrics collection & scoring |
| FileTracker Integration | LOW | Link checkpoints to file commits |
| IDE Sync | LOW | WebSocket events to audit UI |

## Database Status

| Database | Location | Rows |
|----------|----------|------|
| AgentGit | `data/agentgit.db` | 31 checkpoints, 22 sessions |
| WTB | `data/wtb.db` | Schema only (0 rows) - needs persistence layer |

## Next Steps

1. Create `AgentGitStateAdapter` to replace `InMemoryStateAdapter`
2. Add persistence to `ExecutionController` to save to `wtb_executions`
3. Implement `BatchTestRunner` for parallel variant testing


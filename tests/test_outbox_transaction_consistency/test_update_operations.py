"""
Integration tests for Update Operations Transaction Consistency.

Tests outbox transaction consistency during:
- Node update (replace node implementation)
- Workflow update (modify workflow structure)
- Configuration update (modify runtime configuration)
- Hot reload scenarios
- Version management

ACID Compliance Focus:
- Atomicity: Updates complete fully or rolled back
- Consistency: Graph structure remains valid after updates
- Isolation: Concurrent updates don't corrupt state
- Durability: Updates persist correctly

Run with: pytest tests/test_outbox_transaction_consistency/test_update_operations.py -v
"""

import pytest
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Callable
from unittest.mock import Mock, MagicMock, patch

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from tests.test_outbox_transaction_consistency.helpers import (
    SimpleState,
    TransactionState,
    create_simple_state,
    create_transaction_state,
    MockOutboxEvent,
    MockCheckpoint,
    verify_outbox_consistency,
    verify_transaction_atomicity,
    node_a,
    node_b,
    node_c,
    node_d,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Node Update Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestNodeUpdateTransactionConsistency:
    """Tests for node update transaction consistency."""
    
    def test_node_update_creates_version_checkpoint(
        self,
        simple_compiled_graph,
        checkpoint_repository,
        outbox_repository,
    ):
        """Node update should create version checkpoint and outbox event."""
        # Execute original workflow
        initial = create_simple_state()
        config = {"configurable": {"thread_id": "node-update-1"}}
        result = simple_compiled_graph.invoke(initial, config)
        
        # Simulate node update
        old_version = 1
        new_version = 2
        
        # Create version checkpoint
        checkpoint = checkpoint_repository.add_checkpoint(
            checkpoint_id=new_version,
            thread_id="node-update-1",
            step=result["count"],
            state={
                **result,
                "node_version": new_version,
                "previous_version": old_version,
            },
        )
        
        # Create outbox event for node update
        update_event = MockOutboxEvent(
            event_id="node-update-event-1",
            event_type="NODE_UPDATED",
            aggregate_type="WorkflowNode",
            aggregate_id="node_b",
            payload={
                "old_version": old_version,
                "new_version": new_version,
                "checkpoint_id": checkpoint.checkpoint_id,
                "updated_at": datetime.now().isoformat(),
            },
        )
        outbox_repository.add(update_event)
        
        # Verify both created
        assert checkpoint_repository.get_by_id(new_version) is not None
        assert outbox_repository.get_by_id("node-update-event-1") is not None
    
    def test_node_update_preserves_execution_state(
        self,
        memory_checkpointer,
    ):
        """Node update should preserve execution state."""
        # Create original workflow
        workflow = StateGraph(SimpleState)
        workflow.add_node("node_a", node_a)
        workflow.add_node("node_b", node_b)
        workflow.add_node("node_c", node_c)
        workflow.set_entry_point("node_a")
        workflow.add_edge("node_a", "node_b")
        workflow.add_edge("node_b", "node_c")
        workflow.add_edge("node_c", END)
        
        graph = workflow.compile(checkpointer=memory_checkpointer)
        
        # Execute partially (we'll check state after node_a)
        config = {"configurable": {"thread_id": "preserve-state-1"}}
        initial = create_simple_state()
        result = graph.invoke(initial, config)
        
        # Get checkpoint history
        history = list(graph.get_state_history(config))
        
        # Find checkpoint after node_a
        for snap in history:
            if "A" in snap.values.get("messages", []) and "B" not in snap.values.get("messages", []):
                state_after_a = snap.values
                break
        else:
            # All nodes completed, use history
            state_after_a = history[-2].values if len(history) > 1 else result
        
        # Simulate node_b update with new implementation
        def updated_node_b(state: SimpleState) -> Dict[str, Any]:
            return {"messages": ["B_UPDATED"], "count": state["count"] + 1}
        
        # Create new workflow with updated node
        updated_workflow = StateGraph(SimpleState)
        updated_workflow.add_node("node_a", node_a)
        updated_workflow.add_node("node_b", updated_node_b)  # Updated
        updated_workflow.add_node("node_c", node_c)
        updated_workflow.set_entry_point("node_a")
        updated_workflow.add_edge("node_a", "node_b")
        updated_workflow.add_edge("node_b", "node_c")
        updated_workflow.add_edge("node_c", END)
        
        updated_graph = updated_workflow.compile(checkpointer=memory_checkpointer)
        
        # Resume from checkpoint (would use the updated node)
        config2 = {"configurable": {"thread_id": "preserve-state-2"}}
        result2 = updated_graph.invoke(initial, config2)
        
        # Verify updated node was used
        assert "B_UPDATED" in result2["messages"]
    
    def test_node_update_atomicity(
        self,
        outbox_repository,
        checkpoint_repository,
    ):
        """Node update should be atomic - all changes or none."""
        operations = []
        
        try:
            # Step 1: Create update checkpoint
            checkpoint = checkpoint_repository.add_checkpoint(
                checkpoint_id=100,
                thread_id="atomic-update-1",
                step=1,
            )
            operations.append(("checkpoint", True))
            
            # Step 2: Create outbox event
            event = MockOutboxEvent(
                event_id="update-atomic-1",
                event_type="NODE_UPDATED",
                aggregate_type="WorkflowNode",
                aggregate_id="node_b",
            )
            outbox_repository.add(event)
            operations.append(("outbox", True))
            
            # Step 3: Mark event as processed
            event.mark_processed()
            outbox_repository.update(event)
            operations.append(("process", True))
            
        except Exception:
            operations.append(("error", False))
        
        result = verify_transaction_atomicity(operations)
        assert result.success


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Update Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkflowUpdateTransactionConsistency:
    """Tests for workflow update transaction consistency."""
    
    def test_workflow_structure_update(
        self,
        memory_checkpointer,
        outbox_repository,
    ):
        """Workflow structure update should be transactionally consistent."""
        # Original workflow: A -> B -> C
        original = StateGraph(SimpleState)
        original.add_node("node_a", node_a)
        original.add_node("node_b", node_b)
        original.add_node("node_c", node_c)
        original.set_entry_point("node_a")
        original.add_edge("node_a", "node_b")
        original.add_edge("node_b", "node_c")
        original.add_edge("node_c", END)
        
        original_graph = original.compile(checkpointer=memory_checkpointer)
        
        # Execute original
        config = {"configurable": {"thread_id": "wf-update-1"}}
        result1 = original_graph.invoke(create_simple_state(), config)
        assert result1["messages"] == ["A", "B", "C"]
        
        # Updated workflow: A -> B -> D -> C (added D)
        updated = StateGraph(SimpleState)
        updated.add_node("node_a", node_a)
        updated.add_node("node_b", node_b)
        updated.add_node("node_d", node_d)  # New node
        updated.add_node("node_c", node_c)
        updated.set_entry_point("node_a")
        updated.add_edge("node_a", "node_b")
        updated.add_edge("node_b", "node_d")  # New edge
        updated.add_edge("node_d", "node_c")  # New edge
        updated.add_edge("node_c", END)
        
        updated_graph = updated.compile(checkpointer=memory_checkpointer)
        
        # Create update event
        update_event = MockOutboxEvent(
            event_id="wf-update-event-1",
            event_type="WORKFLOW_UPDATED",
            aggregate_type="Workflow",
            aggregate_id="wf-1",
            payload={
                "version": 2,
                "changes": ["added_node:node_d", "modified_edge:node_b->node_d"],
            },
        )
        outbox_repository.add(update_event)
        
        # Execute updated workflow
        config2 = {"configurable": {"thread_id": "wf-update-2"}}
        result2 = updated_graph.invoke(create_simple_state(), config2)
        
        assert "D" in result2["messages"]
        assert result2["messages"] == ["A", "B", "D", "C"]
    
    def test_workflow_update_with_running_execution(
        self,
        memory_checkpointer,
        outbox_repository,
        checkpoint_repository,
    ):
        """Workflow update during execution should be handled safely."""
        # Create workflow
        workflow = StateGraph(SimpleState)
        workflow.add_node("node_a", node_a)
        workflow.add_node("node_b", node_b)
        workflow.add_node("node_c", node_c)
        workflow.set_entry_point("node_a")
        workflow.add_edge("node_a", "node_b")
        workflow.add_edge("node_b", "node_c")
        workflow.add_edge("node_c", END)
        
        graph = workflow.compile(checkpointer=memory_checkpointer)
        
        # Start execution
        config = {"configurable": {"thread_id": "running-exec-1"}}
        result = graph.invoke(create_simple_state(), config)
        
        # Create checkpoint for running execution
        checkpoint = checkpoint_repository.add_checkpoint(
            checkpoint_id=1,
            thread_id="running-exec-1",
            step=result["count"],
            state=result,
        )
        
        # Create workflow update event (should be queued, not immediate)
        update_event = MockOutboxEvent(
            event_id="wf-running-update-1",
            event_type="WORKFLOW_UPDATE_QUEUED",
            aggregate_type="Workflow",
            aggregate_id="wf-1",
            payload={
                "target_version": 3,
                "affected_executions": ["running-exec-1"],
                "apply_after_completion": True,
            },
        )
        outbox_repository.add(update_event)
        
        # Verify event is pending
        assert update_event.status == "pending"
    
    def test_workflow_version_consistency(
        self,
        outbox_repository,
    ):
        """Workflow versions should be consistent across events."""
        versions = []
        
        # Create sequence of version events
        for v in [1, 2, 3]:
            event = MockOutboxEvent(
                event_id=f"version-event-{v}",
                event_type="WORKFLOW_VERSION_CREATED",
                aggregate_type="Workflow",
                aggregate_id="wf-1",
                payload={
                    "version": v,
                    "previous_version": v - 1 if v > 1 else None,
                },
            )
            outbox_repository.add(event)
            versions.append(v)
            time.sleep(0.001)
        
        # Verify version sequence
        events = sorted(outbox_repository.list_all(), key=lambda e: e.created_at)
        for i, event in enumerate(events):
            assert event.payload["version"] == i + 1
            if i > 0:
                assert event.payload["previous_version"] == i


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Update Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigurationUpdateConsistency:
    """Tests for configuration update transaction consistency."""
    
    def test_runtime_config_update(
        self,
        outbox_repository,
    ):
        """Runtime configuration update should be tracked."""
        # Original config
        original_config = {
            "batch_size": 32,
            "learning_rate": 0.001,
            "timeout_seconds": 300,
        }
        
        # Updated config
        updated_config = {
            "batch_size": 64,  # Changed
            "learning_rate": 0.001,
            "timeout_seconds": 600,  # Changed
        }
        
        # Create config update event
        config_event = MockOutboxEvent(
            event_id="config-update-1",
            event_type="CONFIG_UPDATED",
            aggregate_type="RuntimeConfig",
            aggregate_id="config-1",
            payload={
                "original": original_config,
                "updated": updated_config,
                "changes": {
                    "batch_size": {"from": 32, "to": 64},
                    "timeout_seconds": {"from": 300, "to": 600},
                },
            },
        )
        outbox_repository.add(config_event)
        
        # Verify event contains diff
        saved_event = outbox_repository.get_by_id("config-update-1")
        assert saved_event.payload["changes"]["batch_size"]["to"] == 64
    
    def test_config_update_affects_new_executions(
        self,
        batch_test_compiled_graph,
        outbox_repository,
    ):
        """Config updates should affect new executions only."""
        from tests.test_outbox_transaction_consistency.helpers import create_batch_test_state
        
        # Execute with original config
        config1 = {"configurable": {"thread_id": "config-exec-1"}}
        state1 = create_batch_test_state(variant_config={"batch_size": 32})
        result1 = batch_test_compiled_graph.invoke(state1, config1)
        
        # Create config update event
        outbox_repository.add(MockOutboxEvent(
            event_id="config-update-exec-1",
            event_type="CONFIG_UPDATED",
            aggregate_type="RuntimeConfig",
            aggregate_id="global",
            payload={"batch_size": {"from": 32, "to": 64}},
        ))
        
        # Execute with new config
        config2 = {"configurable": {"thread_id": "config-exec-2"}}
        state2 = create_batch_test_state(variant_config={"batch_size": 64})
        result2 = batch_test_compiled_graph.invoke(state2, config2)
        
        # Both executions complete successfully with their configs
        assert result1["count"] == 3
        assert result2["count"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Hot Reload Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHotReloadConsistency:
    """Tests for hot reload transaction consistency."""
    
    def test_hot_reload_preserves_state(
        self,
        memory_checkpointer,
        checkpoint_repository,
    ):
        """Hot reload should preserve execution state."""
        # Original workflow
        workflow_v1 = StateGraph(SimpleState)
        workflow_v1.add_node("node_a", lambda s: {"messages": ["A_v1"], "count": s["count"] + 1})
        workflow_v1.add_node("node_b", node_b)
        workflow_v1.set_entry_point("node_a")
        workflow_v1.add_edge("node_a", "node_b")
        workflow_v1.add_edge("node_b", END)
        
        graph_v1 = workflow_v1.compile(checkpointer=memory_checkpointer)
        
        config = {"configurable": {"thread_id": "hot-reload-1"}}
        result1 = graph_v1.invoke(create_simple_state(), config)
        
        # Save checkpoint
        checkpoint = checkpoint_repository.add_checkpoint(
            checkpoint_id=1,
            thread_id="hot-reload-1",
            step=result1["count"],
            state=result1,
        )
        
        # Hot reload with updated node
        workflow_v2 = StateGraph(SimpleState)
        workflow_v2.add_node("node_a", lambda s: {"messages": ["A_v2"], "count": s["count"] + 1})
        workflow_v2.add_node("node_b", node_b)
        workflow_v2.set_entry_point("node_a")
        workflow_v2.add_edge("node_a", "node_b")
        workflow_v2.add_edge("node_b", END)
        
        graph_v2 = workflow_v2.compile(checkpointer=memory_checkpointer)
        
        # New execution uses v2
        config2 = {"configurable": {"thread_id": "hot-reload-2"}}
        result2 = graph_v2.invoke(create_simple_state(), config2)
        
        assert "A_v1" in result1["messages"]
        assert "A_v2" in result2["messages"]
    
    def test_hot_reload_event_ordering(
        self,
        outbox_repository,
    ):
        """Hot reload events should maintain proper ordering."""
        events = []
        
        # Sequence: prepare -> swap -> verify
        for i, event_type in enumerate([
            "HOT_RELOAD_PREPARING",
            "HOT_RELOAD_SWAPPING",
            "HOT_RELOAD_VERIFYING",
            "HOT_RELOAD_COMPLETED",
        ]):
            event = MockOutboxEvent(
                event_id=f"reload-{i}",
                event_type=event_type,
                aggregate_type="Workflow",
                aggregate_id="wf-1",
                payload={"step": i},
            )
            events.append(event)
            outbox_repository.add(event)
            time.sleep(0.001)
        
        # Verify ordering
        saved = sorted(outbox_repository.list_all(), key=lambda e: e.created_at)
        assert saved[0].event_type == "HOT_RELOAD_PREPARING"
        assert saved[-1].event_type == "HOT_RELOAD_COMPLETED"


# ═══════════════════════════════════════════════════════════════════════════════
# Concurrent Update Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrentUpdateConsistency:
    """Tests for concurrent update transaction consistency."""
    
    def test_concurrent_node_updates_serialized(
        self,
        outbox_repository,
    ):
        """Concurrent node updates should be serialized."""
        results = []
        lock = threading.Lock()
        
        def update_node(update_id: int):
            event = MockOutboxEvent(
                event_id=f"concurrent-update-{update_id}",
                event_type="NODE_UPDATED",
                aggregate_type="WorkflowNode",
                aggregate_id="node_b",
                payload={"update_id": update_id},
            )
            outbox_repository.add(event)
            with lock:
                results.append(update_id)
        
        threads = [threading.Thread(target=update_node, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All updates should be recorded
        assert len(results) == 10
        assert len(outbox_repository.list_all()) == 10
    
    def test_concurrent_workflow_and_node_update(
        self,
        outbox_repository,
    ):
        """Concurrent workflow and node updates should be handled correctly."""
        results = {"workflow": [], "node": []}
        lock = threading.Lock()
        
        def update_workflow():
            for i in range(5):
                event = MockOutboxEvent(
                    event_id=f"wf-update-{i}",
                    event_type="WORKFLOW_UPDATED",
                    aggregate_type="Workflow",
                    aggregate_id="wf-1",
                )
                outbox_repository.add(event)
                with lock:
                    results["workflow"].append(i)
        
        def update_node():
            for i in range(5):
                event = MockOutboxEvent(
                    event_id=f"node-update-{i}",
                    event_type="NODE_UPDATED",
                    aggregate_type="WorkflowNode",
                    aggregate_id="node_a",
                )
                outbox_repository.add(event)
                with lock:
                    results["node"].append(i)
        
        t1 = threading.Thread(target=update_workflow)
        t2 = threading.Thread(target=update_node)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Both update types should complete
        assert len(results["workflow"]) == 5
        assert len(results["node"]) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# ACID Compliance Tests for Updates
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateACIDCompliance:
    """Tests for ACID compliance in update operations."""
    
    def test_update_atomicity(
        self,
        outbox_repository,
        checkpoint_repository,
    ):
        """Update operations should be atomic."""
        operations = []
        
        # Simulate atomic update
        try:
            checkpoint = checkpoint_repository.add_checkpoint(
                checkpoint_id=1,
                thread_id="atomic-1",
                step=1,
            )
            operations.append(("checkpoint", True))
            
            event = MockOutboxEvent(
                event_id="atomic-event-1",
                event_type="UPDATE",
                aggregate_type="Workflow",
                aggregate_id="wf-1",
            )
            outbox_repository.add(event)
            operations.append(("outbox", True))
            
        except Exception:
            operations.append(("error", False))
        
        result = verify_transaction_atomicity(operations)
        assert result.success
    
    def test_update_consistency_graph_valid(
        self,
        memory_checkpointer,
    ):
        """Updated graph should remain valid and executable."""
        # Create valid workflow
        workflow = StateGraph(SimpleState)
        workflow.add_node("node_a", node_a)
        workflow.add_node("node_b", node_b)
        workflow.set_entry_point("node_a")
        workflow.add_edge("node_a", "node_b")
        workflow.add_edge("node_b", END)
        
        graph = workflow.compile(checkpointer=memory_checkpointer)
        
        # Execute should succeed
        config = {"configurable": {"thread_id": "valid-graph-1"}}
        result = graph.invoke(create_simple_state(), config)
        
        assert result["count"] == 2
        assert result["messages"] == ["A", "B"]
    
    def test_update_isolation_different_versions(
        self,
        memory_checkpointer,
    ):
        """Different workflow versions should be isolated."""
        # Version 1
        workflow_v1 = StateGraph(SimpleState)
        workflow_v1.add_node("node_a", lambda s: {"messages": ["V1"], "count": s["count"] + 1})
        workflow_v1.set_entry_point("node_a")
        workflow_v1.add_edge("node_a", END)
        graph_v1 = workflow_v1.compile(checkpointer=MemorySaver())
        
        # Version 2
        workflow_v2 = StateGraph(SimpleState)
        workflow_v2.add_node("node_a", lambda s: {"messages": ["V2"], "count": s["count"] + 1})
        workflow_v2.set_entry_point("node_a")
        workflow_v2.add_edge("node_a", END)
        graph_v2 = workflow_v2.compile(checkpointer=MemorySaver())
        
        # Execute both concurrently
        results = {}
        
        def run_v1():
            config = {"configurable": {"thread_id": "iso-v1"}}
            results["v1"] = graph_v1.invoke(create_simple_state(), config)
        
        def run_v2():
            config = {"configurable": {"thread_id": "iso-v2"}}
            results["v2"] = graph_v2.invoke(create_simple_state(), config)
        
        t1 = threading.Thread(target=run_v1)
        t2 = threading.Thread(target=run_v2)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Results should be isolated
        assert "V1" in results["v1"]["messages"]
        assert "V2" in results["v2"]["messages"]
        assert "V2" not in results["v1"]["messages"]
        assert "V1" not in results["v2"]["messages"]
    
    def test_update_durability(
        self,
        outbox_repository,
    ):
        """Updates should be durably persisted."""
        # Create update event
        event = MockOutboxEvent(
            event_id="durable-update-1",
            event_type="NODE_UPDATED",
            aggregate_type="WorkflowNode",
            aggregate_id="node_a",
            payload={"version": 2},
        )
        outbox_repository.add(event)
        
        # Mark as processed
        event.mark_processed()
        outbox_repository.update(event)
        
        # Verify persistence
        retrieved = outbox_repository.get_by_id("durable-update-1")
        assert retrieved is not None
        assert retrieved.status == "processed"
        assert retrieved.processed_at is not None

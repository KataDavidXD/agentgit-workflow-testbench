"""
================================================================================
Infrastructure Tests for AgentGit v2
================================================================================

SUMMARY OF VERIFIED CAPABILITIES (76 tests passed)
---------------------------------------------------

1. CHECKPOINT SYSTEM
   ✓ Checkpoint creation with session_state, metadata, tool_track_position
   ✓ Serialization to/from dict (persistence ready)
   ✓ Repository CRUD: create, get_by_id, get_by_internal_session, update_metadata, delete
   
2. DUAL GRANULARITY CHECKPOINTS (MDP Extension)
   ✓ Node-level checkpoints: Created at workflow node boundaries
     - metadata.checkpoint_type = "node"
     - Contains: current_node_id, workflow_variables, execution_path
   ✓ Tool/Message-level checkpoints: Fine-grained within nodes
     - metadata.checkpoint_type = "tool_message"  
     - metadata.parent_checkpoint_id links to parent node checkpoint
   ✓ Filtering: get_node_checkpoints() returns only node-level
   ✓ Mixed retrieval: Both granularities coexist in same session

3. SESSION MANAGEMENT
   ✓ InternalSession: state, conversation_history, is_current tracking
   ✓ InternalSession_mdp: MDP extensions (current_node_id, workflow_variables, execution_path)
   ✓ Session hierarchy: parent_session_id for branching
   ✓ Session lineage: get_session_lineage() returns root→current path
   ✓ Current session switching within external session
   ✓ Isolation across external sessions verified

4. BRANCHING & ROLLBACK
   ✓ InternalSession_mdp.create_branch_from_checkpoint(): Creates new session from checkpoint
   ✓ Branch preserves: checkpoint state, parent_session_id, branch_point_checkpoint_id
   ✓ Rollback to node checkpoint: Restores workflow_variables, execution_path
   ✓ Rollback to tool/message checkpoint: Fine-grained state restoration
   ✓ Lineage tracking maintained after branching

5. TOOL MANAGER
   ✓ Tool invocation recording: tool_name, args, result, success/error
   ✓ Tool track position: Monotonically increasing counter
   ✓ Reversible tool registration: register_reversible_tool(name, forward_fn, reverse_fn)
   ✓ Tool statistics: total, successful, failed, per-tool counts
   ✓ Note: Tools execute via spec.forward(), not tool_manager.execute_tool()

6. EVENT BUS
   ✓ Publish/Subscribe pattern for domain events
   ✓ Multiple subscribers per event type
   ✓ Event history tracking
   ✓ Unsubscribe functionality

7. WORKFLOW GRAPH
   ✓ Node/Edge structure with entry_point
   ✓ get_outgoing_edges() for traversal
   ✓ Ready for ExecutionController integration

8. AUDIT TRAIL SYSTEM
   ✓ AuditEvent: timestamp, event_type, severity, message, details, error, duration_ms
   ✓ EventType: TOOL_START, TOOL_SUCCESS, TOOL_ERROR, AGENT_DECISION, LLM_CALL, CHECKPOINT_CREATED, ROLLBACK
   ✓ EventSeverity: INFO, WARNING, ERROR, SUCCESS
   ✓ AuditTrail: add_event, get_errors, get_tool_events, get_summary
   ✓ User-friendly formatting with icons (✅/❌/⚠️/ℹ️)
   ✓ Serialization/deserialization for checkpoint storage
   ✓ Integration: Store audit trail in checkpoint metadata for rollback recovery

9. EXTERNAL SESSION
   ✓ User-facing session container with multiple internal sessions
   ✓ add_internal_session() with branch tracking
   ✓ set_current_internal_session() for switching
   ✓ Branch info: branch_count, total_sessions, is_branched
   ✓ Metadata management and checkpoint counting
   ✓ ExternalSessionRepository: CRUD, get_by_user, deactivate

10. TOOL ROLLBACK REGISTRY
    ✓ ToolSpec: forward function + optional reverse function
    ✓ record_invocation(): Track tool executions
    ✓ rollback(): Execute reverse functions in reverse order
    ✓ Checkpoint tools (create_checkpoint, etc.) skipped during rollback
    ✓ redo(): Re-execute forward functions
    ✓ truncate_track(): Trim history to position

11. NODE MANAGER
    ✓ get_mdp_state(): Extract MDP state from session
    ✓ update_mdp_state(): Sync session with workflow state
    ✓ Orchestrates WorkflowGraph + ToolManager + Session

CRITICAL FINDINGS FOR WTB INTEGRATION
--------------------------------------

1. DATABASE INITIALIZATION ORDER (FK Constraints):
   Tables must be created in order: users → external_sessions → internal_sessions → checkpoints
   Test data required: user(id=1), external_session(id=1, id=2)
   
2. TOOL EXECUTION PATTERN:
   ToolManager.register_reversible_tool() registers ToolSpec in tool_rollback_registry
   Execute via: spec = tool_manager.tool_rollback_registry.get_tool(name); spec.forward(args)
   
3. MDP STATE STORAGE:
   Checkpoint.metadata["mdp_state"] contains: current_node_id, workflow_variables, execution_path
   Checkpoint.metadata["checkpoint_type"] distinguishes "node" vs "tool_message"

4. RECOMMENDED WTB ADAPTER PATTERN:
   - Use node-level checkpoints by default (matches workflow semantics)
   - Enable tool/message granularity only for debugging mode
   - AgentGitStateAdapter should call CheckpointManager_mdp.create_node_checkpoint()

Run with: pytest tests/test_agentgit_v2.py -v
================================================================================
"""

import pytest
import tempfile
import os
from datetime import datetime
from typing import Dict, Any

# AgentGit imports
from agentgit.checkpoints.checkpoint import Checkpoint
from agentgit.sessions.internal_session import InternalSession
from agentgit.sessions.internal_session_mdp import InternalSession_mdp
from agentgit.database.repositories.checkpoint_repository import CheckpointRepository
from agentgit.database.repositories.internal_session_repository import InternalSessionRepository
from agentgit.managers.checkpoint_manager import CheckpointManager
from agentgit.managers.checkpoint_manager_mdp import CheckpointManager_mdp
from agentgit.managers.tool_manager import ToolManager
from agentgit.managers.node_manager import NodeManager
from agentgit.core.workflow import WorkflowGraph, WorkflowNode, WorkflowEdge
from agentgit.core.rollback_protocol import ToolSpec, ToolInvocationRecord, ToolRollbackRegistry, ReverseInvocationResult
from agentgit.events.event_bus import EventBus, DomainEvent
from agentgit.events.agent_events import CheckpointCreatedEvent, SessionCreatedEvent
from agentgit.audit.audit_trail import AuditTrail, AuditEvent, EventType, EventSeverity
from agentgit.sessions.external_session import ExternalSession
from agentgit.database.repositories.external_session_repository import ExternalSessionRepository


# ============== Database Initialization Helper ==============

def init_agentgit_schema(db_path: str):
    """Initialize all AgentGit tables in the correct order to satisfy FK constraints.
    
    Creates tables in order: users → external_sessions → internal_sessions → checkpoints
    with FK constraints disabled during creation, then enables them.
    Also creates test data (user and external_session) for FK satisfaction.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Temporarily disable foreign key checks for schema creation
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # 1. Create users table first (no dependencies)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT,
                last_login TEXT,
                data TEXT,
                api_key TEXT,
                session_limit INTEGER DEFAULT 5
            )
        """)
        
        # 2. Create external_sessions table (depends on users)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                is_active INTEGER DEFAULT 1,
                data TEXT,
                metadata TEXT,
                branch_count INTEGER DEFAULT 0,
                total_checkpoints INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 3. Create internal_sessions table (depends on external_sessions, checkpoints)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS internal_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_session_id INTEGER NOT NULL,
                langgraph_session_id TEXT UNIQUE NOT NULL,
                state_data TEXT,
                conversation_history TEXT,
                created_at TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                checkpoint_count INTEGER DEFAULT 0,
                parent_session_id INTEGER,
                branch_point_checkpoint_id INTEGER,
                tool_invocation_count INTEGER DEFAULT 0,
                metadata TEXT,
                FOREIGN KEY (external_session_id) REFERENCES external_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_session_id) REFERENCES internal_sessions(id) ON DELETE SET NULL,
                FOREIGN KEY (branch_point_checkpoint_id) REFERENCES checkpoints(id) ON DELETE SET NULL
            )
        """)
        
        # 4. Create checkpoints table (depends on internal_sessions, users)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                internal_session_id INTEGER NOT NULL,
                checkpoint_name TEXT,
                checkpoint_data TEXT NOT NULL,
                is_auto INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                user_id INTEGER,
                FOREIGN KEY (internal_session_id) REFERENCES internal_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_external_sessions_user ON external_sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_internal_sessions_external ON internal_sessions(external_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_internal_sessions_langgraph ON internal_sessions(langgraph_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_internal_sessions_parent ON internal_sessions(parent_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(internal_session_id)")
        
        # Insert test data for FK constraints
        # Create a test user (id=1)
        cursor.execute("""
            INSERT INTO users (id, username, password_hash, is_admin, created_at)
            VALUES (1, 'test_user', 'test_hash', 0, datetime('now'))
        """)
        
        # Create test external sessions (id=1 and id=2 for isolation tests)
        cursor.execute("""
            INSERT INTO external_sessions (id, user_id, session_name, created_at, data)
            VALUES (1, 1, 'Test Session 1', datetime('now'), '{}')
        """)
        cursor.execute("""
            INSERT INTO external_sessions (id, user_id, session_name, created_at, data)
            VALUES (2, 1, 'Test Session 2', datetime('now'), '{}')
        """)
        
        conn.commit()
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    finally:
        conn.close()


# ============== Fixtures ==============

@pytest.fixture
def temp_db():
    """Create a temporary database file with initialized schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Initialize all required tables
    init_agentgit_schema(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def checkpoint_repo(temp_db):
    """Create a CheckpointRepository with temp database."""
    return CheckpointRepository(temp_db)


@pytest.fixture
def session_repo(temp_db):
    """Create an InternalSessionRepository with temp database."""
    return InternalSessionRepository(temp_db)


@pytest.fixture
def checkpoint_manager(checkpoint_repo):
    """Create a CheckpointManager."""
    return CheckpointManager(checkpoint_repo)


@pytest.fixture
def checkpoint_manager_mdp(checkpoint_repo):
    """Create a CheckpointManager_mdp for MDP workflows."""
    return CheckpointManager_mdp(checkpoint_repo)


@pytest.fixture
def tool_manager():
    """Create a ToolManager with test tools."""
    return ToolManager(tools=[])


@pytest.fixture
def sample_workflow():
    """Create a sample workflow graph for testing."""
    graph = WorkflowGraph(id="test_workflow", version="1.0.0")
    
    # Add nodes
    start_node = WorkflowNode(id="start", name="Start", tool_name="start_tool")
    process_node = WorkflowNode(id="process", name="Process", tool_name="process_tool")
    end_node = WorkflowNode(id="end", name="End", tool_name="end_tool")
    
    graph.add_node(start_node)
    graph.add_node(process_node)
    graph.add_node(end_node)
    
    # Add edges
    graph.add_edge(WorkflowEdge(source_id="start", target_id="process"))
    graph.add_edge(WorkflowEdge(source_id="process", target_id="end"))
    
    graph.entry_point = "start"
    
    return graph


# ============== Checkpoint Tests ==============

class TestCheckpoint:
    """Tests for Checkpoint model."""
    
    def test_checkpoint_creation(self):
        """Test creating a checkpoint with basic attributes."""
        cp = Checkpoint(
            internal_session_id=1,
            checkpoint_name="Test Checkpoint",
            session_state={"counter": 5},
            is_auto=False
        )
        
        assert cp.internal_session_id == 1
        assert cp.checkpoint_name == "Test Checkpoint"
        assert cp.session_state == {"counter": 5}
        assert cp.is_auto is False
    
    def test_checkpoint_to_dict(self):
        """Test checkpoint serialization to dictionary."""
        cp = Checkpoint(
            internal_session_id=1,
            checkpoint_name="Serialize Test",
            session_state={"key": "value"},
            metadata={"extra": "data"},
            created_at=datetime.now()
        )
        
        data = cp.to_dict()
        
        assert "internal_session_id" in data
        assert "checkpoint_name" in data
        assert "session_state" in data
        assert "metadata" in data
        assert data["session_state"] == {"key": "value"}
    
    def test_checkpoint_from_dict(self):
        """Test checkpoint deserialization from dictionary."""
        data = {
            "internal_session_id": 1,
            "checkpoint_name": "From Dict",
            "session_state": {"restored": True},
            "conversation_history": [{"role": "user", "content": "test"}],
            "is_auto": True,
            "metadata": {"type": "test"}
        }
        
        cp = Checkpoint.from_dict(data)
        
        assert cp.internal_session_id == 1
        assert cp.checkpoint_name == "From Dict"
        assert cp.session_state["restored"] is True
        assert cp.is_auto is True
    
    def test_checkpoint_tool_track_position(self):
        """Test getting tool track position from metadata."""
        cp = Checkpoint(
            internal_session_id=1,
            metadata={"tool_track_position": 5}
        )
        
        assert cp.get_tool_track_position() == 5
    
    def test_checkpoint_tool_track_position_default(self):
        """Test default tool track position when not set."""
        cp = Checkpoint(internal_session_id=1)
        
        assert cp.get_tool_track_position() == 0


# ============== Checkpoint Repository Tests ==============

class TestCheckpointRepository:
    """Tests for CheckpointRepository CRUD operations."""
    
    def test_create_checkpoint(self, checkpoint_repo, session_repo):
        """Test creating and retrieving a checkpoint."""
        # First create a session (required for FK)
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="test_session_1",
            session_state={}
        )
        session = session_repo.create(session)
        
        # Create checkpoint
        cp = Checkpoint(
            internal_session_id=session.id,
            checkpoint_name="Test Create",
            session_state={"step": 1},
            is_auto=True
        )
        
        created = checkpoint_repo.create(cp)
        
        assert created.id is not None
        assert created.checkpoint_name == "Test Create"
    
    def test_get_checkpoint_by_id(self, checkpoint_repo, session_repo):
        """Test retrieving checkpoint by ID."""
        # Setup session
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="test_session_2",
            session_state={}
        )
        session = session_repo.create(session)
        
        # Create and retrieve
        cp = Checkpoint(
            internal_session_id=session.id,
            checkpoint_name="Get By ID",
            session_state={"data": "test"}
        )
        created = checkpoint_repo.create(cp)
        
        retrieved = checkpoint_repo.get_by_id(created.id)
        
        assert retrieved is not None
        assert retrieved.checkpoint_name == "Get By ID"
        assert retrieved.session_state["data"] == "test"
    
    def test_get_checkpoints_by_session(self, checkpoint_repo, session_repo):
        """Test retrieving all checkpoints for a session."""
        # Setup session
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="test_session_3",
            session_state={}
        )
        session = session_repo.create(session)
        
        # Create multiple checkpoints
        for i in range(3):
            cp = Checkpoint(
                internal_session_id=session.id,
                checkpoint_name=f"Checkpoint {i}",
                session_state={"index": i}
            )
            checkpoint_repo.create(cp)
        
        checkpoints = checkpoint_repo.get_by_internal_session(session.id)
        
        assert len(checkpoints) == 3
    
    def test_update_checkpoint_metadata(self, checkpoint_repo, session_repo):
        """Test updating checkpoint metadata."""
        # Setup
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="test_session_4",
            session_state={}
        )
        session = session_repo.create(session)
        
        cp = Checkpoint(
            internal_session_id=session.id,
            checkpoint_name="Metadata Test",
            metadata={"original": True}
        )
        created = checkpoint_repo.create(cp)
        
        # Update metadata
        result = checkpoint_repo.update_checkpoint_metadata(
            created.id,
            {"updated": True, "tool_track_position": 10}
        )
        
        assert result is True
        
        # Verify update
        retrieved = checkpoint_repo.get_by_id(created.id)
        assert retrieved.metadata.get("updated") is True
        assert retrieved.metadata.get("tool_track_position") == 10
    
    def test_delete_checkpoint(self, checkpoint_repo, session_repo):
        """Test deleting a checkpoint."""
        # Setup
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="test_session_5",
            session_state={}
        )
        session = session_repo.create(session)
        
        cp = Checkpoint(
            internal_session_id=session.id,
            checkpoint_name="To Delete"
        )
        created = checkpoint_repo.create(cp)
        
        # Delete
        result = checkpoint_repo.delete(created.id)
        
        assert result is True
        assert checkpoint_repo.get_by_id(created.id) is None


# ============== Internal Session Tests ==============

class TestInternalSession:
    """Tests for InternalSession model."""
    
    def test_session_creation(self):
        """Test creating an internal session."""
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="langgraph_test123",
            session_state={"initialized": True}
        )
        
        assert session.external_session_id == 1
        assert session.langgraph_session_id == "langgraph_test123"
        assert session.session_state["initialized"] is True
        assert session.is_current is True
    
    def test_session_add_message(self):
        """Test adding messages to conversation history."""
        session = InternalSession(external_session_id=1, langgraph_session_id="msg_test")
        
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[1]["content"] == "Hi there!"
    
    def test_session_update_state(self):
        """Test updating session state."""
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="state_test",
            session_state={"count": 0}
        )
        
        session.update_state({"count": 5, "new_key": "value"})
        
        assert session.session_state["count"] == 5
        assert session.session_state["new_key"] == "value"
    
    def test_session_is_branch(self):
        """Test branch detection."""
        # Non-branch session
        session1 = InternalSession(external_session_id=1, langgraph_session_id="s1")
        assert session1.is_branch() is False
        
        # Branch session
        session2 = InternalSession(
            external_session_id=1,
            langgraph_session_id="s2",
            parent_session_id=1
        )
        assert session2.is_branch() is True
    
    def test_session_to_dict(self):
        """Test session serialization."""
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="serialize_test",
            session_state={"key": "value"},
            metadata={"extra": "info"}
        )
        
        data = session.to_dict()
        
        assert data["external_session_id"] == 1
        assert data["langgraph_session_id"] == "serialize_test"
        assert data["session_state"]["key"] == "value"


class TestInternalSessionMDP:
    """Tests for InternalSession_mdp (MDP workflow support)."""
    
    def test_mdp_session_creation(self):
        """Test creating an MDP session with workflow fields."""
        session = InternalSession_mdp(
            external_session_id=1,
            current_node_id="start",
            workflow_variables={"input": "data"},
            execution_path=[]
        )
        
        assert session.current_node_id == "start"
        assert session.workflow_variables == {"input": "data"}
        assert session.execution_path == []
    
    def test_mdp_session_create_branch_from_checkpoint(self, checkpoint_repo, session_repo):
        """Test creating a branched MDP session from checkpoint."""
        # Create initial session
        session = InternalSession(
            external_session_id=1,
            langgraph_session_id="mdp_branch_test",
            session_state={}
        )
        session = session_repo.create(session)
        
        # Create checkpoint with MDP state
        cp = Checkpoint(
            internal_session_id=session.id,
            checkpoint_name="MDP Checkpoint",
            session_state={"graph_state": {"data": "value"}},
            metadata={
                "mdp_state": {
                    "current_node_id": "process",
                    "workflow_variables": {"step": 2},
                    "execution_path": ["start"]
                },
                "workflow_version": "1.0.0",
                "node_id": "process"
            }
        )
        cp = checkpoint_repo.create(cp)
        
        # Create branch
        branched = InternalSession_mdp.create_branch_from_checkpoint(
            checkpoint=cp,
            external_session_id=1,
            parent_session_id=session.id
        )
        
        assert branched.current_node_id == "process"
        assert branched.workflow_variables == {"step": 2}
        assert branched.execution_path == ["start"]
        assert branched.branch_point_checkpoint_id == cp.id


# ============== Checkpoint Manager MDP Tests ==============

class TestCheckpointManagerMDP:
    """Tests for CheckpointManager_mdp (dual granularity support)."""
    
    def test_create_node_checkpoint(self, checkpoint_manager_mdp, session_repo):
        """Test creating a node-level checkpoint."""
        # Setup session
        session = InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="node_cp_test",
            current_node_id="data_load",
            workflow_variables={"data_path": "/path/to/data"},
            execution_path=["start"]
        )
        session = session_repo.create(session)
        
        # Create node checkpoint
        cp = checkpoint_manager_mdp.create_node_checkpoint(
            internal_session=session,
            node_id="data_load",
            workflow_version="1.0.0",
            tool_track_position=5
        )
        
        assert cp is not None
        assert cp.metadata.get("checkpoint_type") == "node"
        assert cp.metadata.get("node_id") == "data_load"
        assert cp.metadata.get("workflow_version") == "1.0.0"
        assert "mdp_state" in cp.metadata
    
    def test_create_tool_message_checkpoint(self, checkpoint_manager_mdp, session_repo):
        """Test creating a tool/message level checkpoint."""
        # Setup session and parent node checkpoint
        session = InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="tool_cp_test",
            current_node_id="process",
            workflow_variables={},
            execution_path=["start", "data_load"]
        )
        session = session_repo.create(session)
        
        # Create parent node checkpoint first
        parent_cp = checkpoint_manager_mdp.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0"
        )
        
        # Create tool/message checkpoint
        child_cp = checkpoint_manager_mdp.create_tool_message_checkpoint(
            internal_session=session,
            parent_checkpoint_id=parent_cp.id,
            tool_track_position=3
        )
        
        assert child_cp is not None
        assert child_cp.metadata.get("checkpoint_type") == "tool_message"
        assert child_cp.metadata.get("parent_checkpoint_id") == parent_cp.id
    
    def test_get_node_checkpoints(self, checkpoint_manager_mdp, session_repo):
        """Test filtering to get only node-level checkpoints."""
        # Setup
        session = InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="filter_test",
            current_node_id="node1"
        )
        session = session_repo.create(session)
        
        # Create mixed checkpoints
        node_cp = checkpoint_manager_mdp.create_node_checkpoint(
            internal_session=session,
            node_id="node1",
            workflow_version="1.0.0"
        )
        
        checkpoint_manager_mdp.create_tool_message_checkpoint(
            internal_session=session,
            parent_checkpoint_id=node_cp.id
        )
        
        # Get only node checkpoints
        node_checkpoints = checkpoint_manager_mdp.get_node_checkpoints(session.id)
        
        assert len(node_checkpoints) == 1
        assert node_checkpoints[0].metadata.get("checkpoint_type") == "node"


# ============== Tool Manager Tests ==============

class TestToolManager:
    """Tests for ToolManager."""
    
    def test_record_tool_invocation(self, tool_manager):
        """Test recording a tool invocation."""
        tool_manager.record_tool_invocation(
            tool_name="test_tool",
            args={"param": "value"},
            result={"output": "success"},
            success=True
        )
        
        track = tool_manager.get_tool_track()
        
        assert len(track) == 1
        assert track[0].tool_name == "test_tool"
        assert track[0].success is True
    
    def test_get_tool_track_position(self, tool_manager):
        """Test getting current track position."""
        assert tool_manager.get_tool_track_position() == 0
        
        tool_manager.record_tool_invocation("tool1", {}, {})
        tool_manager.record_tool_invocation("tool2", {}, {})
        
        assert tool_manager.get_tool_track_position() == 2
    
    def test_register_reversible_tool(self, tool_manager):
        """Test registering a reversible tool."""
        def forward(args):
            return {"created": args["name"]}
        
        def reverse(args, result):
            pass  # Would undo the forward action
        
        tool_manager.register_reversible_tool("create_file", forward, reverse)
        
        # Verify registration
        spec = tool_manager.tool_rollback_registry.get_tool("create_file")
        assert spec is not None
        assert spec.name == "create_file"
    
    def test_tool_statistics(self, tool_manager):
        """Test getting tool usage statistics."""
        tool_manager.record_tool_invocation("tool_a", {}, {}, success=True)
        tool_manager.record_tool_invocation("tool_a", {}, {}, success=True)
        tool_manager.record_tool_invocation("tool_b", {}, {}, success=False, error_message="Failed")
        
        stats = tool_manager.get_tool_statistics()
        
        assert stats["total_invocations"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["tool_counts"]["tool_a"] == 2
    
    def test_clear_track(self, tool_manager):
        """Test clearing the tool track."""
        tool_manager.record_tool_invocation("tool", {}, {})
        tool_manager.record_tool_invocation("tool", {}, {})
        
        assert tool_manager.get_tool_track_position() == 2
        
        tool_manager.clear_track()
        
        assert tool_manager.get_tool_track_position() == 0


# ============== Event Bus Tests ==============

class TestEventBus:
    """Tests for EventBus pub-sub system."""
    
    def test_publish_subscribe(self):
        """Test basic publish/subscribe."""
        bus = EventBus()
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe(CheckpointCreatedEvent, handler)
        
        event = CheckpointCreatedEvent(
            timestamp=datetime.now(),
            checkpoint_id=1,
            session_id=1,
            checkpoint_name="Test"
        )
        bus.publish(event)
        
        assert len(received_events) == 1
        assert received_events[0].checkpoint_id == 1
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers for same event."""
        bus = EventBus()
        results = {"handler1": 0, "handler2": 0}
        
        def handler1(event):
            results["handler1"] += 1
        
        def handler2(event):
            results["handler2"] += 1
        
        bus.subscribe(SessionCreatedEvent, handler1)
        bus.subscribe(SessionCreatedEvent, handler2)
        
        event = SessionCreatedEvent(
            timestamp=datetime.now(),
            session_id=1,
            external_session_id=1
        )
        bus.publish(event)
        
        assert results["handler1"] == 1
        assert results["handler2"] == 1
    
    def test_event_history(self):
        """Test event history tracking."""
        bus = EventBus()
        
        for i in range(5):
            event = CheckpointCreatedEvent(
                timestamp=datetime.now(),
                checkpoint_id=i,
                session_id=1
            )
            bus.publish(event)
        
        history = bus.get_event_history()
        
        assert len(history) == 5
    
    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        call_count = 0
        
        def handler(event):
            nonlocal call_count
            call_count += 1
        
        bus.subscribe(CheckpointCreatedEvent, handler)
        
        # First event should be handled
        bus.publish(CheckpointCreatedEvent(
            timestamp=datetime.now(),
            checkpoint_id=1,
            session_id=1
        ))
        assert call_count == 1
        
        # Unsubscribe
        bus.unsubscribe(CheckpointCreatedEvent, handler)
        
        # Second event should not be handled
        bus.publish(CheckpointCreatedEvent(
            timestamp=datetime.now(),
            checkpoint_id=2,
            session_id=1
        ))
        assert call_count == 1


# ============== Workflow Graph Tests ==============

class TestWorkflowGraph:
    """Tests for WorkflowGraph structure."""
    
    def test_add_node(self, sample_workflow):
        """Test adding nodes to workflow."""
        assert len(sample_workflow.nodes) == 3
        assert "start" in sample_workflow.nodes
        assert "process" in sample_workflow.nodes
        assert "end" in sample_workflow.nodes
    
    def test_add_edge(self, sample_workflow):
        """Test adding edges to workflow."""
        assert len(sample_workflow.edges) == 2
    
    def test_get_outgoing_edges(self, sample_workflow):
        """Test getting outgoing edges from a node."""
        edges = sample_workflow.get_outgoing_edges("start")
        
        assert len(edges) == 1
        assert edges[0].target_id == "process"
    
    def test_entry_point(self, sample_workflow):
        """Test workflow entry point."""
        assert sample_workflow.entry_point == "start"
    
    def test_get_node(self, sample_workflow):
        """Test getting a node by ID."""
        node = sample_workflow.get_node("process")
        
        assert node is not None
        assert node.name == "Process"
        assert node.tool_name == "process_tool"


# ============== Integration Test ==============

class TestAgentGitIntegration:
    """Integration tests for AgentGit v2 components."""
    
    def test_full_checkpoint_workflow(self, temp_db):
        """Test complete checkpoint creation and retrieval workflow."""
        # Initialize repositories
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_manager = CheckpointManager_mdp(checkpoint_repo)
        
        # Create session
        session = InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="integration_test",
            current_node_id="start",
            workflow_variables={"input": "test_data"},
            execution_path=[]
        )
        session = session_repo.create(session)
        
        # Create checkpoints at different nodes
        cp1 = checkpoint_manager.create_node_checkpoint(
            internal_session=session,
            node_id="start",
            workflow_version="1.0.0",
            tool_track_position=0
        )
        
        # Simulate node execution
        session.execution_path.append("start")
        session.current_node_id = "process"
        session.workflow_variables["processed"] = True
        session_repo.update(session)
        
        cp2 = checkpoint_manager.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0",
            tool_track_position=2
        )
        
        # Verify checkpoints
        checkpoints = checkpoint_repo.get_by_internal_session(session.id)
        assert len(checkpoints) == 2
        
        # Verify checkpoint content
        cp1_retrieved = checkpoint_manager.get_checkpoint(cp1.id)
        assert cp1_retrieved.metadata["node_id"] == "start"
        
        cp2_retrieved = checkpoint_manager.get_checkpoint(cp2.id)
        assert cp2_retrieved.metadata["node_id"] == "process"
        assert "processed" in cp2_retrieved.metadata["mdp_state"]["workflow_variables"]
    
    def test_branch_and_rollback_workflow(self, temp_db):
        """Test branching from checkpoint (rollback scenario)."""
        # Initialize
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_manager = CheckpointManager_mdp(checkpoint_repo)
        
        # Create initial session
        original_session = InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="original_session",
            current_node_id="start",
            workflow_variables={"version": 1}
        )
        original_session = session_repo.create(original_session)
        
        # Create checkpoint
        cp = checkpoint_manager.create_node_checkpoint(
            internal_session=original_session,
            node_id="start",
            workflow_version="1.0.0"
        )
        
        # Simulate execution continuing
        original_session.current_node_id = "error_node"
        original_session.workflow_variables["error"] = True
        session_repo.update(original_session)
        
        # Now "rollback" by creating a branch from the checkpoint
        branched_session = InternalSession_mdp.create_branch_from_checkpoint(
            checkpoint=cp,
            external_session_id=1,
            parent_session_id=original_session.id
        )
        branched_session = session_repo.create(branched_session)
        
        # Verify branch state is from checkpoint (not error state)
        assert branched_session.current_node_id == "start"
        assert "error" not in branched_session.workflow_variables
        assert branched_session.parent_session_id == original_session.id
        assert branched_session.branch_point_checkpoint_id == cp.id


# ============== Session Management Tests ==============

class TestSessionManagement:
    """Tests for internal/external session relationship and management."""
    
    def test_internal_sessions_per_external_session(self, session_repo):
        """Test that multiple internal sessions can belong to one external session."""
        external_id = 1
        
        # Create multiple internal sessions for the same external session
        sessions = []
        for i in range(3):
            session = InternalSession(
                external_session_id=external_id,
                langgraph_session_id=f"session_{i}",
                session_state={"index": i}
            )
            sessions.append(session_repo.create(session))
        
        # Query all internal sessions for external session
        result = session_repo.get_by_external_session(external_id)
        
        assert len(result) == 3
        # Should be ordered by created_at DESC
        assert result[0].langgraph_session_id == "session_2"
    
    def test_current_session_switching(self, session_repo):
        """Test switching current session within an external session."""
        external_id = 1
        
        # Create two sessions
        session1 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="session_1",
            is_current=True
        ))
        
        session2 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="session_2",
            is_current=True  # This should mark session1 as not current
        ))
        
        # Verify only one is current
        current = session_repo.get_current_session(external_id)
        assert current is not None
        assert current.id == session2.id
        
        # Switch current to session1
        session_repo.set_current_session(session1.id)
        
        current = session_repo.get_current_session(external_id)
        assert current.id == session1.id
        
        # Verify session2 is no longer current
        session2_updated = session_repo.get_by_id(session2.id)
        assert session2_updated.is_current is False
    
    def test_session_count_per_external(self, session_repo):
        """Test counting sessions for an external session."""
        external_id = 1
        
        for i in range(5):
            session_repo.create(InternalSession(
                external_session_id=external_id,
                langgraph_session_id=f"count_session_{i}"
            ))
        
        count = session_repo.count_sessions(external_id)
        assert count == 5
    
    def test_branch_sessions_relationship(self, session_repo):
        """Test parent-child session relationship (branching)."""
        external_id = 1
        
        # Create parent session
        parent = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="parent_session",
            session_state={"level": 0}
        ))
        
        # Create child sessions (branches)
        child1 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="child_session_1",
            parent_session_id=parent.id,
            session_state={"level": 1, "branch": "a"}
        ))
        
        child2 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="child_session_2",
            parent_session_id=parent.id,
            session_state={"level": 1, "branch": "b"}
        ))
        
        # Get branch sessions
        branches = session_repo.get_branch_sessions(parent.id)
        
        assert len(branches) == 2
        assert all(b.parent_session_id == parent.id for b in branches)
    
    def test_session_lineage(self, session_repo):
        """Test getting session lineage (root to current)."""
        external_id = 1
        
        # Create a chain: root -> branch1 -> branch2
        root = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="root"
        ))
        
        branch1 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="branch1",
            parent_session_id=root.id
        ))
        
        branch2 = session_repo.create(InternalSession(
            external_session_id=external_id,
            langgraph_session_id="branch2",
            parent_session_id=branch1.id
        ))
        
        # Get lineage from branch2
        lineage = session_repo.get_session_lineage(branch2.id)
        
        assert len(lineage) == 3
        assert lineage[0].id == root.id
        assert lineage[1].id == branch1.id
        assert lineage[2].id == branch2.id
    
    def test_tool_invocation_count_update(self, session_repo):
        """Test updating tool invocation count."""
        session = session_repo.create(InternalSession(
            external_session_id=1,
            langgraph_session_id="tool_count_test",
            tool_invocation_count=0
        ))
        
        # Increment multiple times
        session_repo.update_tool_count(session.id, 1)
        session_repo.update_tool_count(session.id, 3)
        
        updated = session_repo.get_by_id(session.id)
        assert updated.tool_invocation_count == 4
    
    def test_session_isolation_across_external_sessions(self, session_repo):
        """Test that sessions are properly isolated across external sessions."""
        # Create sessions for external session 1
        for i in range(3):
            session_repo.create(InternalSession(
                external_session_id=1,
                langgraph_session_id=f"ext1_session_{i}"
            ))
        
        # Create sessions for external session 2
        for i in range(2):
            session_repo.create(InternalSession(
                external_session_id=2,
                langgraph_session_id=f"ext2_session_{i}"
            ))
        
        # Verify isolation
        ext1_sessions = session_repo.get_by_external_session(1)
        ext2_sessions = session_repo.get_by_external_session(2)
        
        assert len(ext1_sessions) == 3
        assert len(ext2_sessions) == 2
        
        # Ensure no cross-contamination
        assert all(s.external_session_id == 1 for s in ext1_sessions)
        assert all(s.external_session_id == 2 for s in ext2_sessions)


# ============== Dual Granularity Rollback Tests ==============

class TestDualGranularityRollback:
    """Tests for rollback with Node and Tool/Message granularity checkpoints."""
    
    def test_node_checkpoint_creation_and_retrieval(self, temp_db):
        """Test creating and retrieving node-level checkpoints."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        # Create session
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="node_test",
            current_node_id="start",
            workflow_variables={"data": "initial"}
        ))
        
        # Create node checkpoints at different nodes
        cp1 = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="start",
            workflow_version="1.0.0",
            tool_track_position=0
        )
        
        session.current_node_id = "process"
        session.workflow_variables = {"data": "processed"}
        session_repo.update(session)
        
        cp2 = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0",
            tool_track_position=3
        )
        
        # Retrieve only node checkpoints
        node_cps = checkpoint_mgr.get_node_checkpoints(session.id)
        
        assert len(node_cps) == 2
        assert all(cp.metadata.get("checkpoint_type") == "node" for cp in node_cps)
    
    def test_tool_message_checkpoint_hierarchy(self, temp_db):
        """Test tool/message checkpoints as children of node checkpoints."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="tool_msg_test",
            current_node_id="process"
        ))
        
        # Create parent node checkpoint
        parent_cp = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0"
        )
        
        # Create multiple tool/message checkpoints under the node
        tool_cps = []
        for i in range(3):
            tool_cp = checkpoint_mgr.create_tool_message_checkpoint(
                internal_session=session,
                parent_checkpoint_id=parent_cp.id,
                tool_track_position=i + 1
            )
            tool_cps.append(tool_cp)
        
        # Verify hierarchy
        for tcp in tool_cps:
            assert tcp.metadata.get("checkpoint_type") == "tool_message"
            assert tcp.metadata.get("parent_checkpoint_id") == parent_cp.id
        
        # All checkpoints should be present
        all_cps = checkpoint_repo.get_by_internal_session(session.id)
        assert len(all_cps) == 4  # 1 node + 3 tool/message
    
    def test_rollback_to_node_checkpoint(self, temp_db):
        """Test rollback to a node-level checkpoint."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        # Setup: Create session and checkpoints
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="rollback_node_test",
            current_node_id="start",
            workflow_variables={"step": 1},
            execution_path=[]
        ))
        
        # Checkpoint at start
        cp_start = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="start",
            workflow_version="1.0.0"
        )
        
        # Progress to next node
        session.current_node_id = "process"
        session.workflow_variables = {"step": 2}
        session.execution_path = ["start"]
        session_repo.update(session)
        
        # Checkpoint at process
        cp_process = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0"
        )
        
        # Progress further (to error state)
        session.current_node_id = "error"
        session.workflow_variables = {"step": 3, "error": True}
        session_repo.update(session)
        
        # Now rollback to "start" checkpoint by creating a branch
        branched = InternalSession_mdp.create_branch_from_checkpoint(
            checkpoint=cp_start,
            external_session_id=1,
            parent_session_id=session.id
        )
        branched = session_repo.create(branched)
        
        # Verify rollback state
        assert branched.current_node_id == "start"
        assert branched.workflow_variables.get("step") == 1
        assert "error" not in branched.workflow_variables
        assert branched.execution_path == []
    
    def test_rollback_to_tool_message_checkpoint(self, temp_db):
        """Test rollback to a tool/message-level checkpoint (fine-grained)."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="rollback_tool_test",
            current_node_id="process",
            workflow_variables={"counter": 0}
        ))
        
        # Node checkpoint
        node_cp = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0",
            tool_track_position=0
        )
        
        # Simulate tool executions with checkpoints
        for i in range(1, 4):
            session.workflow_variables["counter"] = i
            session_repo.update(session)
            checkpoint_mgr.create_tool_message_checkpoint(
                internal_session=session,
                parent_checkpoint_id=node_cp.id,
                tool_track_position=i
            )
        
        # Final state has counter = 3, but checkpoint at counter = 2 exists
        tool_cps = checkpoint_repo.get_by_internal_session(session.id)
        cp_at_2 = next(
            cp for cp in tool_cps 
            if cp.metadata.get("checkpoint_type") == "tool_message" 
            and cp.metadata.get("tool_track_position") == 2
        )
        
        # Rollback to counter = 2
        branched = InternalSession_mdp.create_branch_from_checkpoint(
            checkpoint=cp_at_2,
            external_session_id=1,
            parent_session_id=session.id
        )
        branched = session_repo.create(branched)
        
        assert branched.workflow_variables.get("counter") == 2
        assert branched.branch_point_checkpoint_id == cp_at_2.id
    
    def test_mixed_granularity_checkpoint_retrieval(self, temp_db):
        """Test retrieving checkpoints with mixed granularities."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="mixed_test",
            current_node_id="node1"
        ))
        
        # Create: 2 node checkpoints, 3 tool/message checkpoints each
        for node_id in ["node1", "node2"]:
            session.current_node_id = node_id
            session_repo.update(session)
            
            node_cp = checkpoint_mgr.create_node_checkpoint(
                internal_session=session,
                node_id=node_id,
                workflow_version="1.0.0"
            )
            
            for i in range(3):
                checkpoint_mgr.create_tool_message_checkpoint(
                    internal_session=session,
                    parent_checkpoint_id=node_cp.id,
                    tool_track_position=i
                )
        
        # Get all checkpoints
        all_cps = checkpoint_repo.get_by_internal_session(session.id)
        assert len(all_cps) == 8  # 2 nodes + 6 tool/message
        
        # Get only node checkpoints
        node_only = checkpoint_mgr.get_node_checkpoints(session.id)
        assert len(node_only) == 2
        
        # Verify we can filter by type
        node_types = [cp for cp in all_cps if cp.metadata.get("checkpoint_type") == "node"]
        tool_types = [cp for cp in all_cps if cp.metadata.get("checkpoint_type") == "tool_message"]
        
        assert len(node_types) == 2
        assert len(tool_types) == 6
    
    def test_rollback_preserves_checkpoint_lineage(self, temp_db):
        """Test that rollback creates proper checkpoint lineage for debugging."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        # Create initial session with checkpoints
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="lineage_test",
            current_node_id="start"
        ))
        
        cp1 = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="start",
            workflow_version="1.0.0"
        )
        
        session.current_node_id = "process"
        session_repo.update(session)
        
        cp2 = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0"
        )
        
        # Rollback by creating branch
        branch1 = InternalSession_mdp.create_branch_from_checkpoint(
            checkpoint=cp1,
            external_session_id=1,
            parent_session_id=session.id
        )
        branch1 = session_repo.create(branch1)
        
        # Create checkpoint in branched session
        cp_branch = checkpoint_mgr.create_node_checkpoint(
            internal_session=branch1,
            node_id="alternative",
            workflow_version="1.0.0"
        )
        
        # Verify lineage
        lineage = session_repo.get_session_lineage(branch1.id)
        assert len(lineage) == 2
        assert lineage[0].id == session.id
        assert lineage[1].id == branch1.id
        
        # Branch1 should track its branch point
        assert branch1.branch_point_checkpoint_id == cp1.id


# ============== Tool Rollback Integration Tests ==============

class TestToolRollbackWithCheckpoints:
    """Tests for tool rollback integrated with checkpoint system."""
    
    def test_tool_track_position_in_checkpoints(self, temp_db):
        """Test that tool track position is properly stored in checkpoints."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        tool_mgr = ToolManager(tools=[])
        
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="tool_track_test",
            current_node_id="process"
        ))
        
        # Simulate tool executions
        tool_mgr.record_tool_invocation("tool1", {}, {})
        tool_mgr.record_tool_invocation("tool2", {}, {})
        
        # Create checkpoint with current tool position
        cp = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="process",
            workflow_version="1.0.0",
            tool_track_position=tool_mgr.get_tool_track_position()
        )
        
        # More tools executed
        tool_mgr.record_tool_invocation("tool3", {}, {})
        tool_mgr.record_tool_invocation("tool4", {}, {})
        
        # Verify checkpoint has correct position
        retrieved = checkpoint_mgr.get_checkpoint(cp.id)
        assert retrieved.get_tool_track_position() == 2
        
        # Current position is 4
        assert tool_mgr.get_tool_track_position() == 4
    
    def test_reversible_tool_registration(self, tool_manager):
        """Test registering tools with reverse functions."""
        files_created = []
        
        def create_file(args):
            path = args["path"]
            files_created.append(path)
            return {"path": path, "created": True}
        
        def delete_file(args, result):
            path = result["path"]
            files_created.remove(path)
        
        tool_manager.register_reversible_tool("create_file", create_file, delete_file)
        
        # Verify the tool is registered in the rollback registry
        spec = tool_manager.tool_rollback_registry.get_tool("create_file")
        assert spec is not None
        assert spec.name == "create_file"
        
        # Manually execute forward function to test it works
        result = create_file({"path": "/test/file.txt"})
        assert len(files_created) == 1
        assert result["created"] is True
        
        # Record the invocation
        tool_manager.record_tool_invocation("create_file", {"path": "/test/file.txt"}, result)
        
        # Verify it was tracked
        assert tool_manager.get_tool_track_position() == 1


# ============== Audit Trail Tests ==============

class TestAuditEvent:
    """Tests for AuditEvent model."""
    
    def test_audit_event_creation(self):
        """Test creating an audit event with all attributes."""
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Tool completed successfully",
            details={"tool_name": "test_tool", "output": "result"},
            duration_ms=150.5
        )
        
        assert event.event_type == EventType.TOOL_SUCCESS
        assert event.severity == EventSeverity.SUCCESS
        assert event.message == "Tool completed successfully"
        assert event.duration_ms == 150.5
    
    def test_audit_event_with_error(self):
        """Test audit event with error field."""
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_ERROR,
            severity=EventSeverity.ERROR,
            message="Tool failed",
            error="Connection timeout"
        )
        
        assert event.error == "Connection timeout"
    
    def test_audit_event_to_dict(self):
        """Test serializing audit event to dictionary."""
        timestamp = datetime.now()
        event = AuditEvent(
            timestamp=timestamp,
            event_type=EventType.CHECKPOINT_CREATED,
            severity=EventSeverity.INFO,
            message="Checkpoint created",
            details={"checkpoint_id": 1}
        )
        
        data = event.to_dict()
        
        assert data["timestamp"] == timestamp.isoformat()
        assert data["event_type"] == "checkpoint_created"
        assert data["severity"] == "info"
        assert data["details"]["checkpoint_id"] == 1
    
    def test_audit_event_format_user_friendly(self):
        """Test user-friendly formatting."""
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Tool 'calculate' completed",
            duration_ms=150
        )
        
        formatted = event.format_user_friendly()
        
        assert "✅" in formatted
        assert "calculate" in formatted
        assert "150ms" in formatted
    
    def test_audit_event_format_with_error(self):
        """Test formatting with error message."""
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_ERROR,
            severity=EventSeverity.ERROR,
            message="Tool failed",
            error="Division by zero"
        )
        
        formatted = event.format_user_friendly()
        
        assert "❌" in formatted
        assert "Division by zero" in formatted


class TestAuditTrail:
    """Tests for AuditTrail collection and management."""
    
    def test_audit_trail_creation(self):
        """Test creating an audit trail."""
        trail = AuditTrail(session_id="test_session_123")
        
        assert trail.session_id == "test_session_123"
        assert len(trail.events) == 0
    
    def test_add_events(self):
        """Test adding events to trail."""
        trail = AuditTrail()
        
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_START,
            severity=EventSeverity.INFO,
            message="Tool started"
        ))
        
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Tool completed"
        ))
        
        assert len(trail.events) == 2
    
    def test_get_errors(self):
        """Test filtering error events."""
        trail = AuditTrail()
        
        # Add mixed events
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Success"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_ERROR,
            severity=EventSeverity.ERROR,
            message="Error 1",
            error="Failed"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_ERROR,
            severity=EventSeverity.ERROR,
            message="Error 2",
            error="Also failed"
        ))
        
        errors = trail.get_errors()
        
        assert len(errors) == 2
        assert all(e.severity == EventSeverity.ERROR for e in errors)
    
    def test_get_tool_events(self):
        """Test filtering tool-related events."""
        trail = AuditTrail()
        
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_START,
            severity=EventSeverity.INFO,
            message="Tool start"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.LLM_CALL,
            severity=EventSeverity.INFO,
            message="LLM call"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Tool success"
        ))
        
        tool_events = trail.get_tool_events()
        
        assert len(tool_events) == 2
    
    def test_get_summary(self):
        """Test generating summary statistics."""
        trail = AuditTrail()
        
        # Add various events
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_START,
            severity=EventSeverity.INFO,
            message="Start"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Success"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_ERROR,
            severity=EventSeverity.ERROR,
            message="Error"
        ))
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.CHECKPOINT_CREATED,
            severity=EventSeverity.INFO,
            message="Checkpoint"
        ))
        
        summary = trail.get_summary()
        
        assert summary["total_events"] == 4
        assert summary["tool_calls"] == 1  # TOOL_START
        assert summary["successful_tools"] == 1
        assert summary["failed_tools"] == 1
        assert summary["checkpoints"] == 1
        assert summary["errors"] == 1
    
    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = AuditTrail(session_id="serialize_test")
        
        original.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Test event",
            details={"key": "value"},
            duration_ms=100.5
        ))
        
        # Serialize
        data = original.to_dict()
        
        assert data["session_id"] == "serialize_test"
        assert len(data["events"]) == 1
        assert "summary" in data
        
        # Deserialize
        restored = AuditTrail.from_dict(data)
        
        assert restored.session_id == "serialize_test"
        assert len(restored.events) == 1
        assert restored.events[0].message == "Test event"
        assert restored.events[0].duration_ms == 100.5
    
    def test_format_user_display(self):
        """Test user-friendly display formatting."""
        trail = AuditTrail()
        
        for i in range(5):
            trail.add_event(AuditEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_SUCCESS,
                severity=EventSeverity.SUCCESS,
                message=f"Event {i}"
            ))
        
        display = trail.format_user_display()
        
        assert "=== Audit Trail ===" in display
        assert "Total Events: 5" in display
    
    def test_format_user_display_truncation(self):
        """Test that display truncates to 20 events by default."""
        trail = AuditTrail()
        
        # Add 25 events
        for i in range(25):
            trail.add_event(AuditEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_SUCCESS,
                severity=EventSeverity.SUCCESS,
                message=f"Event {i}"
            ))
        
        display = trail.format_user_display(show_all=False)
        
        assert "5 more events" in display
    
    def test_empty_trail_display(self):
        """Test display for empty trail."""
        trail = AuditTrail()
        
        display = trail.format_user_display()
        
        assert "No events recorded" in display


# ============== External Session Tests ==============

class TestExternalSession:
    """Tests for ExternalSession model."""
    
    def test_external_session_creation(self):
        """Test creating an external session."""
        session = ExternalSession(
            user_id=1,
            session_name="Test Session",
            created_at=datetime.now()
        )
        
        assert session.user_id == 1
        assert session.session_name == "Test Session"
        assert session.is_active is True
        assert session.branch_count == 0
    
    def test_add_internal_session(self):
        """Test adding internal sessions to external session."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        session.add_internal_session("internal_1")
        session.add_internal_session("internal_2")
        
        assert len(session.internal_session_ids) == 2
        assert session.current_internal_session_id == "internal_2"
    
    def test_add_branch_session(self):
        """Test adding a branch session increments counter."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        session.add_internal_session("main")
        session.add_internal_session("branch_1", is_branch=True)
        session.add_internal_session("branch_2", is_branch=True)
        
        assert session.branch_count == 2
    
    def test_set_current_internal_session(self):
        """Test switching current internal session."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        session.add_internal_session("session_1")
        session.add_internal_session("session_2")
        
        assert session.current_internal_session_id == "session_2"
        
        result = session.set_current_internal_session("session_1")
        
        assert result is True
        assert session.current_internal_session_id == "session_1"
    
    def test_set_current_internal_session_invalid(self):
        """Test setting invalid session returns False."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        result = session.set_current_internal_session("nonexistent")
        
        assert result is False
    
    def test_get_branch_info(self):
        """Test getting branch information."""
        session = ExternalSession(user_id=1, session_name="Test")
        session.add_internal_session("main")
        session.add_internal_session("branch", is_branch=True)
        
        info = session.get_branch_info()
        
        assert info["total_branches"] == 1
        assert info["total_sessions"] == 2
        assert info["is_branched"] is True
    
    def test_update_metadata(self):
        """Test updating session metadata."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        session.update_metadata({"model": "gpt-4", "temperature": 0.7})
        session.update_metadata({"temperature": 0.5})
        
        assert session.metadata["model"] == "gpt-4"
        assert session.metadata["temperature"] == 0.5
    
    def test_increment_checkpoint_count(self):
        """Test incrementing checkpoint count."""
        session = ExternalSession(user_id=1, session_name="Test")
        
        session.increment_checkpoint_count()
        session.increment_checkpoint_count()
        
        assert session.total_checkpoints == 2
    
    def test_get_session_age(self):
        """Test getting session age."""
        session = ExternalSession(
            user_id=1,
            session_name="Test",
            created_at=datetime.now()
        )
        
        age = session.get_session_age()
        
        assert age is not None
        assert age >= 0  # Should be very small
    
    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = ExternalSession(
            user_id=1,
            session_name="Serialize Test",
            created_at=datetime.now(),
            metadata={"key": "value"}
        )
        original.add_internal_session("session_1")
        original.add_internal_session("session_2", is_branch=True)
        
        # Serialize
        data = original.to_dict()
        
        assert data["user_id"] == 1
        assert data["session_name"] == "Serialize Test"
        assert data["branch_count"] == 1
        
        # Deserialize
        restored = ExternalSession.from_dict(data)
        
        assert restored.user_id == 1
        assert restored.session_name == "Serialize Test"
        assert len(restored.internal_session_ids) == 2
        assert restored.branch_count == 1


class TestExternalSessionRepository:
    """Tests for ExternalSessionRepository CRUD operations."""
    
    def test_create_external_session(self, temp_db):
        """Test creating an external session."""
        repo = ExternalSessionRepository(temp_db)
        
        session = ExternalSession(
            user_id=1,
            session_name="New Session"
        )
        
        created = repo.create(session)
        
        assert created.id is not None
        assert created.session_name == "New Session"
    
    def test_get_external_session_by_id(self, temp_db):
        """Test retrieving external session by ID."""
        repo = ExternalSessionRepository(temp_db)
        
        session = ExternalSession(user_id=1, session_name="Get By ID")
        created = repo.create(session)
        
        retrieved = repo.get_by_id(created.id)
        
        assert retrieved is not None
        assert retrieved.session_name == "Get By ID"
    
    def test_get_sessions_by_user(self, temp_db):
        """Test retrieving all sessions for a user."""
        repo = ExternalSessionRepository(temp_db)
        
        # Create multiple sessions
        for i in range(3):
            session = ExternalSession(user_id=1, session_name=f"Session {i}")
            repo.create(session)
        
        sessions = repo.get_user_sessions(1)
        
        assert len(sessions) >= 3  # May include fixture sessions
    
    def test_update_external_session(self, temp_db):
        """Test updating an external session."""
        repo = ExternalSessionRepository(temp_db)
        
        session = ExternalSession(user_id=1, session_name="Original Name")
        created = repo.create(session)
        
        created.session_name = "Updated Name"
        created.update_metadata({"updated": True})
        repo.update(created)
        
        retrieved = repo.get_by_id(created.id)
        
        assert retrieved.session_name == "Updated Name"
    
    def test_deactivate_session(self, temp_db):
        """Test deactivating a session."""
        repo = ExternalSessionRepository(temp_db)
        
        session = ExternalSession(user_id=1, session_name="To Deactivate")
        created = repo.create(session)
        
        assert created.is_active is True
        
        repo.deactivate(created.id)
        
        retrieved = repo.get_by_id(created.id)
        assert retrieved.is_active is False


# ============== Tool Rollback Registry Tests ==============

class TestToolRollbackRegistry:
    """Tests for ToolRollbackRegistry operations."""
    
    def test_registry_creation(self):
        """Test creating a tool rollback registry."""
        registry = ToolRollbackRegistry()
        
        assert registry.get_track() == []
    
    def test_register_tool(self):
        """Test registering a tool specification."""
        registry = ToolRollbackRegistry()
        
        def forward_fn(args):
            return {"created": args["name"]}
        
        def reverse_fn(args, result):
            pass
        
        spec = ToolSpec(name="create", forward=forward_fn, reverse=reverse_fn)
        registry.register_tool(spec)
        
        retrieved = registry.get_tool("create")
        
        assert retrieved is not None
        assert retrieved.name == "create"
    
    def test_record_invocation(self):
        """Test recording tool invocations."""
        registry = ToolRollbackRegistry()
        
        registry.record_invocation(
            tool_name="test_tool",
            args={"param": "value"},
            result={"output": "success"},
            success=True
        )
        
        track = registry.get_track()
        
        assert len(track) == 1
        assert track[0].tool_name == "test_tool"
        assert track[0].success is True
    
    def test_truncate_track(self):
        """Test truncating the invocation track."""
        registry = ToolRollbackRegistry()
        
        for i in range(5):
            registry.record_invocation(f"tool_{i}", {}, {})
        
        assert len(registry.get_track()) == 5
        
        registry.truncate_track(3)
        
        assert len(registry.get_track()) == 3
    
    def test_rollback_with_reversible_tools(self):
        """Test rolling back reversible tool invocations."""
        registry = ToolRollbackRegistry()
        state = {"files": []}
        
        def create_file(args):
            state["files"].append(args["path"])
            return {"path": args["path"]}
        
        def delete_file(args, result):
            state["files"].remove(result["path"])
        
        # Register reversible tool
        registry.register_tool(ToolSpec(
            name="create_file",
            forward=create_file,
            reverse=delete_file
        ))
        
        # Execute forward
        result = create_file({"path": "/test/file.txt"})
        registry.record_invocation("create_file", {"path": "/test/file.txt"}, result)
        
        assert len(state["files"]) == 1
        
        # Rollback
        results = registry.rollback()
        
        assert len(results) == 1
        assert results[0].reversed_successfully is True
        assert len(state["files"]) == 0
        assert len(registry.get_track()) == 0
    
    def test_rollback_non_reversible_tool(self):
        """Test rollback for tool without reverse handler."""
        registry = ToolRollbackRegistry()
        
        # Register tool without reverse
        registry.register_tool(ToolSpec(
            name="read_only",
            forward=lambda args: args
        ))
        
        registry.record_invocation("read_only", {}, {})
        
        results = registry.rollback()
        
        assert len(results) == 1
        assert results[0].reversed_successfully is False
        assert "No reverse handler" in results[0].error_message
    
    def test_rollback_skips_checkpoint_tools(self):
        """Test that checkpoint management tools are skipped during rollback."""
        registry = ToolRollbackRegistry()
        
        # Record checkpoint tool invocation
        registry.record_invocation("create_checkpoint", {"name": "cp1"}, {"id": 1})
        registry.record_invocation("some_other_tool", {}, {})
        
        results = registry.rollback()
        
        # Only one result (checkpoint tool skipped)
        assert len(results) == 1
        assert results[0].tool_name == "some_other_tool"
    
    def test_redo_operations(self):
        """Test redoing tool operations."""
        registry = ToolRollbackRegistry()
        call_count = {"value": 0}
        
        def counting_forward(args):
            call_count["value"] += 1
            return {"count": call_count["value"]}
        
        registry.register_tool(ToolSpec(
            name="counter",
            forward=counting_forward
        ))
        
        # Record initial invocations
        registry.record_invocation("counter", {}, {"count": 1})
        registry.record_invocation("counter", {}, {"count": 2})
        
        # Redo
        new_records = registry.redo()
        
        assert len(new_records) == 2
        assert call_count["value"] == 2  # Forward was called twice


# ============== Node Manager Tests ==============

class TestNodeManager:
    """Tests for NodeManager workflow orchestration."""
    
    @pytest.fixture
    def node_manager_setup(self, sample_workflow):
        """Create a NodeManager with sample workflow and tools."""
        from langchain_core.tools import tool
        
        @tool
        def start_tool(context: dict = {}) -> dict:
            """Start tool."""
            return {"started": True}
        
        @tool
        def process_tool(context: dict = {}) -> dict:
            """Process tool."""
            return {"processed": True}
        
        @tool
        def end_tool(context: dict = {}) -> dict:
            """End tool."""
            return {"ended": True}
        
        tool_mgr = ToolManager(tools=[start_tool, process_tool, end_tool])
        node_mgr = NodeManager(sample_workflow, tool_mgr)
        
        return node_mgr, tool_mgr
    
    def test_get_mdp_state_from_mdp_session(self, sample_workflow):
        """Test getting MDP state from InternalSession_mdp."""
        tool_mgr = ToolManager(tools=[])
        node_mgr = NodeManager(sample_workflow, tool_mgr)
        
        session = InternalSession_mdp(
            external_session_id=1,
            current_node_id="process",
            workflow_variables={"data": "test"},
            execution_path=["start"]
        )
        
        state = node_mgr.get_mdp_state(session)
        
        assert state["current_node_id"] == "process"
        assert state["workflow_variables"] == {"data": "test"}
        assert state["execution_path"] == ["start"]
    
    def test_get_mdp_state_default_entry(self, sample_workflow):
        """Test default entry point when no current node."""
        tool_mgr = ToolManager(tools=[])
        node_mgr = NodeManager(sample_workflow, tool_mgr)
        
        session = InternalSession_mdp(
            external_session_id=1,
            current_node_id=None
        )
        
        state = node_mgr.get_mdp_state(session)
        
        assert state["current_node_id"] == "start"  # Entry point
    
    def test_update_mdp_state(self, sample_workflow):
        """Test updating MDP state in session."""
        tool_mgr = ToolManager(tools=[])
        node_mgr = NodeManager(sample_workflow, tool_mgr)
        
        session = InternalSession_mdp(
            external_session_id=1,
            current_node_id="start"
        )
        
        new_state = {
            "current_node_id": "process",
            "workflow_variables": {"updated": True},
            "execution_path": ["start"]
        }
        
        node_mgr.update_mdp_state(session, new_state)
        
        assert session.current_node_id == "process"
        assert session.workflow_variables == {"updated": True}
        assert session.execution_path == ["start"]


# ============== Audit Trail with Checkpoint Integration ==============

class TestAuditTrailCheckpointIntegration:
    """Tests for AuditTrail integration with checkpoints."""
    
    def test_audit_trail_stored_in_checkpoint(self, temp_db):
        """Test storing audit trail in checkpoint metadata."""
        session_repo = InternalSessionRepository(temp_db)
        checkpoint_repo = CheckpointRepository(temp_db)
        checkpoint_mgr = CheckpointManager_mdp(checkpoint_repo)
        
        # Create session
        session = session_repo.create(InternalSession_mdp(
            external_session_id=1,
            langgraph_session_id="audit_checkpoint_test",
            current_node_id="start"
        ))
        
        # Create audit trail
        trail = AuditTrail(session_id=session.langgraph_session_id)
        trail.add_event(AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_SUCCESS,
            severity=EventSeverity.SUCCESS,
            message="Tool executed",
            duration_ms=100
        ))
        
        # Create checkpoint with audit trail in metadata
        cp = checkpoint_mgr.create_node_checkpoint(
            internal_session=session,
            node_id="start",
            workflow_version="1.0.0"
        )
        
        # Update checkpoint metadata with audit trail
        checkpoint_repo.update_checkpoint_metadata(
            cp.id,
            {**cp.metadata, "audit_trail": trail.to_dict()}
        )
        
        # Retrieve and verify
        retrieved = checkpoint_repo.get_by_id(cp.id)
        
        assert "audit_trail" in retrieved.metadata
        
        # Restore audit trail
        restored_trail = AuditTrail.from_dict(retrieved.metadata["audit_trail"])
        
        assert len(restored_trail.events) == 1
        assert restored_trail.events[0].message == "Tool executed"
    
    def test_checkpoint_created_event(self):
        """Test recording checkpoint creation in audit trail."""
        trail = AuditTrail()
        
        # Simulate checkpoint creation event
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.CHECKPOINT_CREATED,
            severity=EventSeverity.INFO,
            message="Checkpoint 'before_process' created",
            details={"checkpoint_id": 5, "node_id": "process"}
        )
        trail.add_event(event)
        
        summary = trail.get_summary()
        
        assert summary["checkpoints"] == 1
    
    def test_rollback_event_in_audit(self):
        """Test recording rollback event in audit trail."""
        trail = AuditTrail()
        
        event = AuditEvent(
            timestamp=datetime.now(),
            event_type=EventType.ROLLBACK,
            severity=EventSeverity.WARNING,
            message="Rolled back to checkpoint 3",
            details={
                "from_checkpoint": 5,
                "to_checkpoint": 3,
                "tools_reversed": 2
            }
        )
        trail.add_event(event)
        
        assert len(trail.events) == 1
        assert trail.events[0].event_type == EventType.ROLLBACK
        assert trail.events[0].severity == EventSeverity.WARNING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


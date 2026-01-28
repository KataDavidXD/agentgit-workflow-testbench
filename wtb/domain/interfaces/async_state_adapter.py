
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator, TYPE_CHECKING

from wtb.domain.models.workflow import ExecutionState

if TYPE_CHECKING:
    from wtb.domain.models.workflow import CheckpointTrigger


class IAsyncStateAdapter(ABC):
    """
    Async State Adapter Interface.
  
    Provides async operations for:
    - Session management
    - Checkpoint operations
    - Execution control
    - Streaming support
  
    SOLID:
    - SRP: Only state management
    - OCP: New adapters via implementation
    - LSP: All implementations interchangeable
    - ISP: Focused interface (~15 methods)
    - DIP: Application depends on this abstraction
    """
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Session Management (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def ainitialize_session(
        self, 
        execution_id: str,
        initial_state: ExecutionState
    ) -> Optional[str]:
        """Initialize session asynchronously."""
        pass
  
    @abstractmethod
    async def aset_current_session(
        self, 
        session_id: str,
        execution_id: Optional[str] = None,
    ) -> bool:
        """Set current session asynchronously."""
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoint Operations (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def asave_checkpoint(
        self,
        state: ExecutionState,
        node_id: str,
        trigger: "CheckpointTrigger",
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save checkpoint asynchronously. Returns checkpoint_id."""
        pass
  
    @abstractmethod
    async def aload_checkpoint(self, checkpoint_id: str) -> ExecutionState:
        """Load checkpoint asynchronously."""
        pass
  
    @abstractmethod
    async def arollback(self, to_checkpoint_id: str) -> ExecutionState:
        """Rollback to checkpoint asynchronously."""
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # Execution (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def aexecute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute workflow asynchronously.
      
        This is the PRIMARY async execution method. Uses LangGraph's ainvoke().
        """
        pass
  
    @abstractmethod
    async def astream(
        self, 
        initial_state: Dict[str, Any],
        stream_mode: str = "updates"
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream execution events asynchronously.
      
        Yields state updates as they occur. Uses LangGraph's astream().
        """
        pass
  
    # ═══════════════════════════════════════════════════════════════════════════
    # State Operations (Async)
    # ═══════════════════════════════════════════════════════════════════════════
  
    @abstractmethod
    async def aupdate_state(
        self, 
        values: Dict[str, Any], 
        as_node: Optional[str] = None
    ) -> bool:
        """Update state asynchronously (human-in-the-loop)."""
        pass
  
    @abstractmethod
    async def aget_current_state(self) -> Dict[str, Any]:
        """Get current state asynchronously."""
        pass

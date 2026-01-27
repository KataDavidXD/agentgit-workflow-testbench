"""
Unified Graph Factory for WTB Presentation Demo.

Creates LangGraph StateGraph combining:
- RAG Pipeline (7 nodes with SEPARATE doc/query embedding)
- SQL Agent (1 wrapped node)

═══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE: SEPARATE INDEXING vs QUERY PHASES
═══════════════════════════════════════════════════════════════════════════════

PHASE 1: DOCUMENT INDEXING (One-time, cached)
─────────────────────────────────────────────────────────────────────────────
  load_docs → chunk_split → embed_docs → [INDEX CACHED]
  
  Documents are embedded ONCE and stored. This phase:
  - Runs when documents change
  - Results cached by content hash
  - Expensive but amortized across queries

PHASE 2: QUERY PROCESSING (Per-query)
─────────────────────────────────────────────────────────────────────────────
  embed_query → retrieve → grade → generate/sql
  
  Each query:
  - Embeds just the query (fast, single vector)
  - Searches against cached doc index
  - Routes to RAG generation or SQL agent

═══════════════════════════════════════════════════════════════════════════════
GRAPH STRUCTURE
═══════════════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    INDEXING PHASE (Cached)                               │
  │                                                                          │
  │  START ─► ┌─────────────┐   ┌──────────────┐   ┌──────────────┐        │
  │           │ rag_load_   │ ─►│rag_chunk_    │ ─►│rag_embed_    │        │
  │           │ docs        │   │split         │   │docs          │        │
  │           │             │   │              │   │              │        │
  │           │ venv: base  │   │ venv: base   │   │ venv: numpy  │        │
  │           │ ray: 1 cpu  │   │ ray: 1 cpu   │   │ ray: 2 cpu   │        │
  │           └─────────────┘   └──────────────┘   └──────┬───────┘        │
  │                                                        │                 │
  │                                                   [INDEX READY]         │
  │                                                        │                 │
  ├────────────────────────────────────────────────────────┼─────────────────┤
  │                    QUERY PHASE (Per Request)           │                 │
  │                                                        ▼                 │
  │                                                 ┌──────────────┐        │
  │                                                 │rag_embed_    │        │
  │                                                 │query         │        │
  │                                                 │              │        │
  │                                                 │ venv: numpy  │        │
  │                                                 │ ray: 1 cpu   │        │
  │                                                 └──────┬───────┘        │
  │                                                        │                 │
  │                                                        ▼                 │
  │                                                 ┌──────────────┐        │
  │   ← Variants: dense_v1, bm25_v1, hybrid_v1 ─►  │rag_retrieve  │        │
  │                                                 │              │        │
  │                                                 │ venv: faiss  │        │
  │                                                 │ ray: 2 cpu   │        │
  │                                                 └──────┬───────┘        │
  │                                                        │                 │
  │                                                        ▼                 │
  │                                                 ┌──────────────┐        │
  │                                                 │  rag_grade   │        │
  │                                                 │              │        │
  │                                                 │ venv: base   │        │
  │                                                 │ ray: 1 cpu   │        │
  │                                                 └──────┬───────┘        │
  │                                                        │                 │
  │                              ┌─────────────────────────┼─────────┐      │
  │                              │                         │         │      │
  │                          [rewrite]               [generate]   [sql]    │
  │                              │                         │         │      │
  │                              ▼                         ▼         ▼      │
  │                       ┌──────────────┐          ┌──────────┐ ┌───────┐ │
  │                       │rag_embed_    │          │rag_      │ │sql_   │ │
  │                       │query (loop)  │          │generate  │ │agent  │ │
  │                       └──────────────┘          │          │ │       │ │
  │                                                 │venv: base│ │venv:  │ │
  │                                                 │ray: 1cpu │ │sqlite │ │
  │                                                 └────┬─────┘ └───┬───┘ │
  │                                                      │           │      │
  │                                                      ▼           ▼      │
  │                                                    END         END      │
  └─────────────────────────────────────────────────────────────────────────┘

NODE CONFIGURATION SUMMARY:
═══════════════════════════════════════════════════════════════════════════════
  Node              │ Venv Packages              │ Ray CPU │ Ray Memory
  ──────────────────┼────────────────────────────┼─────────┼────────────
  rag_load_docs     │ openai, aiofiles           │ 1       │ 256MB
  rag_chunk_split   │ openai, tiktoken           │ 1       │ 256MB
  rag_embed_docs    │ openai, numpy, faiss-cpu   │ 2       │ 2048MB
  rag_embed_query   │ openai, numpy              │ 1       │ 512MB
  rag_retrieve      │ openai, numpy, faiss-cpu   │ 2       │ 1024MB
  rag_grade         │ openai                     │ 1       │ 512MB
  rag_generate      │ openai                     │ 1       │ 1024MB
  sql_agent         │ openai, sqlite-utils       │ 1       │ 512MB
═══════════════════════════════════════════════════════════════════════════════

Features:
- Separate doc indexing (cached) vs query processing (per-request)
- Conditional edges at rag_grade for routing decisions
- Rewrite loop with max 2 iterations
- Checkpointing at each node (when used with WTB)
- Node variants for A/B testing
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    MemorySaver = None

# Local imports
from .state_schemas import UnifiedState
from .rag_nodes import (
    # Indexing phase
    rag_load_docs,
    rag_chunk_split,
    rag_embed_docs,        # NEW: Document embedding (cached)
    rag_embed_docs_small,
    rag_embed_docs_large,
    # Query phase
    rag_embed_query,       # NEW: Query embedding (per request)
    rag_embed_query_small,
    rag_embed_query_large,
    rag_retrieve,
    rag_retrieve_dense_v1,
    rag_retrieve_bm25_v1,
    rag_retrieve_hybrid_v1,
    rag_grade,
    rag_generate,
    rag_generate_gpt4_v1,
    # Legacy
    rag_embed,  # For backward compatibility
)
from .sql_agent_node import sql_agent_node


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════

def create_unified_graph(
    checkpointer: Optional[Any] = None,
    embed_docs_variant: Optional[Callable] = None,
    embed_query_variant: Optional[Callable] = None,
    retrieve_variant: Optional[Callable] = None,
    generate_variant: Optional[Callable] = None,
) -> Any:
    """
    Create unified workflow graph combining RAG pipeline and SQL agent.
    
    This is the main graph factory for the WTB presentation demo.
    It creates a StateGraph with:
    - 7 RAG nodes (load, chunk, embed_docs, embed_query, retrieve, grade, generate)
    - 1 SQL agent node
    - Conditional routing at grade node
    - Rewrite loop for query refinement
    
    Architecture:
        INDEXING PHASE (cached): load_docs → chunk_split → embed_docs
        QUERY PHASE (per-req):   embed_query → retrieve → grade → generate
    
    Args:
        checkpointer: Optional LangGraph checkpointer for persistence
        embed_docs_variant: Document embedding variant (e.g., small/large)
        embed_query_variant: Query embedding variant
        retrieve_variant: Retrieval variant (dense/bm25/hybrid)
        generate_variant: Generation variant (gpt4/local)
        
    Returns:
        Compiled LangGraph ready for execution
        
    Usage:
        from graphs.unified_graph import create_unified_graph
        
        graph = create_unified_graph()
        result = graph.invoke({"query": "What is TechFlow's revenue?"})
        
    With WTB and variants:
        project = WorkflowProject(
            name="unified_demo",
            graph_factory=lambda: create_unified_graph(
                retrieve_variant=rag_retrieve_hybrid_v1
            ),
        )
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph not installed. Run: pip install langgraph")
    
    # Use provided variants or defaults
    embed_docs_fn = embed_docs_variant or rag_embed_docs
    embed_query_fn = embed_query_variant or rag_embed_query
    retrieve_fn = retrieve_variant or rag_retrieve
    generate_fn = generate_variant or rag_generate
    
    # Create StateGraph
    builder = StateGraph(UnifiedState)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INDEXING PHASE NODES (Document processing - cached)
    # ═══════════════════════════════════════════════════════════════════════════
    
    builder.add_node("rag_load_docs", rag_load_docs)
    builder.add_node("rag_chunk_split", rag_chunk_split)
    builder.add_node("rag_embed_docs", embed_docs_fn)  # NEW: Documents only
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY PHASE NODES (Per-request processing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    builder.add_node("rag_embed_query", embed_query_fn)  # NEW: Query only
    builder.add_node("rag_retrieve", retrieve_fn)
    builder.add_node("rag_grade", rag_grade)
    builder.add_node("rag_generate", generate_fn)
    
    # SQL Agent node
    builder.add_node("sql_agent", sql_agent_node)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Add Edges - INDEXING PHASE
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Indexing: start → load_docs → chunk_split → embed_docs
    builder.add_edge("__start__", "rag_load_docs")
    builder.add_edge("rag_load_docs", "rag_chunk_split")
    builder.add_edge("rag_chunk_split", "rag_embed_docs")  # Document embedding
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Add Edges - QUERY PHASE  
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Query: embed_docs → embed_query → retrieve → grade
    builder.add_edge("rag_embed_docs", "rag_embed_query")  # Query embedding
    builder.add_edge("rag_embed_query", "rag_retrieve")
    builder.add_edge("rag_retrieve", "rag_grade")
    
    # Conditional routing from grade node
    def route_after_grade(state: Dict[str, Any]) -> Literal["rag_generate", "rag_embed_query", "sql_agent"]:
        """
        Route based on grade decision:
        - "generate": Docs relevant, generate answer
        - "rewrite": Docs not relevant, rewrite query and re-embed
        - "sql": Query needs database access
        """
        decision = state.get("grade_decision", "generate")
        
        if decision == "sql":
            return "sql_agent"
        elif decision == "rewrite":
            return "rag_embed_query"  # Re-embed the rewritten query
        else:
            return "rag_generate"
    
    builder.add_conditional_edges(
        "rag_grade",
        route_after_grade,
        {
            "rag_generate": "rag_generate",
            "rag_embed_query": "rag_embed_query",  # Loop back with rewritten query
            "sql_agent": "sql_agent",
        }
    )
    
    # Terminal edges
    builder.add_edge("rag_generate", END)
    builder.add_edge("sql_agent", END)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Return Graph
    # ═══════════════════════════════════════════════════════════════════════════
    # ARCHITECTURAL FIX (2026-01-17):
    # Return UNCOMPILED StateGraph so that LangGraphStateAdapter can compile
    # with its own checkpointer. This ensures proper checkpoint persistence.
    # If checkpointer is explicitly passed (e.g., for standalone use), compile here.
    
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    else:
        # Return uncompiled graph - StateAdapter will compile with checkpointer
        return builder


def create_rag_only_graph(
    checkpointer: Optional[Any] = None,
    embed_docs_variant: Optional[Callable] = None,
    embed_query_variant: Optional[Callable] = None,
    retrieve_variant: Optional[Callable] = None,
    generate_variant: Optional[Callable] = None,
) -> Any:
    """
    Create RAG-only workflow graph (no SQL agent).
    
    Simplified graph for demonstrating RAG pipeline in isolation.
    No conditional routing to SQL - all queries go through RAG.
    
    Architecture:
        INDEXING: load → chunk → embed_docs (cached)
        QUERY:    embed_query → retrieve → grade → generate
    
    Args:
        checkpointer: Optional LangGraph checkpointer
        embed_docs_variant: Document embedding variant
        embed_query_variant: Query embedding variant
        retrieve_variant: Retrieval function variant
        generate_variant: Generation function variant
        
    Returns:
        Compiled LangGraph ready for execution
        
    Graph Structure:
        load → chunk → embed_docs → embed_query → retrieve → grade → generate → END
                                         ↑                      │
                                         └──────────────────────┘ (rewrite loop)
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph not installed. Run: pip install langgraph")
    
    # Use provided variants or defaults
    embed_docs_fn = embed_docs_variant or rag_embed_docs
    embed_query_fn = embed_query_variant or rag_embed_query
    retrieve_fn = retrieve_variant or rag_retrieve
    generate_fn = generate_variant or rag_generate
    
    builder = StateGraph(UnifiedState)
    
    # Add nodes - Indexing phase
    builder.add_node("rag_load_docs", rag_load_docs)
    builder.add_node("rag_chunk_split", rag_chunk_split)
    builder.add_node("rag_embed_docs", embed_docs_fn)
    
    # Add nodes - Query phase
    builder.add_node("rag_embed_query", embed_query_fn)
    builder.add_node("rag_retrieve", retrieve_fn)
    builder.add_node("rag_grade", rag_grade)
    builder.add_node("rag_generate", generate_fn)
    
    # Indexing edges
    builder.add_edge("__start__", "rag_load_docs")
    builder.add_edge("rag_load_docs", "rag_chunk_split")
    builder.add_edge("rag_chunk_split", "rag_embed_docs")
    
    # Query edges
    builder.add_edge("rag_embed_docs", "rag_embed_query")
    builder.add_edge("rag_embed_query", "rag_retrieve")
    builder.add_edge("rag_retrieve", "rag_grade")
    
    # Conditional edges (rewrite loop or generate)
    def route_after_grade_rag_only(state: Dict[str, Any]) -> Literal["rag_generate", "rag_embed_query"]:
        """Route based on grade decision (RAG only)."""
        decision = state.get("grade_decision", "generate")
        
        if decision == "rewrite":
            return "rag_embed_query"  # Re-embed rewritten query
        else:
            return "rag_generate"
    
    builder.add_conditional_edges(
        "rag_grade",
        route_after_grade_rag_only,
        {
            "rag_generate": "rag_generate",
            "rag_embed_query": "rag_embed_query",
        }
    )
    
    builder.add_edge("rag_generate", END)
    
    # ARCHITECTURAL FIX: Return uncompiled graph for StateAdapter to compile
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    else:
        return builder  # Uncompiled - StateAdapter will add checkpointer


def create_sql_only_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Create SQL-only workflow graph.
    
    Simple graph with just the SQL agent node.
    
    Args:
        checkpointer: Optional LangGraph checkpointer
        
    Returns:
        Compiled LangGraph ready for execution
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph not installed. Run: pip install langgraph")
    
    from .state_schemas import SQLState
    
    builder = StateGraph(SQLState)
    builder.add_node("sql_agent", sql_agent_node)
    builder.add_edge("__start__", "sql_agent")
    builder.add_edge("sql_agent", END)
    
    # ARCHITECTURAL FIX: Return uncompiled graph for StateAdapter to compile
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    else:
        return builder  # Uncompiled - StateAdapter will add checkpointer


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Factory with Variant Support
# ═══════════════════════════════════════════════════════════════════════════════

def create_graph_with_variants(
    embed_docs_variant: str = "default",
    embed_query_variant: str = "default",
    retrieve_variant: str = "default",
    generate_variant: str = "default",
    checkpointer: Optional[Any] = None,
) -> Any:
    """
    Create graph with specified node variants.
    
    This factory allows selecting specific variants by name,
    which is useful for batch testing and A/B experiments.
    
    Args:
        embed_docs_variant: "default", "small", or "large" (document embedding)
        embed_query_variant: "default", "small", or "large" (query embedding)
        retrieve_variant: "default", "dense", "bm25", or "hybrid"
        generate_variant: "default", "gpt4", or "local"
        checkpointer: Optional LangGraph checkpointer
        
    Returns:
        Compiled LangGraph with selected variants
        
    Example:
        # Test BM25 retrieval with local generation
        graph = create_graph_with_variants(
            retrieve_variant="bm25",
            generate_variant="local",
        )
    """
    from .rag_nodes import (
        rag_embed_docs, rag_embed_docs_small, rag_embed_docs_large,
        rag_embed_query, rag_embed_query_small, rag_embed_query_large,
        rag_retrieve, rag_retrieve_dense_v1, rag_retrieve_bm25_v1, rag_retrieve_hybrid_v1,
        rag_generate, rag_generate_gpt4_v1, rag_generate_local_v1,
    )
    
    # Map variant names to functions
    embed_docs_variants = {
        "default": rag_embed_docs,
        "small": rag_embed_docs_small,
        "large": rag_embed_docs_large,
    }
    
    embed_query_variants = {
        "default": rag_embed_query,
        "small": rag_embed_query_small,
        "large": rag_embed_query_large,
    }
    
    retrieve_variants = {
        "default": rag_retrieve,
        "dense": rag_retrieve_dense_v1,
        "bm25": rag_retrieve_bm25_v1,
        "hybrid": rag_retrieve_hybrid_v1,
    }
    
    generate_variants = {
        "default": rag_generate,
        "gpt4": rag_generate_gpt4_v1,
        "local": rag_generate_local_v1,
    }
    
    return create_unified_graph(
        checkpointer=checkpointer,
        embed_docs_variant=embed_docs_variants.get(embed_docs_variant, rag_embed_docs),
        embed_query_variant=embed_query_variants.get(embed_query_variant, rag_embed_query),
        retrieve_variant=retrieve_variants.get(retrieve_variant, rag_retrieve),
        generate_variant=generate_variants.get(generate_variant, rag_generate),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Visualization Helper
# ═══════════════════════════════════════════════════════════════════════════════

def get_graph_mermaid() -> str:
    """
    Get Mermaid diagram representation of the unified graph.
    
    Returns:
        Mermaid flowchart string for documentation/visualization
    """
    return """
flowchart TB
    subgraph RAG [RAG Pipeline]
        START((Start))
        LOAD[rag_load_docs]
        CHUNK[rag_chunk_split]
        EMBED[rag_embed]
        RETRIEVE[rag_retrieve]
        GRADE[rag_grade]
        GENERATE[rag_generate]
    end
    
    subgraph SQL [SQL Agent]
        SQLAGENT[sql_agent]
    end
    
    START --> LOAD
    LOAD --> CHUNK
    CHUNK --> EMBED
    EMBED --> RETRIEVE
    RETRIEVE --> GRADE
    
    GRADE -->|generate| GENERATE
    GRADE -->|rewrite| RETRIEVE
    GRADE -->|sql| SQLAGENT
    
    GENERATE --> END_NODE((End))
    SQLAGENT --> END_NODE
    
    style GRADE fill:#f9f,stroke:#333
    style EMBED fill:#bbf,stroke:#333
    style RETRIEVE fill:#bfb,stroke:#333
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "create_unified_graph",
    "create_rag_only_graph",
    "create_sql_only_graph",
    "create_graph_with_variants",
    "get_graph_mermaid",
]

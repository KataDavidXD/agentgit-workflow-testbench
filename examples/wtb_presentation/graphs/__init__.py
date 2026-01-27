"""
Graph definitions for WTB Presentation Demo.

Contains:
- state_schemas: TypedDict state definitions
- rag_nodes: 7 RAG pipeline nodes with variants (separate doc/query embedding)
- sql_agent_node: SQL Agent wrapped as single node
- unified_graph: Combined LangGraph factory
"""

from .state_schemas import RAGState, SQLState, UnifiedState
from .rag_nodes import (
    # Indexing phase nodes
    rag_load_docs,
    rag_chunk_split,
    rag_embed_docs,           # Document embedding (cached)
    rag_embed_docs_small,
    rag_embed_docs_large,
    # Query phase nodes
    rag_embed_query,          # Query embedding (per request)
    rag_embed_query_small,
    rag_embed_query_large,
    rag_retrieve,
    rag_grade,
    rag_generate,
    # Retrieve variants
    rag_retrieve_dense_v1,
    rag_retrieve_bm25_v1,
    rag_retrieve_hybrid_v1,
    # Generate variants
    rag_generate_gpt4_v1,
    rag_generate_local_v1,
    # Legacy (backward compatibility)
    rag_embed,
    rag_embed_minilm_v1,
    rag_embed_bge_v1,
)
from .sql_agent_node import sql_agent_node
from .unified_graph import (
    create_unified_graph,
    create_rag_only_graph,
    create_sql_only_graph,
)

__all__ = [
    # State schemas
    "RAGState",
    "SQLState", 
    "UnifiedState",
    # Indexing phase nodes
    "rag_load_docs",
    "rag_chunk_split",
    "rag_embed_docs",
    "rag_embed_docs_small",
    "rag_embed_docs_large",
    # Query phase nodes
    "rag_embed_query",
    "rag_embed_query_small",
    "rag_embed_query_large",
    "rag_retrieve",
    "rag_grade",
    "rag_generate",
    # Retrieve variants
    "rag_retrieve_dense_v1",
    "rag_retrieve_bm25_v1",
    "rag_retrieve_hybrid_v1",
    # Generate variants
    "rag_generate_gpt4_v1",
    "rag_generate_local_v1",
    # Legacy (backward compatibility)
    "rag_embed",
    "rag_embed_minilm_v1",
    "rag_embed_bge_v1",
    # SQL node
    "sql_agent_node",
    # Graph factories
    "create_unified_graph",
    "create_rag_only_graph",
    "create_sql_only_graph",
]

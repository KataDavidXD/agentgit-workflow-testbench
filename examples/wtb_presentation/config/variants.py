"""
Node Variant Definitions for WTB Presentation Demo.

Defines all available variants for each configurable node,
enabling A/B testing and batch variant comparisons.

Variant Types:
- Embed variants: minilm, bge
- Retrieve variants: dense, bm25, hybrid
- Generate variants: gpt4, local

Usage:
    from config.variants import register_all_variants, VARIANT_DEFINITIONS
    
    # Register all variants with WTB
    wtb = WTBTestBench.create(mode="development")
    register_all_variants(wtb, "my_project")
    
    # Or use variant matrix for batch testing
    batch_result = wtb.run_batch_test(
        project="my_project",
        variant_matrix=[
            {"rag_retrieve": "dense"},
            {"rag_retrieve": "bm25"},
            {"rag_retrieve": "hybrid"},
        ],
        test_cases=[...]
    )
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, TYPE_CHECKING

# Import variant implementations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from examples.wtb_presentation.graphs.rag_nodes import (
    # Embed variants
    rag_embed_minilm_v1,
    rag_embed_bge_v1,
    # Retrieve variants
    rag_retrieve_dense_v1,
    rag_retrieve_bm25_v1,
    rag_retrieve_hybrid_v1,
    # Generate variants
    rag_generate_gpt4_v1,
    rag_generate_local_v1,
)

if TYPE_CHECKING:
    from wtb.sdk import WTBTestBench


# ═══════════════════════════════════════════════════════════════════════════════
# Variant Definitions
# ═══════════════════════════════════════════════════════════════════════════════

VARIANT_DEFINITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    # Embedding variants
    "rag_embed": {
        "minilm": {
            "implementation": rag_embed_minilm_v1,
            "description": "MiniLM-L6 embedding model (384 dimensions, fast)",
            "characteristics": {
                "dimensions": 384,
                "speed": "fast",
                "quality": "good",
            },
        },
        "bge": {
            "implementation": rag_embed_bge_v1,
            "description": "BGE embedding model (768 dimensions, high quality)",
            "characteristics": {
                "dimensions": 768,
                "speed": "medium",
                "quality": "excellent",
            },
        },
    },
    
    # Retrieval variants
    "rag_retrieve": {
        "dense": {
            "implementation": rag_retrieve_dense_v1,
            "description": "Dense vector retrieval using embeddings",
            "characteristics": {
                "type": "semantic",
                "speed": "fast",
                "recall": "high",
            },
        },
        "bm25": {
            "implementation": rag_retrieve_bm25_v1,
            "description": "BM25 sparse keyword-based retrieval",
            "characteristics": {
                "type": "lexical",
                "speed": "very_fast",
                "recall": "medium",
            },
        },
        "hybrid": {
            "implementation": rag_retrieve_hybrid_v1,
            "description": "Hybrid retrieval combining dense and BM25",
            "characteristics": {
                "type": "hybrid",
                "speed": "medium",
                "recall": "highest",
            },
        },
    },
    
    # Generation variants
    "rag_generate": {
        "gpt4": {
            "implementation": rag_generate_gpt4_v1,
            "description": "GPT-4 style generation (simulated)",
            "characteristics": {
                "model": "gpt-4",
                "quality": "excellent",
                "cost": "high",
            },
        },
        "local": {
            "implementation": rag_generate_local_v1,
            "description": "Local LLM generation (simulated)",
            "characteristics": {
                "model": "local",
                "quality": "good",
                "cost": "low",
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Variant Matrix Definitions
# ═══════════════════════════════════════════════════════════════════════════════

# Predefined variant matrices for common testing scenarios

# Test all retrieval strategies
RETRIEVAL_VARIANT_MATRIX: List[Dict[str, str]] = [
    {"rag_retrieve": "dense"},
    {"rag_retrieve": "bm25"},
    {"rag_retrieve": "hybrid"},
]

# Test embedding models
EMBEDDING_VARIANT_MATRIX: List[Dict[str, str]] = [
    {"rag_embed": "minilm"},
    {"rag_embed": "bge"},
]

# Test generation models
GENERATION_VARIANT_MATRIX: List[Dict[str, str]] = [
    {"rag_generate": "gpt4"},
    {"rag_generate": "local"},
]

# Full cross-product: retrieval x generation
FULL_VARIANT_MATRIX: List[Dict[str, str]] = [
    {"rag_retrieve": "dense", "rag_generate": "gpt4"},
    {"rag_retrieve": "dense", "rag_generate": "local"},
    {"rag_retrieve": "bm25", "rag_generate": "gpt4"},
    {"rag_retrieve": "bm25", "rag_generate": "local"},
    {"rag_retrieve": "hybrid", "rag_generate": "gpt4"},
    {"rag_retrieve": "hybrid", "rag_generate": "local"},
]

# Cost-optimized matrix (fast/cheap options)
COST_OPTIMIZED_MATRIX: List[Dict[str, str]] = [
    {"rag_embed": "minilm", "rag_retrieve": "bm25", "rag_generate": "local"},
]

# Quality-optimized matrix (best options)
QUALITY_OPTIMIZED_MATRIX: List[Dict[str, str]] = [
    {"rag_embed": "bge", "rag_retrieve": "hybrid", "rag_generate": "gpt4"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def register_all_variants(wtb: "WTBTestBench", project_name: str) -> None:
    """
    Register all defined variants with a WTBTestBench instance.
    
    Args:
        wtb: WTBTestBench instance
        project_name: Name of the project to register variants for
    """
    for node_id, variants in VARIANT_DEFINITIONS.items():
        for variant_name, variant_info in variants.items():
            wtb.register_variant(
                project=project_name,
                node=node_id,
                name=variant_name,
                implementation=variant_info["implementation"],
                description=variant_info["description"],
            )


def get_variant_implementation(node_id: str, variant_name: str) -> Callable:
    """
    Get the implementation function for a specific variant.
    
    Args:
        node_id: The node identifier
        variant_name: The variant name
        
    Returns:
        The variant implementation callable
        
    Raises:
        KeyError: If node or variant not found
    """
    return VARIANT_DEFINITIONS[node_id][variant_name]["implementation"]


def get_variant_info(node_id: str, variant_name: str) -> Dict[str, Any]:
    """
    Get full information about a variant.
    
    Args:
        node_id: The node identifier
        variant_name: The variant name
        
    Returns:
        Dictionary with implementation, description, and characteristics
    """
    return VARIANT_DEFINITIONS[node_id][variant_name]


def list_variants(node_id: str = None) -> Dict[str, List[str]]:
    """
    List available variants.
    
    Args:
        node_id: Optional node ID to filter by
        
    Returns:
        Dictionary mapping node IDs to list of variant names
    """
    if node_id:
        if node_id in VARIANT_DEFINITIONS:
            return {node_id: list(VARIANT_DEFINITIONS[node_id].keys())}
        return {}
    
    return {node: list(variants.keys()) for node, variants in VARIANT_DEFINITIONS.items()}


def create_variant_matrix(
    embed: List[str] = None,
    retrieve: List[str] = None,
    generate: List[str] = None,
) -> List[Dict[str, str]]:
    """
    Create a custom variant matrix from specified options.
    
    Args:
        embed: List of embed variants to include (None = skip)
        retrieve: List of retrieve variants to include (None = skip)
        generate: List of generate variants to include (None = skip)
        
    Returns:
        List of variant configurations for batch testing
        
    Example:
        matrix = create_variant_matrix(
            retrieve=["dense", "hybrid"],
            generate=["gpt4"],
        )
        # Returns:
        # [
        #     {"rag_retrieve": "dense", "rag_generate": "gpt4"},
        #     {"rag_retrieve": "hybrid", "rag_generate": "gpt4"},
        # ]
    """
    from itertools import product
    
    # Build lists of (key, value) pairs
    options = []
    
    if embed:
        options.append([("rag_embed", v) for v in embed])
    if retrieve:
        options.append([("rag_retrieve", v) for v in retrieve])
    if generate:
        options.append([("rag_generate", v) for v in generate])
    
    if not options:
        return [{}]
    
    # Generate cross product
    matrix = []
    for combo in product(*options):
        matrix.append(dict(combo))
    
    return matrix


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "VARIANT_DEFINITIONS",
    "register_all_variants",
    "get_variant_implementation",
    "get_variant_info",
    "list_variants",
    "create_variant_matrix",
    # Predefined matrices
    "RETRIEVAL_VARIANT_MATRIX",
    "EMBEDDING_VARIANT_MATRIX",
    "GENERATION_VARIANT_MATRIX",
    "FULL_VARIANT_MATRIX",
    "COST_OPTIMIZED_MATRIX",
    "QUALITY_OPTIMIZED_MATRIX",
]

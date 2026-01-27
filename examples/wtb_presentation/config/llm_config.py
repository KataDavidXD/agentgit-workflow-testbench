"""
LLM Configuration for WTB Presentation Demo.

Configures OpenAI-compatible API for:
- Text generation (gpt-4o-mini, gpt-4o)
- Embeddings (text-embedding-3-small, text-embedding-3-large)

Uses environment variables from .env file.

Usage:
    from config.llm_config import get_llm_client, get_embedding_client
    
    # Get configured clients
    llm = get_llm_client()
    embeddings = get_embedding_client()
    
    # Generate text
    response = llm.chat.completions.create(
        model=DEFAULT_LLM,
        messages=[{"role": "user", "content": "Hello"}]
    )
    
    # Generate embeddings
    response = embeddings.embeddings.create(
        model=EMBEDDING_MODEL,
        input=["text to embed"]
    )
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load from presentation directory .env
    ENV_PATH = Path(__file__).parent.parent / ".env"
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    # Also try env.local
    ENV_LOCAL_PATH = Path(__file__).parent.parent / "env.local"
    if ENV_LOCAL_PATH.exists():
        load_dotenv(ENV_LOCAL_PATH)
except ImportError:
    pass  # dotenv not installed, rely on system env vars

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Constants
# ═══════════════════════════════════════════════════════════════════════════════

# LLM Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_LLM = os.getenv("DEFAULT_LLM", "gpt-4o-mini")
ALT_LLM = os.getenv("ALT_LLM", "gpt-4o")

# Embedding Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
ALT_EMBEDDING_MODEL = os.getenv("ALT_EMBEDDING_MODEL", "text-embedding-3-large")

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


# ═══════════════════════════════════════════════════════════════════════════════
# Client Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm_client():
    """
    Get configured OpenAI client for LLM operations.
    
    Returns:
        OpenAI client configured with base URL and API key
        
    Raises:
        ValueError: If API key is not configured
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")
    
    if not LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY not configured. "
            "Create a .env file in examples/wtb_presentation/ with your API key."
        )
    
    return OpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )


def get_embedding_client():
    """
    Get configured OpenAI client for embedding operations.
    
    Uses the same client as LLM but may use different models.
    
    Returns:
        OpenAI client configured for embeddings
    """
    return get_llm_client()


# ═══════════════════════════════════════════════════════════════════════════════
# High-Level API Functions
# ═══════════════════════════════════════════════════════════════════════════════

def generate_text(
    prompt: str,
    model: str = None,
    system_prompt: str = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """
    Generate text using the configured LLM.
    
    Args:
        prompt: User prompt
        model: Model to use (default: DEFAULT_LLM)
        system_prompt: Optional system prompt
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        Generated text response
    """
    client = get_llm_client()
    model = model or DEFAULT_LLM
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    if DEBUG:
        print(f"[LLM] Generating with {model}: {prompt[:50]}...")
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return response.choices[0].message.content


def generate_embeddings(
    texts: List[str],
    model: str = None,
) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.
    
    Args:
        texts: List of texts to embed
        model: Embedding model to use (default: EMBEDDING_MODEL)
        
    Returns:
        List of embedding vectors
    """
    client = get_embedding_client()
    model = model or EMBEDDING_MODEL
    
    if DEBUG:
        print(f"[Embedding] Generating {len(texts)} embeddings with {model}")
    
    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    
    return [item.embedding for item in response.data]


def grade_document_relevance(
    query: str,
    document: str,
    model: str = None,
) -> Dict[str, Any]:
    """
    Grade a document's relevance to a query using LLM.
    
    Args:
        query: The user query
        document: Document content to grade
        model: Model to use for grading
        
    Returns:
        Dict with is_relevant (bool) and reason (str)
    """
    model = model or DEFAULT_LLM
    
    system_prompt = """You are a relevance grading assistant. 
    Given a query and a document, determine if the document is relevant to answering the query.
    Respond with JSON: {"is_relevant": true/false, "reason": "brief explanation"}
    Be strict - only mark as relevant if the document directly helps answer the query."""
    
    prompt = f"""Query: {query}

Document:
{document[:1000]}

Is this document relevant to the query? Respond with JSON only."""
    
    response = generate_text(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=100,
    )
    
    # Parse response
    import json
    try:
        # Try to extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    
    # Fallback
    is_relevant = "true" in response.lower() or "relevant" in response.lower()
    return {"is_relevant": is_relevant, "reason": response[:100]}


def generate_answer(
    query: str,
    context: str,
    model: str = None,
) -> str:
    """
    Generate an answer using RAG context.
    
    Args:
        query: The user query
        context: Retrieved context documents
        model: Model to use for generation
        
    Returns:
        Generated answer
    """
    model = model or DEFAULT_LLM
    
    system_prompt = """You are a helpful assistant that answers questions based on provided context.
    Use the context to provide accurate, detailed answers.
    If the context doesn't contain relevant information, say so.
    Always cite specific facts from the context when possible."""
    
    prompt = f"""Context:
{context}

Question: {query}

Please provide a detailed answer based on the context above."""
    
    return generate_text(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=1024,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Model Variants for A/B Testing
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelVariant:
    """Configuration for a model variant."""
    name: str
    model_id: str
    description: str
    temperature: float = 0.7
    max_tokens: int = 1024


# Generation model variants
GENERATION_VARIANTS = {
    "gpt4o_mini": ModelVariant(
        name="gpt4o_mini",
        model_id=DEFAULT_LLM,
        description="GPT-4o-mini - Fast and cost-effective",
        temperature=0.7,
    ),
    "gpt4o": ModelVariant(
        name="gpt4o",
        model_id=ALT_LLM,
        description="GPT-4o - Higher quality, more expensive",
        temperature=0.5,
    ),
}

# Embedding model variants
EMBEDDING_VARIANTS = {
    "small": ModelVariant(
        name="small",
        model_id=EMBEDDING_MODEL,
        description="text-embedding-3-small - Fast, good quality",
    ),
    "large": ModelVariant(
        name="large",
        model_id=ALT_EMBEDDING_MODEL,
        description="text-embedding-3-large - Best quality",
    ),
}


def get_model_variant(variant_type: str, variant_name: str) -> ModelVariant:
    """
    Get a model variant by type and name.
    
    Args:
        variant_type: "generation" or "embedding"
        variant_name: Variant name
        
    Returns:
        ModelVariant configuration
    """
    variants = GENERATION_VARIANTS if variant_type == "generation" else EMBEDDING_VARIANTS
    return variants.get(variant_name, list(variants.values())[0])


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def check_api_connection() -> bool:
    """
    Check if the API connection is working.
    
    Returns:
        True if connection is successful
    """
    try:
        client = get_llm_client()
        # Simple test call
        response = client.chat.completions.create(
            model=DEFAULT_LLM,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5,
        )
        return True
    except Exception as e:
        print(f"[LLM] Connection check failed: {e}")
        return False


def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of current LLM configuration.
    
    Returns:
        Dictionary with configuration details
    """
    return {
        "base_url": LLM_BASE_URL,
        "api_key_configured": bool(LLM_API_KEY),
        "default_llm": DEFAULT_LLM,
        "alt_llm": ALT_LLM,
        "embedding_model": EMBEDDING_MODEL,
        "alt_embedding_model": ALT_EMBEDDING_MODEL,
        "debug": DEBUG,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Configuration
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "DEFAULT_LLM",
    "ALT_LLM",
    "EMBEDDING_MODEL",
    "ALT_EMBEDDING_MODEL",
    # Client factories
    "get_llm_client",
    "get_embedding_client",
    # High-level API
    "generate_text",
    "generate_embeddings",
    "grade_document_relevance",
    "generate_answer",
    # Variants
    "ModelVariant",
    "GENERATION_VARIANTS",
    "EMBEDDING_VARIANTS",
    "get_model_variant",
    # Utilities
    "check_api_connection",
    "get_config_summary",
]

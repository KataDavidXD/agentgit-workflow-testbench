"""Configuration loader for LangExtract demo."""
import os
from pathlib import Path

def load_env_file(env_file: str = ".env") -> None:
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent / env_file
    if not env_path.exists():
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Only set if not already in environment
                if key and not os.getenv(key):
                    os.environ[key] = value

def get_config() -> dict:
    """Get configuration from environment variables.
    
    Supported models (from LangExtract built-in provider patterns):
    - OpenAI: gpt-4, gpt-4-turbo, gpt-4-32k, etc. (pattern: ^gpt-4)
    - Gemini: gemini-pro, gemini-1.5-flash, etc. (pattern: ^gemini)
    - Local/Other: llama, mistral, ollama models (patterns: ^llama, ^mistral, etc.)
    """
    # Try to load from .env file
    load_env_file()
    
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("DEFAULT_LLM", "gpt-4-turbo")
    
    if not api_key:
        raise ValueError(
            "LLM_API_KEY not found. Please:\n"
            "1. Copy .env.example to .env\n"
            "2. Fill in your API key\n"
            "Or set environment variable: $env:LLM_API_KEY='your-key'"
        )
    
    config = {
        "api_key": api_key,
        "model": model,
    }
    
    # Only add base_url if it's set
    # OpenAI provider expects 'base_url' parameter for custom endpoints
    if base_url:
        config["base_url"] = base_url
    
    return config


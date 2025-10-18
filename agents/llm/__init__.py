"""
LLM Client abstraction layer for SquadOps agents.

Provides a protocol-based interface for different LLM providers (Ollama, OpenAI, etc.)
with routing, validation, and testing capabilities.
"""

from .client import LLMClient
from .router import LLMRouter
from .validators import validate_html, validate_css, validate_js, parse_delimited_files

__all__ = [
    'LLMClient',
    'LLMRouter', 
    'validate_html',
    'validate_css',
    'validate_js',
    'parse_delimited_files'
]



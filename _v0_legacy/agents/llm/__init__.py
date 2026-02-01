"""
LLM Client abstraction layer for SquadOps agents.

DEPRECATED: This module is deprecated as of SIP-0.8.7.
Use squadops.llm, squadops.ports.llm, and adapters.llm instead.

Provides a protocol-based interface for different LLM providers (Ollama, OpenAI, etc.)
with routing, validation, and testing capabilities.
"""
import warnings

warnings.warn(
    "Importing from _v0_legacy.agents.llm is deprecated. "
    "Use squadops.llm, squadops.ports.llm, and adapters.llm instead. "
    "This module will be removed in version 0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy exports (preserved for backwards compatibility)
from .client import LLMClient
from .router import LLMRouter
from .validators import parse_delimited_files, validate_css, validate_html, validate_js

# Re-export new canonical symbols for migration convenience
from adapters.llm.factory import create_llm_provider
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse

__all__ = [
    # Legacy (deprecated)
    'LLMClient',
    'LLMRouter',
    'validate_html',
    'validate_css',
    'validate_js',
    'parse_delimited_files',
    # New (canonical)
    'create_llm_provider',
    'ChatMessage',
    'LLMRequest',
    'LLMResponse',
]





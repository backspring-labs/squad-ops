"""LLM adapters.

Provides implementations of LLM ports:
- OllamaAdapter: Local Ollama LLM server adapter

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from adapters.llm.factory import create_llm_provider
from adapters.llm.ollama import OllamaAdapter

__all__ = [
    "OllamaAdapter",
    "create_llm_provider",
]

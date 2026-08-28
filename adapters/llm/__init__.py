"""LLM adapters.

Provides implementations of LLM ports:
- OllamaAdapter: Local Ollama LLM server adapter
- VLLMAdapter: vLLM OpenAI-compatible server adapter
- AtlasAdapter: Atlas (DGX Spark inference engine) adapter, SIP-0106

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from adapters.llm.atlas import AtlasAdapter
from adapters.llm.factory import create_llm_provider
from adapters.llm.ollama import OllamaAdapter
from adapters.llm.vllm import VLLMAdapter

__all__ = [
    "AtlasAdapter",
    "OllamaAdapter",
    "VLLMAdapter",
    "create_llm_provider",
]

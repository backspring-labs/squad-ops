"""
LLM provider implementations for SquadOps agents.

Providers implement the LLMClient protocol and can be registered with LLMRouter.
Future providers (e.g., DockerModelClient) can be added here.
"""

from .ollama import OllamaClient

__all__ = ['OllamaClient']

# Future providers can be added here:
# from .docker_model import DockerModelClient
# __all__.append('DockerModelClient')





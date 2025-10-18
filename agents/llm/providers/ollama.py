"""
Ollama LLM provider adapter for SquadOps agents.

Implements the LLMClient protocol for local Ollama instances.
"""

import aiohttp
import os
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama LLM provider adapter"""
    
    def __init__(self, url: str = None, model: str = None, timeout: int = 60):
        self.url = url or os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434')
        self.model = model or os.getenv('AGENT_MODEL', 'qwen2.5:7b')
        self.timeout = timeout
    
    async def complete(self, prompt: str, temperature: float = 0.7, 
                      max_tokens: int = 4000, **kwargs) -> str:
        """Generate completion via Ollama API"""
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': temperature,
                'num_predict': max_tokens,
                **kwargs
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.url}/api/generate', 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('response', '')
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")
    
    async def chat(self, messages: List[Dict[str, str]], 
                   temperature: float = 0.7, max_tokens: int = 4000, 
                   **kwargs) -> str:
        """Generate chat completion via Ollama API"""
        payload = {
            'model': self.model,
            'messages': messages,
            'stream': False,
            'options': {
                'temperature': temperature,
                'num_predict': max_tokens,
                **kwargs
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.url}/api/chat',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('message', {}).get('content', '')
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama chat API error {response.status}: {error_text}")



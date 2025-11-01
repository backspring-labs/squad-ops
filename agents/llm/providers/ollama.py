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
        # Use unified config if url/model not provided
        if url is None or model is None:
            try:
                from config.unified_config import get_config
                config = get_config()
                llm_config = config.get_llm_config()
                self.url = url or llm_config.get('url') if llm_config else None
                self.model = model or llm_config.get('model') if llm_config else None
            except Exception as e:
                logger.warning(f"Failed to load unified config in OllamaClient, using fallbacks: {e}")
                self.url = None
                self.model = None
        else:
            self.url = url
            self.model = model
        
        # Fallback to env vars if still not set
        if not self.url:
            env_url = os.getenv('OLLAMA_URL')
            if env_url:
                self.url = env_url
            else:
                logger.info("Using default Ollama URL: http://host.docker.internal:11434 (set OLLAMA_URL to override)")
                self.url = 'http://host.docker.internal:11434'
        
        if not self.model:
            env_model = os.getenv('AGENT_MODEL')
            if env_model:
                self.model = env_model
            else:
                logger.warning(
                    "⚠️  Using hardcoded default model 'qwen2.5:7b' - ensure this model is available. "
                    "Set AGENT_MODEL environment variable to override. "
                    "If this model doesn't exist, LLM calls will fail."
                )
                self.model = 'qwen2.5:7b'
        
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





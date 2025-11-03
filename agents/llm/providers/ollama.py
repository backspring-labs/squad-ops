"""
Ollama LLM provider adapter for SquadOps agents.

Implements the LLMClient protocol for local Ollama instances.
"""

import aiohttp
import asyncio
import os
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama LLM provider adapter"""
    
    def __init__(self, url: str = None, model: str = None, timeout: int = 180):
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
        # Track token usage from last call (Task 1.3)
        self._last_token_usage: Dict[str, int] = None
    
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.url}/api/generate', 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Extract token usage from Ollama response (Task 1.3)
                        # Ollama returns: prompt_eval_count, eval_count
                        prompt_tokens = result.get('prompt_eval_count', 0)
                        completion_tokens = result.get('eval_count', 0)
                        total_tokens = prompt_tokens + completion_tokens
                        
                        # Store token usage for get_token_usage() method
                        self._last_token_usage = {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': total_tokens
                        }
                        
                        response_text = result.get('response', '')
                        if not response_text:
                            raise Exception(f"Ollama API returned empty response")
                        return response_text
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text[:500] if error_text else 'No error details'}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Ollama: {type(e).__name__}: {str(e)}")
        except asyncio.TimeoutError as e:
            raise Exception(f"Ollama API timeout after {self.timeout}s: {str(e)}")
        except Exception as e:
            # Re-raise if it's already a formatted Exception
            if isinstance(e, Exception) and len(str(e)) > 0:
                raise
            raise Exception(f"Unexpected error calling Ollama: {type(e).__name__}: {str(e)}")
    
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.url}/api/chat',
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Extract token usage from Ollama chat response (Task 1.3)
                        # Ollama chat returns: prompt_eval_count, eval_count
                        prompt_tokens = result.get('prompt_eval_count', 0)
                        completion_tokens = result.get('eval_count', 0)
                        total_tokens = prompt_tokens + completion_tokens
                        
                        # Store token usage for get_token_usage() method
                        self._last_token_usage = {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': total_tokens
                        }
                        
                        content = result.get('message', {}).get('content', '')
                        if not content:
                            raise Exception(f"Ollama chat API returned empty content")
                        return content
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama chat API error {response.status}: {error_text[:500] if error_text else 'No error details'}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Ollama chat: {type(e).__name__}: {str(e)}")
        except asyncio.TimeoutError as e:
            raise Exception(f"Ollama chat API timeout after {self.timeout}s: {str(e)}")
        except Exception as e:
            # Re-raise if it's already a formatted Exception
            if isinstance(e, Exception) and len(str(e)) > 0:
                raise
            raise Exception(f"Unexpected error calling Ollama chat: {type(e).__name__}: {str(e)}")
    
    def get_token_usage(self) -> Dict[str, int]:
        """
        Get token usage from the last LLM call (Task 1.3)
        
        Returns:
            Dict with keys: 'prompt_tokens', 'completion_tokens', 'total_tokens'
            Returns None if no token usage is available
        """
        return self._last_token_usage





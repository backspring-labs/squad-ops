"""
Ollama LLM provider adapter for SquadOps agents.

Implements the LLMClient protocol for local Ollama instances.
"""

import logging
import os

import aiohttp

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama LLM provider adapter"""
    
    def __init__(self, url: str = None, model: str = None, timeout: int = 180):
        # Use unified config if url/model not provided
        if url is None or model is None:
            try:
                import os
                from infra.config.loader import load_config
                strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
                config = load_config(strict=strict_mode)
                llm_config = {"url": config.llm.url, "model": config.llm.model, "timeout": config.llm.timeout}
                self.url = url or llm_config.get('url') if llm_config else None
                self.model = model or llm_config.get('model') if llm_config else None
            except Exception as e:
                logger.warning(f"Failed to load unified config in OllamaClient, using fallbacks: {e}")
                self.url = None
                self.model = None
        else:
            self.url = url
            self.model = model
        
        # Fallback to default if still not set
        if not self.url:
            logger.info("Using default Ollama URL: http://host.docker.internal:11434")
            self.url = 'http://host.docker.internal:11434'
        
        if not self.model:
            # Fail fast with informative error - no hardcoded fallback
            raise ValueError(
                "❌ LLM model not configured!\n\n"
                "💡 To fix:\n"
                "  1. Configure model in agent's config.yaml:\n"
                "     defaults:\n"
                "       model: ollama:<model-name>\n"
                "  2. Example: defaults.model: ollama:llama3.1:8b\n"
                "  3. Ensure the model is available in Ollama: ollama list\n"
                "  4. If model doesn't exist, pull it: ollama pull <model-name>\n\n"
                "📖 See agents/roles/<role>/config.yaml for examples"
            )
        
        self.timeout = timeout
        # Track token usage from last call (Task 1.3)
        self._last_token_usage: dict[str, int] = None
    
    async def complete(self, prompt: str, temperature: float = 0.7, 
                      max_tokens: int = 4000, **kwargs) -> str:
        """Generate completion via Ollama API
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional options including:
                - format: Response format (e.g., 'json' for JSON format)
                - top_p: Top-p sampling
                - Other Ollama-specific options
        """
        # Extract format from kwargs if present (for JSON format support)
        response_format = kwargs.pop('format', None)
        
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
        
        # Add format at top level if specified (Ollama API requirement)
        if response_format:
            payload['format'] = response_format
        
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
                            raise Exception("Ollama API returned empty response")
                        return response_text
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text[:500] if error_text else 'No error details'}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Ollama: {type(e).__name__}: {str(e)}") from e
        except TimeoutError as e:
            raise Exception(f"Ollama API timeout after {self.timeout}s: {str(e)}") from e
        except Exception as e:
            # Re-raise if it's already a formatted Exception
            if isinstance(e, Exception) and len(str(e)) > 0:
                raise
            raise Exception(f"Unexpected error calling Ollama: {type(e).__name__}: {str(e)}") from e
    
    async def chat(self, messages: list[dict[str, str]], 
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
                            raise Exception("Ollama chat API returned empty content")
                        return content
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama chat API error {response.status}: {error_text[:500] if error_text else 'No error details'}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Ollama chat: {type(e).__name__}: {str(e)}") from e
        except TimeoutError as e:
            raise Exception(f"Ollama chat API timeout after {self.timeout}s: {str(e)}") from e
        except Exception as e:
            # Re-raise if it's already a formatted Exception
            if isinstance(e, Exception) and len(str(e)) > 0:
                raise
            raise Exception(f"Unexpected error calling Ollama chat: {type(e).__name__}: {str(e)}") from e
    
    def get_token_usage(self) -> dict[str, int]:
        """
        Get token usage from the last LLM call (Task 1.3)
        
        Returns:
            Dict with keys: 'prompt_tokens', 'completion_tokens', 'total_tokens'
            Returns None if no token usage is available
        """
        return self._last_token_usage





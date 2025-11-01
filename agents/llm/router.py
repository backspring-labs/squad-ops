"""
LLM router for selecting and configuring LLM providers.

Routes LLM requests to the appropriate provider based on configuration.
"""

import yaml
import os
from pathlib import Path
from agents.llm.client import LLMClient
from agents.llm.providers.ollama import OllamaClient


class LLMRouter:
    """Route LLM requests to configured provider"""
    
    def __init__(self, config: dict):
        self.config = config
        self.default_provider = config.get('default_provider', 'ollama')
    
    @classmethod
    def from_config(cls, config_path: str = 'config/llm_config.yaml'):
        """Load router from config file"""
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                config = yaml.safe_load(f)
                # Expand environment variables in config
                config = cls._expand_env_vars(config)
        else:
            # Default config if file doesn't exist - use unified config with fallbacks
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                from config.unified_config import get_config
                unified_config = get_config()
                llm_config = unified_config.get_llm_config()
                # Fallbacks in .get() handle missing keys; these are ultimate fallbacks if config fails
                default_url = llm_config.get('url') if llm_config else None
                default_model = llm_config.get('model') if llm_config else None
                default_timeout = llm_config.get('timeout') if llm_config else None
            except Exception as e:
                # If unified config fails entirely, fall back to environment vars and hardcoded defaults
                logger.warning(f"Failed to load unified config, using fallbacks: {e}")
                default_url = None
                default_model = None
                default_timeout = None
            
            # Build config with clear logging for fallback usage
            final_url = default_url or os.getenv('OLLAMA_URL')
            final_model = default_model or os.getenv('AGENT_MODEL')
            final_timeout = default_timeout
            
            # Log warnings for hardcoded fallbacks, especially model name
            if not final_url:
                logger.info("Using default Ollama URL: http://host.docker.internal:11434 (set OLLAMA_URL to override)")
                final_url = 'http://host.docker.internal:11434'
            
            if not final_model:
                logger.warning(
                    "⚠️  Using hardcoded default model 'qwen2.5:7b' - ensure this model is available. "
                    "Set AGENT_MODEL environment variable to override. "
                    "If this model doesn't exist, LLM calls will fail."
                )
                final_model = 'qwen2.5:7b'
            
            if not final_timeout:
                logger.debug("Using default timeout: 60 seconds (set LLM_TIMEOUT to override)")
                final_timeout = 60
            
            config = {
                'default_provider': 'ollama',
                'providers': {
                    'ollama': {
                        'url': final_url,
                        'model': final_model,
                        'timeout': final_timeout
                    }
                }
            }
        return cls(config)
    
    @classmethod
    def _expand_env_vars(cls, config):
        """Recursively expand environment variables in config"""
        if isinstance(config, dict):
            return {k: cls._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [cls._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Handle ${VAR:-default} syntax
            import re
            def replace_env_var(match):
                var_expr = match.group(1)
                if ':-' in var_expr:
                    var_name, default = var_expr.split(':-', 1)
                    return os.getenv(var_name, default)
                else:
                    return os.getenv(var_expr, '')
            
            return re.sub(r'\$\{([^}]+)\}', replace_env_var, config)
        else:
            return config
    
    def get_default_client(self) -> LLMClient:
        """Get default LLM client"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Check if local LLM is disabled - use unified config with fallback
        try:
            from config.unified_config import get_config
            config = get_config()
            use_local_llm = config.get_use_local_llm()
        except Exception as e:
            # Fallback to environment variable if unified config fails
            logger.warning(f"Failed to load unified config for USE_LOCAL_LLM, using environment variable: {e}")
            use_local_llm = os.getenv('USE_LOCAL_LLM', 'true').lower() == 'true'
            if use_local_llm:
                logger.info("Using default: USE_LOCAL_LLM=true (set USE_LOCAL_LLM=false to disable local LLM)")
        
        if not use_local_llm:
            # Return a mock client when local LLM is disabled
            from unittest.mock import MagicMock
            mock_client = MagicMock()
            mock_client.complete = MagicMock(return_value="[MOCK CODE RESPONSE] Test prompt for code generation")
            mock_client.chat = MagicMock(return_value="[MOCK CHAT RESPONSE] Test prompt")
            return mock_client
        
        provider_name = self.default_provider
        provider_config = self.config['providers'].get(provider_name, {})
        
        if provider_name == 'ollama':
            return OllamaClient(**provider_config)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

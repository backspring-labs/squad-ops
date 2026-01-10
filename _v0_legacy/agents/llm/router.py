"""
LLM router for selecting and configuring LLM providers.

Routes LLM requests to the appropriate provider based on configuration.
Supports dynamic provider registration for extensibility (Ollama, Docker models, etc.)
"""

import importlib
import os
from pathlib import Path

import yaml

from agents.llm.client import LLMClient
from agents.llm.providers.ollama import OllamaClient


class LLMRouter:
    """Route LLM requests to configured provider"""
    
    # Provider registry - maps provider names to client classes
    _provider_registry: dict[str, type[LLMClient]] = {
        'ollama': OllamaClient,
        # Future providers can be added here:
        # 'docker_model': DockerModelClient,
        # 'openai': OpenAIClient,
    }
    
    def __init__(self, config: dict):
        self.config = config
        self.default_provider = config.get('default_provider', 'ollama')
    
    @classmethod
    def register_provider(cls, name: str, client_class: type[LLMClient]):
        """Register a new LLM provider dynamically"""
        cls._provider_registry[name] = client_class
        logger = importlib.import_module('logging').getLogger(__name__)
        logger.info(f"Registered LLM provider: {name}")
    
    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available provider names"""
        return list(cls._provider_registry.keys())
    
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
                import os
                from infra.config.loader import load_config
                strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
                app_config = load_config(strict=strict_mode)
                # Use AppConfig model attributes (SIP-051)
                default_url = app_config.llm.url
                default_model = app_config.llm.model
                default_timeout = app_config.llm.timeout
            except Exception as e:
                # If unified config fails entirely, fall back to environment vars and hardcoded defaults
                logger.warning(f"Failed to load unified config, using fallbacks: {e}")
                default_url = None
                default_model = None
                default_timeout = None
            
            # Build config with clear logging for fallback usage
            # Use AppConfig LLM URL if available, otherwise fall back to default_url
            final_url = default_url or (app_config.llm.url if app_config.llm.url else None)
            final_model = default_model  # No longer read from AGENT_MODEL env var
            final_timeout = default_timeout
            
            # Log warnings for hardcoded fallbacks, especially model name
            if not final_url:
                logger.info("Using default Ollama URL: http://host.docker.internal:11434 (set OLLAMA_URL to override)")
                final_url = 'http://host.docker.internal:11434'
            
            if not final_model:
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
            
            if not final_timeout:
                logger.debug("Using default timeout: 180 seconds (set LLM_TIMEOUT to override)")
                final_timeout = 180
            
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
            import os
            from infra.config.loader import load_config
            strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
            config = load_config(strict=strict_mode)
            use_local_llm = config.llm.use_local
        except Exception as e:
            # Fallback to default if config fails
            logger.warning(f"Failed to load config for USE_LOCAL_LLM, using default: {e}")
            use_local_llm = True  # Default to True
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
        
        # Get provider class from registry
        provider_class = self._provider_registry.get(provider_name)
        if not provider_class:
            available = ', '.join(self._provider_registry.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {available}"
            )
        
        # Instantiate provider with config
        return provider_class(**provider_config)

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
            # Default config if file doesn't exist
            config = {
                'default_provider': 'ollama',
                'providers': {
                    'ollama': {
                        'url': os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434'),
                        'model': os.getenv('AGENT_MODEL', 'qwen2.5:7b'),
                        'timeout': 60
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
        provider_name = self.default_provider
        provider_config = self.config['providers'].get(provider_name, {})
        
        if provider_name == 'ollama':
            return OllamaClient(**provider_config)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

#!/usr/bin/env python3
"""
SquadOps Unified Configuration Manager
Consolidates deployment_config, agent_config, and environment variables
with platform-aware architecture for future extensibility
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from config import deployment_config, agent_config


class SquadOpsConfig:
    """
    Unified configuration manager that loads from:
    1. deployment_config.py (infrastructure URLs)
    2. agent_config.py (agent settings)
    3. config/environments/{platform}.yaml (optional platform overrides - future)
    4. Environment variables (highest priority)
    """
    
    def __init__(self, platform: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            platform: Optional platform override (local, edge, aws, gcp, azure, jetson)
                     If None, auto-detects from SQUADOPS_PLATFORM env var or defaults to 'local'
        """
        self.platform = platform or os.getenv('SQUADOPS_PLATFORM', 'local')
        self._platform_profile = None
        
        # Load platform profile if it exists (graceful fallback if not)
        self._load_platform_profile()
        
        # Validate configuration
        self._validate()
    
    def _load_platform_profile(self):
        """Load platform-specific profile if it exists (optional, future-ready)"""
        profile_path = Path(__file__).parent / 'environments' / f'{self.platform}.yaml'
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
                    self._platform_profile = yaml.safe_load(f)
            except Exception:
                # Gracefully handle missing YAML parser or invalid files
                self._platform_profile = None
    
    def _get_platform_value(self, key: str, default: Any = None) -> Any:
        """Get value from platform profile if it exists"""
        if self._platform_profile:
            return self._platform_profile.get(key, default)
        return default
    
    def _get_env_with_platform_fallback(self, env_var: str, default: Any) -> Any:
        """Get value from env var, then platform profile, then default"""
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value
        platform_value = self._get_platform_value(env_var.lower(), None)
        if platform_value is not None:
            return platform_value
        return default
    
    def _validate(self):
        """Validate configuration on initialization"""
        # Basic validation - can be extended
        if not self.get_task_api_url():
            raise ValueError("Task API URL is required")
    
    # Infrastructure URLs
    
    def get_rabbitmq_url(self) -> str:
        """Get RabbitMQ connection URL"""
        env_url = os.getenv('RABBITMQ_URL')
        if env_url:
            return env_url
        
        # Use deployment_config helper
        return deployment_config.get_rabbitmq_url()
    
    def get_postgres_url(self) -> str:
        """Get PostgreSQL database URL"""
        env_url = os.getenv('POSTGRES_URL')
        if env_url:
            return env_url
        
        # Use deployment_config helper
        return deployment_config.get_database_url()
    
    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        env_url = os.getenv('REDIS_URL')
        if env_url:
            return env_url
        
        # Use deployment_config helper
        return deployment_config.get_redis_url()
    
    def get_task_api_url(self) -> str:
        """Get Task API URL"""
        return os.getenv('TASK_API_URL', 'http://task-api:8001')
    
    def get_tasks_backend(self) -> str:
        """Get tasks backend selection"""
        return os.getenv('TASKS_BACKEND', 'sql').lower()
    
    # Agent Configuration
    
    def get_agent_id(self) -> str:
        """Get agent ID"""
        return os.getenv('AGENT_ID', 'unknown_agent')
    
    def get_agent_role(self) -> str:
        """Get agent role"""
        return os.getenv('AGENT_ROLE', 'unknown')
    
    def get_agent_display_name(self) -> str:
        """Get agent display name"""
        return os.getenv('AGENT_DISPLAY_NAME', self.get_agent_id())
    
    def get_agent_config(self, key: str) -> Any:
        """
        Get agent configuration value
        
        Args:
            key: Configuration key (complexity_threshold, task_processing, communication, etc.)
        """
        if key == 'id':
            return self.get_agent_id()
        elif key == 'role':
            return self.get_agent_role()
        elif key == 'display_name':
            return self.get_agent_display_name()
        
        # Map to agent_config functions
        config_mapping = {
            'complexity_threshold': agent_config.get_complexity_threshold,
            'task_config': agent_config.get_task_config,
            'communication_config': agent_config.get_communication_config,
            'logging_config': agent_config.get_logging_config,
            'performance_config': agent_config.get_performance_config,
            'security_config': agent_config.get_security_config,
        }
        
        if key in config_mapping:
            return config_mapping[key]
        
        return None
    
    # LLM Configuration
    
    def get_llm_config(self, key: Optional[str] = None) -> Any:
        """
        Get LLM configuration
        
        Args:
            key: Optional specific config key (url, model, use_local, etc.)
                 If None, returns all LLM config as dict
        """
        llm_config = {
            'url': self._get_env_with_platform_fallback('OLLAMA_URL', 'http://host.docker.internal:11434'),
            'model': None,  # No default - agents must configure model in config.yaml defaults.model
            'use_local': os.getenv('USE_LOCAL_LLM', 'true').lower() == 'true',
            'timeout': int(os.getenv('LLM_TIMEOUT', '60'))
        }
        
        if key:
            return llm_config.get(key)
        return llm_config
    
    def get_ollama_url(self) -> str:
        """Get Ollama URL"""
        return self.get_llm_config('url')
    
    def get_agent_model(self) -> str:
        """Get agent model"""
        return self.get_llm_config('model')
    
    def get_use_local_llm(self) -> bool:
        """Get whether to use local LLM"""
        return self.get_llm_config('use_local')
    
    # Deployment Configuration Helpers
    
    def get_deployment_config(self, key: str) -> Any:
        """Get deployment configuration value"""
        return deployment_config.get_deployment_config(key)
    
    def get_infrastructure_config(self, key: str) -> Any:
        """Get infrastructure configuration value"""
        return deployment_config.get_infrastructure_config(key)
    
    def get_filesystem_config(self, key: str) -> Any:
        """Get filesystem configuration value"""
        return deployment_config.get_filesystem_config(key)
    
    # Platform information
    
    def get_platform(self) -> str:
        """Get current platform"""
        return self.platform
    
    # Service discovery (stubbed for future cloud providers)
    
    def get_service_endpoint(self, service: str) -> Optional[str]:
        """
        Get service endpoint with platform-aware service discovery (future)
        
        Currently returns None - ready for future implementation
        Examples: 'database', 'queue', 'cache', 'storage'
        """
        # Future: Implement AWS/GCP/Azure service discovery
        # For now, returns None to use standard URLs
        return None
    
    # Convenience methods for common patterns
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return {
            'platform': self.platform,
            'infrastructure': {
                'rabbitmq_url': self.get_rabbitmq_url(),
                'postgres_url': self.get_postgres_url(),
                'redis_url': self.get_redis_url(),
                'task_api_url': self.get_task_api_url(),
            },
            'agent': {
                'id': self.get_agent_id(),
                'role': self.get_agent_role(),
                'display_name': self.get_agent_display_name(),
            },
            'llm': self.get_llm_config(),
        }


# Global singleton instance (lazy initialization)
_config_instance: Optional[SquadOpsConfig] = None


def get_config(platform: Optional[str] = None) -> SquadOpsConfig:
    """
    Get global configuration instance (singleton pattern)
    
    Args:
        platform: Optional platform override for first initialization
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = SquadOpsConfig(platform=platform)
    return _config_instance


def reset_config():
    """Reset global config instance (useful for testing)"""
    global _config_instance
    _config_instance = None


#!/usr/bin/env python3
"""
SquadOps Agent Configuration
Centralized configuration for all agent-related settings
"""

import os
from typing import Any

# Agent Complexity Thresholds
COMPLEXITY_THRESHOLDS = {
    "escalation": float(os.getenv("AGENT_ESCALATION_THRESHOLD", "0.8")),
    "delegation": float(os.getenv("AGENT_DELEGATION_THRESHOLD", "0.5")),
    "approval": float(os.getenv("AGENT_APPROVAL_THRESHOLD", "0.9")),
    "high_priority": float(os.getenv("AGENT_HIGH_PRIORITY_THRESHOLD", "0.7"))
}

# Agent Task Processing Configuration
TASK_PROCESSING_CONFIG = {
    "max_retries": int(os.getenv("TASK_MAX_RETRIES", "3")),
    "retry_delay": float(os.getenv("TASK_RETRY_DELAY", "1.0")),
    "timeout_seconds": int(os.getenv("TASK_TIMEOUT_SECONDS", "300")),
    "batch_size": int(os.getenv("TASK_BATCH_SIZE", "10"))
}

# Agent Communication Configuration
COMMUNICATION_CONFIG = {
    "message_timeout": int(os.getenv("MESSAGE_TIMEOUT", "30")),
    "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "60")),
    "max_message_size": int(os.getenv("MAX_MESSAGE_SIZE", "1048576")),  # 1MB
    "queue_durable": os.getenv("QUEUE_DURABLE", "true").lower() == "true"
}

# Agent Logging Configuration
LOGGING_CONFIG = {
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    "log_format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
    "log_file": os.getenv("LOG_FILE", "/app/logs/agent.log"),
    "max_log_size": int(os.getenv("MAX_LOG_SIZE", "10485760")),  # 10MB
    "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5"))
}

# Agent Performance Configuration
PERFORMANCE_CONFIG = {
    "connection_pool_size": int(os.getenv("CONNECTION_POOL_SIZE", "10")),
    "max_concurrent_tasks": int(os.getenv("MAX_CONCURRENT_TASKS", "5")),
    "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),  # 1 hour
    "memory_limit": int(os.getenv("AGENT_MEMORY_LIMIT", "512"))  # MB
}

# Agent Security Configuration
SECURITY_CONFIG = {
    "enable_authentication": os.getenv("ENABLE_AUTHENTICATION", "false").lower() == "true",
    "jwt_secret": os.getenv("JWT_SECRET", "your-secret-key"),
    "jwt_expiry": int(os.getenv("JWT_EXPIRY", "3600")),  # 1 hour
    "api_key_required": os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
}

def get_complexity_threshold(threshold_type: str) -> float:
    """Get complexity threshold by type"""
    return COMPLEXITY_THRESHOLDS.get(threshold_type, 0.5)

def get_task_config(config_key: str) -> Any:
    """Get task processing configuration"""
    return TASK_PROCESSING_CONFIG.get(config_key)

def get_communication_config(config_key: str) -> Any:
    """Get communication configuration"""
    return COMMUNICATION_CONFIG.get(config_key)

def get_logging_config(config_key: str) -> Any:
    """Get logging configuration"""
    return LOGGING_CONFIG.get(config_key)

def get_performance_config(config_key: str) -> Any:
    """Get performance configuration"""
    return PERFORMANCE_CONFIG.get(config_key)

def get_security_config(config_key: str) -> Any:
    """Get security configuration"""
    return SECURITY_CONFIG.get(config_key)

# Configuration validation
def validate_config() -> bool:
    """Validate all configuration values"""
    try:
        # Validate complexity thresholds
        for threshold_type, value in COMPLEXITY_THRESHOLDS.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Complexity threshold {threshold_type} must be between 0.0 and 1.0")
        
        # Validate task processing config
        if TASK_PROCESSING_CONFIG["max_retries"] < 0:
            raise ValueError("max_retries must be non-negative")
        
        if TASK_PROCESSING_CONFIG["retry_delay"] <= 0:
            raise ValueError("retry_delay must be positive")
        
        # Validate performance config
        if PERFORMANCE_CONFIG["connection_pool_size"] <= 0:
            raise ValueError("connection_pool_size must be positive")
        
        return True
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        return False

if __name__ == "__main__":
    # Test configuration
    print("SquadOps Agent Configuration")
    print("=" * 40)
    print(f"Complexity Thresholds: {COMPLEXITY_THRESHOLDS}")
    print(f"Task Processing: {TASK_PROCESSING_CONFIG}")
    print(f"Communication: {COMMUNICATION_CONFIG}")
    print(f"Logging: {LOGGING_CONFIG}")
    print(f"Performance: {PERFORMANCE_CONFIG}")
    print(f"Security: {SECURITY_CONFIG}")
    print(f"Configuration Valid: {validate_config()}")

#!/usr/bin/env python3
"""
SquadOps Deployment Configuration
Centralized configuration for deployment and infrastructure settings
"""

import os
from typing import Dict, Any, List

# Docker Configuration
DOCKER_CONFIG = {
    "network_name": os.getenv("DOCKER_NETWORK_NAME", "squad-ops_squadnet"),
    "restart_policy": os.getenv("DOCKER_RESTART_POLICY", "unless-stopped"),
    "port_mapping": os.getenv("DOCKER_PORT_MAPPING", "8080:80"),
    "base_image": os.getenv("DOCKER_BASE_IMAGE", "python:3.11-slim"),
    "timeout": int(os.getenv("DOCKER_TIMEOUT", "300")),
    "memory_limit": os.getenv("DOCKER_MEMORY_LIMIT", "512m"),
    "cpu_limit": os.getenv("DOCKER_CPU_LIMIT", "0.5")
}

# Application Deployment Configuration
DEPLOYMENT_CONFIG = {
    "default_port": int(os.getenv("DEFAULT_APP_PORT", "8080")),
    "health_check_path": os.getenv("HEALTH_CHECK_PATH", "/health"),
    "health_check_timeout": int(os.getenv("HEALTH_CHECK_TIMEOUT", "30")),
    "deployment_timeout": int(os.getenv("DEPLOYMENT_TIMEOUT", "600")),
    "max_deployments": int(os.getenv("MAX_DEPLOYMENTS", "10")),
    "cleanup_old_deployments": os.getenv("CLEANUP_OLD_DEPLOYMENTS", "true").lower() == "true"
}

# Infrastructure Configuration
INFRASTRUCTURE_CONFIG = {
    "rabbitmq_host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
    "rabbitmq_port": int(os.getenv("RABBITMQ_PORT", "5672")),
    "rabbitmq_user": os.getenv("RABBITMQ_USER", "squadops"),
    "rabbitmq_vhost": os.getenv("RABBITMQ_VHOST", "/"),
    
    "postgres_host": os.getenv("POSTGRES_HOST", "postgres"),
    "postgres_port": int(os.getenv("POSTGRES_PORT", "5432")),
    "postgres_db": os.getenv("POSTGRES_DB", "squadops"),
    "postgres_user": os.getenv("POSTGRES_USER", "squadops"),
    
    "redis_host": os.getenv("REDIS_HOST", "redis"),
    "redis_port": int(os.getenv("REDIS_PORT", "6379")),
    "redis_db": int(os.getenv("REDIS_DB", "0")),
    
    "health_check_port": int(os.getenv("HEALTH_CHECK_PORT", "8000")),
    "health_check_host": os.getenv("HEALTH_CHECK_HOST", "0.0.0.0")
}

# File System Configuration
FILESYSTEM_CONFIG = {
    "warm_boot_dir": os.getenv("WARM_BOOT_DIR", "/app/warm-boot"),
    "apps_dir": os.getenv("APPS_DIR", "/app/warm-boot/apps"),
    "archive_dir": os.getenv("ARCHIVE_DIR", "/app/warm-boot/archive"),
    "runs_dir": os.getenv("RUNS_DIR", "/app/warm-boot/runs"),
    "prd_dir": os.getenv("PRD_DIR", "/app/warm-boot/prd"),
    "max_file_size": int(os.getenv("MAX_FILE_SIZE", "10485760")),  # 10MB
    "allowed_extensions": os.getenv("ALLOWED_EXTENSIONS", ".md,.py,.js,.html,.css,.json,.yaml,.yml").split(",")
}

# Version Management Configuration
VERSION_CONFIG = {
    "framework_version": os.getenv("FRAMEWORK_VERSION", "0.1.4"),
    "version_format": os.getenv("VERSION_FORMAT", "{framework}.{sequence}"),
    "archive_format": os.getenv("ARCHIVE_FORMAT", "{app}-{version}-archive"),
    "container_name_format": os.getenv("CONTAINER_NAME_FORMAT", "squadops-{app}"),
    "image_tag_format": os.getenv("IMAGE_TAG_FORMAT", "{app}:{version}")
}

# Security Configuration
SECURITY_CONFIG = {
    "enable_ssl": os.getenv("ENABLE_SSL", "false").lower() == "true",
    "ssl_cert_path": os.getenv("SSL_CERT_PATH", "/app/certs/cert.pem"),
    "ssl_key_path": os.getenv("SSL_KEY_PATH", "/app/certs/key.pem"),
    "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
    "rate_limit": int(os.getenv("RATE_LIMIT", "100")),
    "rate_limit_window": int(os.getenv("RATE_LIMIT_WINDOW", "60"))
}

# Monitoring Configuration
MONITORING_CONFIG = {
    "enable_metrics": os.getenv("ENABLE_METRICS", "true").lower() == "true",
    "metrics_port": int(os.getenv("METRICS_PORT", "9090")),
    "metrics_path": os.getenv("METRICS_PATH", "/metrics"),
    "enable_tracing": os.getenv("ENABLE_TRACING", "false").lower() == "true",
    "tracing_endpoint": os.getenv("TRACING_ENDPOINT", "http://jaeger:14268/api/traces"),
    "log_level": os.getenv("MONITORING_LOG_LEVEL", "INFO")
}

def get_docker_config(config_key: str) -> Any:
    """Get Docker configuration value"""
    return DOCKER_CONFIG.get(config_key)

def get_deployment_config(config_key: str) -> Any:
    """Get deployment configuration value"""
    return DEPLOYMENT_CONFIG.get(config_key)

def get_infrastructure_config(config_key: str) -> Any:
    """Get infrastructure configuration value"""
    return INFRASTRUCTURE_CONFIG.get(config_key)

def get_filesystem_config(config_key: str) -> Any:
    """Get filesystem configuration value"""
    return FILESYSTEM_CONFIG.get(config_key)

def get_version_config(config_key: str) -> Any:
    """Get version management configuration value"""
    return VERSION_CONFIG.get(config_key)

def get_security_config(config_key: str) -> Any:
    """Get security configuration value"""
    return SECURITY_CONFIG.get(config_key)

def get_monitoring_config(config_key: str) -> Any:
    """Get monitoring configuration value"""
    return MONITORING_CONFIG.get(config_key)

# Helper functions for common configurations
def get_database_url() -> str:
    """Get PostgreSQL database URL"""
    return f"postgresql://{INFRASTRUCTURE_CONFIG['postgres_user']}:{os.getenv('POSTGRES_PASSWORD', 'password')}@{INFRASTRUCTURE_CONFIG['postgres_host']}:{INFRASTRUCTURE_CONFIG['postgres_port']}/{INFRASTRUCTURE_CONFIG['postgres_db']}"

def get_rabbitmq_url() -> str:
    """Get RabbitMQ connection URL"""
    return f"amqp://{INFRASTRUCTURE_CONFIG['rabbitmq_user']}:{os.getenv('RABBITMQ_PASSWORD', 'password')}@{INFRASTRUCTURE_CONFIG['rabbitmq_host']}:{INFRASTRUCTURE_CONFIG['rabbitmq_port']}{INFRASTRUCTURE_CONFIG['rabbitmq_vhost']}"

def get_redis_url() -> str:
    """Get Redis connection URL"""
    return f"redis://{INFRASTRUCTURE_CONFIG['redis_host']}:{INFRASTRUCTURE_CONFIG['redis_port']}/{INFRASTRUCTURE_CONFIG['redis_db']}"

def get_container_name(app_name: str) -> str:
    """Get container name for application"""
    return VERSION_CONFIG["container_name_format"].format(app=app_name.lower().replace("_", "-"))

def get_image_tag(app_name: str, version: str) -> str:
    """Get Docker image tag for application"""
    return VERSION_CONFIG["image_tag_format"].format(app=app_name.lower().replace("_", "-"), version=version)

def get_archive_name(app_name: str, version: str) -> str:
    """Get archive directory name for application"""
    return VERSION_CONFIG["archive_format"].format(app=app_name.lower().replace("_", "-"), version=version)

# Configuration validation
def validate_deployment_config() -> bool:
    """Validate deployment configuration"""
    try:
        # Validate port numbers
        if not 1 <= DEPLOYMENT_CONFIG["default_port"] <= 65535:
            raise ValueError("default_port must be between 1 and 65535")
        
        if not 1 <= INFRASTRUCTURE_CONFIG["postgres_port"] <= 65535:
            raise ValueError("postgres_port must be between 1 and 65535")
        
        if not 1 <= INFRASTRUCTURE_CONFIG["redis_port"] <= 65535:
            raise ValueError("redis_port must be between 1 and 65535")
        
        # Validate timeouts
        if DEPLOYMENT_CONFIG["deployment_timeout"] <= 0:
            raise ValueError("deployment_timeout must be positive")
        
        if DEPLOYMENT_CONFIG["health_check_timeout"] <= 0:
            raise ValueError("health_check_timeout must be positive")
        
        # Validate file system paths
        required_dirs = ["warm_boot_dir", "apps_dir", "archive_dir", "runs_dir", "prd_dir"]
        for dir_key in required_dirs:
            if not FILESYSTEM_CONFIG[dir_key]:
                raise ValueError(f"{dir_key} cannot be empty")
        
        return True
    except Exception as e:
        print(f"Deployment configuration validation failed: {e}")
        return False

if __name__ == "__main__":
    # Test configuration
    print("SquadOps Deployment Configuration")
    print("=" * 40)
    print(f"Docker Config: {DOCKER_CONFIG}")
    print(f"Deployment Config: {DEPLOYMENT_CONFIG}")
    print(f"Infrastructure Config: {INFRASTRUCTURE_CONFIG}")
    print(f"Filesystem Config: {FILESYSTEM_CONFIG}")
    print(f"Version Config: {VERSION_CONFIG}")
    print(f"Security Config: {SECURITY_CONFIG}")
    print(f"Monitoring Config: {MONITORING_CONFIG}")
    print(f"Configuration Valid: {validate_deployment_config()}")
    print(f"Database URL: {get_database_url()}")
    print(f"RabbitMQ URL: {get_rabbitmq_url()}")
    print(f"Redis URL: {get_redis_url()}")

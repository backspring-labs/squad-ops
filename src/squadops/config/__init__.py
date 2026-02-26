"""
SquadOps Configuration Module.

Provides configuration loading, validation, and utilities.
"""

from squadops.config.errors import ConfigValidationError
from squadops.config.fingerprint import config_fingerprint
from squadops.config.loader import get_config, load_config, parse_cli_args, reset_config
from squadops.config.redaction import redact_config, redact_value
from squadops.config.schema import (
    AgentConfig,
    AppConfig,
    CommsConfig,
    DBConfig,
    DeploymentConfig,
    LLMConfig,
    ObservabilityConfig,
    PrefectConfig,
    RabbitMQConfig,
    RedisConfig,
    SecretsConfig,
    TasksBackend,
    TelemetryConfig,
)

__all__ = [
    # Loader functions
    "load_config",
    "get_config",
    "reset_config",
    "parse_cli_args",
    # Utilities
    "redact_config",
    "redact_value",
    "config_fingerprint",
    # Errors
    "ConfigValidationError",
    # Schema types
    "AppConfig",
    "SecretsConfig",
    "DBConfig",
    "CommsConfig",
    "RabbitMQConfig",
    "RedisConfig",
    "PrefectConfig",
    "LLMConfig",
    "AgentConfig",
    "TelemetryConfig",
    "ObservabilityConfig",
    "DeploymentConfig",
    "TasksBackend",
]

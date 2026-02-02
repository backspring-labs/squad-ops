"""
SquadOps Configuration Module.

Provides configuration loading, validation, and utilities.
"""

from squadops.config.redaction import redact_config, redact_value
from squadops.config.fingerprint import config_fingerprint
from squadops.config.errors import ConfigValidationError
from squadops.config.loader import load_config, get_config, reset_config, parse_cli_args
from squadops.config.schema import (
    AppConfig,
    SecretsConfig,
    DBConfig,
    CommsConfig,
    RabbitMQConfig,
    RedisConfig,
    PrefectConfig,
    LLMConfig,
    AgentConfig,
    TelemetryConfig,
    ObservabilityConfig,
    DeploymentConfig,
    TasksBackend,
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

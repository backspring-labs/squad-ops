"""
Factory for creating queue transport adapter instances.
This factory maps configuration to concrete adapter instances and resolves secrets.
"""

import logging
from typing import Any

from adapters.comms.rabbitmq import RabbitMQAdapter
from squadops.core.secrets import SecretManager

logger = logging.getLogger(__name__)


def validate_comms_config(profile: dict[str, Any]) -> None:
    """
    Validate communication/queue configuration from profile.

    Args:
        profile: Configuration profile dictionary

    Raises:
        ValueError: If required configuration keys are missing or invalid
    """
    comms_config = profile.get("comms")
    if not comms_config:
        raise ValueError("Communication configuration ('comms') not found in profile")

    provider = comms_config.get("provider")
    if not provider:
        raise ValueError("Queue provider ('comms.provider') not specified")

    if provider == "rabbitmq":
        # RabbitMQ requires URL
        url = comms_config.get("url")
        if not url:
            raise ValueError("RabbitMQ URL ('comms.url') is required when provider=rabbitmq")


def get_queue_adapter(
    profile: dict[str, Any], secret_manager: SecretManager
) -> Any:  # Returns QueuePort, but using Any to avoid circular import
    """
    Create a queue transport adapter instance based on profile configuration.

    This factory function:
    1. Validates the communication configuration
    2. Resolves secret:// references in URL/credentials via SecretManager
    3. Creates and returns the appropriate QueuePort implementation

    Args:
        profile: Configuration profile dictionary containing 'comms' section
        secret_manager: SecretManager instance for resolving secret:// references

    Returns:
        QueuePort instance (currently only RabbitMQAdapter is supported)

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate configuration
    validate_comms_config(profile)

    comms_config = profile["comms"]
    provider = comms_config["provider"]

    if provider == "rabbitmq":
        # Extract URL (may contain secret:// references)
        url = comms_config.get("url")
        if not url:
            raise ValueError("RabbitMQ URL ('comms.url') is required")

        # Resolve secret:// references in URL
        # SecretManager.resolve_all_references handles dicts, but URL is a string
        # So we resolve it directly
        if "secret://" in url:
            # Extract secret reference and resolve
            resolved_url = secret_manager.resolve(url)
        else:
            resolved_url = url

        # Extract namespace (optional)
        namespace = comms_config.get("namespace")

        # Create RabbitMQAdapter instance
        adapter = RabbitMQAdapter(url=resolved_url, namespace=namespace)

        logger.info(
            f"Created RabbitMQAdapter instance (namespace={namespace}, provider={provider})"
        )

        return adapter
    else:
        raise ValueError(f"Unknown queue provider: {provider}")

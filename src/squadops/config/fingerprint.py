"""
Configuration fingerprinting for debugging and change detection.

This module provides functions to generate stable hashes of configuration
dictionaries, useful for detecting configuration changes across deployments.
"""

import hashlib
import json
from typing import Any

from squadops.config.redaction import redact_config


def config_fingerprint(config: dict[str, Any]) -> str:
    """
    Generate a stable fingerprint (hash) for a configuration dictionary.

    The fingerprint is based on the redacted configuration to ensure
    that secret values don't affect the fingerprint, while still detecting
    meaningful configuration changes.

    Args:
        config: Configuration dictionary

    Returns:
        Stable hash string (hex digest) prefixed with "cfg-"
    """
    # Redact sensitive values before fingerprinting
    redacted = redact_config(config)

    # Sort keys for deterministic ordering
    # Convert to JSON string for hashing
    try:
        # Use sort_keys=True for deterministic output
        config_str = json.dumps(redacted, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Fallback: convert to string representation
        config_str = str(sorted(redacted.items()))

    # Generate SHA256 hash
    hash_obj = hashlib.sha256(config_str.encode("utf-8"))
    hash_hex = hash_obj.hexdigest()[:16]  # Use first 16 chars for brevity

    return f"cfg-{hash_hex}"

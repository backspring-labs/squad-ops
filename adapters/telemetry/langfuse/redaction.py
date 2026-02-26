"""Redaction strategies for LLM observability data (SIP-0061).

Applied at buffer ingestion time (before enqueue) so sensitive data
never enters the buffer.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod


class RedactionStrategy(ABC):
    """Base class for redaction strategies."""

    @abstractmethod
    def redact(self, text: str) -> str:
        """Redact sensitive content from text. Returns redacted copy."""


# ---------------------------------------------------------------------------
# Common patterns
# ---------------------------------------------------------------------------

# API keys / tokens — generic patterns that cover most providers
_API_KEY_PATTERNS: list[re.Pattern[str]] = [
    # Bearer tokens
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}", re.IGNORECASE),
    # Generic API key patterns: sk-..., pk-..., api-..., key-...
    re.compile(r"\b(?:sk|pk|api|key)[-_][A-Za-z0-9\-_]{16,}\b"),
    # AWS-style keys (AKIA...)
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    # secret:// references that should never leak
    re.compile(r"secret://[A-Za-z0-9_]+"),
]

# Password-like patterns
_PASSWORD_PATTERNS: list[re.Pattern[str]] = [
    # password=... or password:... in connection strings / config
    re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
    # Connection string password component
    re.compile(r"://[^:]+:([^@]+)@"),
]

# PII patterns (strict mode only)
_PII_PATTERNS: list[re.Pattern[str]] = [
    # Email addresses
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    # Phone numbers (US/international)
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    # SSN patterns
    re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
]

_REDACTED = "[REDACTED]"
_REDACTED_PII = "[REDACTED-PII]"


class StandardRedaction(RedactionStrategy):
    """Strips known secret patterns (API keys, tokens, passwords).

    Default mode — suitable for most environments.
    """

    def redact(self, text: str) -> str:
        result = text
        for pattern in _API_KEY_PATTERNS:
            result = pattern.sub(_REDACTED, result)
        for pattern in _PASSWORD_PATTERNS:
            # For connection strings, only redact the password group
            if "://" in pattern.pattern:
                result = pattern.sub(lambda m: m.group(0).replace(m.group(1), _REDACTED), result)
            else:
                result = pattern.sub(_REDACTED, result)
        return result


class StrictRedaction(RedactionStrategy):
    """Strips secrets + PII patterns. Hashes identifiers for correlation.

    Recommended for production environments.
    """

    def redact(self, text: str) -> str:
        # First apply standard redaction
        result = text
        for pattern in _API_KEY_PATTERNS:
            result = pattern.sub(_REDACTED, result)
        for pattern in _PASSWORD_PATTERNS:
            if "://" in pattern.pattern:
                result = pattern.sub(lambda m: m.group(0).replace(m.group(1), _REDACTED), result)
            else:
                result = pattern.sub(_REDACTED, result)
        # Then apply PII redaction
        for pattern in _PII_PATTERNS:
            result = pattern.sub(_REDACTED_PII, result)
        return result

    @staticmethod
    def hash_identifier(value: str) -> str:
        """Hash an identifier for correlation without exposing the raw value."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]


def get_redaction_strategy(mode: str) -> RedactionStrategy:
    """Factory for redaction mode selection.

    Args:
        mode: "standard" or "strict"

    Returns:
        RedactionStrategy implementation

    Raises:
        ValueError: If mode is unknown
    """
    if mode == "standard":
        return StandardRedaction()
    if mode == "strict":
        return StrictRedaction()
    raise ValueError(f"Unknown redaction mode: {mode!r}. Use 'standard' or 'strict'.")

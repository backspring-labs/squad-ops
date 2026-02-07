"""Unit tests for redaction strategies (SIP-0061)."""

import pytest

from adapters.telemetry.langfuse.redaction import (
    StandardRedaction,
    StrictRedaction,
    get_redaction_strategy,
)


class TestStandardRedaction:
    """Standard mode: strips API keys, tokens, passwords."""

    def test_redacts_bearer_token(self):
        r = StandardRedaction()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        result = r.redact(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redacts_sk_api_key(self):
        r = StandardRedaction()
        text = "Key is sk-abc123def456ghi789jkl012"
        result = r.redact(text)
        assert "sk-abc123def456ghi789jkl012" not in result

    def test_redacts_pk_api_key(self):
        r = StandardRedaction()
        text = "Public key: pk-lf-1234567890abcdef1234"
        result = r.redact(text)
        assert "pk-lf-1234567890abcdef1234" not in result

    def test_redacts_aws_key(self):
        r = StandardRedaction()
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = r.redact(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_redacts_secret_reference(self):
        r = StandardRedaction()
        text = "Using secret://MY_SECRET_KEY for auth"
        result = r.redact(text)
        assert "secret://MY_SECRET_KEY" not in result

    def test_redacts_password_in_connection_string(self):
        r = StandardRedaction()
        text = "postgresql://user:mysecretpass@localhost:5432/db"
        result = r.redact(text)
        assert "mysecretpass" not in result
        # URL structure should be preserved
        assert "localhost:5432" in result

    def test_redacts_password_key_value(self):
        r = StandardRedaction()
        text = "password=hunter2 in config"
        result = r.redact(text)
        assert "hunter2" not in result

    def test_no_false_positive_on_normal_text(self):
        r = StandardRedaction()
        text = "The quick brown fox jumps over the lazy dog. Version 1.2.3"
        result = r.redact(text)
        assert result == text  # No changes

    def test_no_false_positive_on_short_key_like_words(self):
        r = StandardRedaction()
        text = "Use the skip command to skip the test"
        result = r.redact(text)
        assert result == text


class TestStrictRedaction:
    """Strict mode: standard + PII patterns."""

    def test_redacts_email(self):
        r = StrictRedaction()
        text = "Contact user@example.com for help"
        result = r.redact(text)
        assert "user@example.com" not in result
        assert "[REDACTED-PII]" in result

    def test_redacts_phone_number(self):
        r = StrictRedaction()
        text = "Call 555-123-4567 for support"
        result = r.redact(text)
        assert "555-123-4567" not in result

    def test_redacts_ssn(self):
        r = StrictRedaction()
        text = "SSN: 123-45-6789"
        result = r.redact(text)
        assert "123-45-6789" not in result

    def test_also_redacts_api_keys(self):
        r = StrictRedaction()
        text = "Key is sk-abc123def456ghi789jkl012"
        result = r.redact(text)
        assert "sk-abc123def456ghi789jkl012" not in result

    def test_hash_identifier(self):
        h1 = StrictRedaction.hash_identifier("test@example.com")
        h2 = StrictRedaction.hash_identifier("test@example.com")
        h3 = StrictRedaction.hash_identifier("other@example.com")
        assert h1 == h2  # Deterministic
        assert h1 != h3  # Different inputs produce different hashes
        assert len(h1) == 16  # Truncated to 16 chars


class TestGetRedactionStrategy:
    """Factory function for mode selection."""

    def test_standard_mode(self):
        s = get_redaction_strategy("standard")
        assert isinstance(s, StandardRedaction)

    def test_strict_mode(self):
        s = get_redaction_strategy("strict")
        assert isinstance(s, StrictRedaction)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown redaction mode"):
            get_redaction_strategy("ultra")

"""Unit tests for redaction strategies (SIP-0061)."""

import re

import pytest

from adapters.telemetry.langfuse.redaction import (
    _API_KEY_PATTERNS,
    _PASSWORD_PATTERNS,
    _PII_PATTERNS,
    StandardRedaction,
    StrictRedaction,
    get_redaction_strategy,
)


class TestPatternHygiene:
    """#573 asked for a sweep of the sibling patterns for the same typo. This
    pins the outcome rather than leaving it to the next reader's eyeball."""

    # A `[...]` containing an unescaped `|` — the #573 shape.
    _CLASS_WITH_PIPE = re.compile(r"\[(?:[^\]\\]|\\.)*\|(?:[^\]\\]|\\.)*\]")

    @pytest.mark.parametrize(
        "pattern",
        [*_API_KEY_PATTERNS, *_PASSWORD_PATTERNS, *_PII_PATTERNS],
        ids=lambda p: p.pattern[:40],
    )
    def test_no_literal_pipe_inside_a_character_class(self, pattern):
        """In a character class `|` is a literal pipe, never alternation. In a
        scrubber that means the class silently accepts a character it was never
        meant to, and the match runs past its intended end — which is how the
        email pattern started swallowing the next pipe-delimited log field.
        No pattern in this module wants a literal pipe."""
        assert self._CLASS_WITH_PIPE.search(pattern.pattern) is None


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

    def test_email_redaction_stops_at_the_address_in_a_pipe_delimited_line(self):
        """#573: the TLD class was `[A-Z|a-z]`, and a `|` inside a character
        class is a *literal pipe*, not alternation. The match therefore ran past
        the address into the next pipe-delimited field, so a log line lost its
        surrounding context — `email=…|status=ok` redacted to
        `email=[REDACTED-PII]=ok`, silently corrupting the record it was meant to
        make safe. Pipe-delimited fields are everywhere in log output, so this is
        the shape that actually bit."""
        r = StrictRedaction()

        result = r.redact("email=alice@example.com|status=ok|retry=3")

        assert result == "email=[REDACTED-PII]|status=ok|retry=3"

    def test_a_pipe_is_not_a_tld_character(self):
        """The direct statement of the typo: `b.c|m` is not a domain, so the
        pattern must not treat it as one."""
        r = StrictRedaction()

        assert r.redact("user@example.c|m") == "user@example.c|m"

    @pytest.mark.parametrize(
        "address",
        [
            "alice@example.com",
            "Bob.Smith+tag@sub.example.co.uk",
            "x@y.IO",
            "user_name%test@mail-server.example.org",
        ],
    )
    def test_real_addresses_still_redact(self, address):
        """The fix narrows the class, so the guard that matters is that every
        genuine address still scrubs — both ranges were always covered, and this
        pins that they stay covered."""
        r = StrictRedaction()

        assert address not in r.redact(f"Contact {address} for help")


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

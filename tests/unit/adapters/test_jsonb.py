"""Tests for the shared asyncpg JSONB decode helper (#156).

Single-sources the decode used by every postgres-backed adapter; this locks the
contract so the behavior can't drift back into per-adapter copies.
"""

from __future__ import annotations

import json

import pytest

from adapters.jsonb import parse_jsonb


def test_decodes_json_object_string():
    """asyncpg returns JSONB as a JSON string by default — decode it to a dict."""
    assert parse_jsonb('{"key": "value"}') == {"key": "value"}


def test_decodes_json_array_string():
    """A JSONB array column decodes to a list (e.g. the *_refs / id columns in
    the cycle registry)."""
    assert parse_jsonb('["a", "b"]') == ["a", "b"]


def test_passes_through_already_decoded_value():
    """An already-decoded value (tests, or a registered custom codec) is
    returned unchanged — same object, not a re-encoded copy."""
    value = {"key": "value"}
    assert parse_jsonb(value) is value


def test_none_passes_through_as_none():
    """None (SQL NULL) is returned as-is. The None→{} coercion is deliberately
    NOT baked into the helper — callers that need it apply ``or {}`` at the call
    site (e.g. chat metadata)."""
    assert parse_jsonb(None) is None


def test_invalid_json_string_raises():
    """A malformed JSON string surfaces a decode error rather than being
    silently swallowed."""
    with pytest.raises(json.JSONDecodeError):
        parse_jsonb("{not valid json}")

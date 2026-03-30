"""Unit tests for model context registry (SIP-0073)."""

import pytest

from squadops.llm.model_registry import MODEL_SPECS, ModelSpec, get_model_spec


class TestModelSpec:
    """Tests for ModelSpec dataclass."""

    def test_frozen(self):
        spec = ModelSpec(name="test", context_window=8192, default_max_completion=4096)
        with pytest.raises(AttributeError):
            spec.name = "changed"  # type: ignore[misc]

    def test_all_specs_context_exceeds_completion(self):
        """Every registered model must have context_window > default_max_completion."""
        for name, spec in MODEL_SPECS.items():
            assert spec.context_window > spec.default_max_completion, (
                f"{name}: context_window ({spec.context_window}) must exceed "
                f"default_max_completion ({spec.default_max_completion})"
            )


class TestGetModelSpec:
    """Tests for get_model_spec lookup."""

    def test_registered_models_resolvable(self):
        """Every model in MODEL_SPECS must be resolvable by get_model_spec."""
        for name in MODEL_SPECS:
            spec = get_model_spec(name)
            assert spec is not None, f"get_model_spec({name!r}) returned None"
            assert spec.name == name

    def test_unknown_model_returns_none(self):
        assert get_model_spec("nonexistent-model") is None

    def test_whitespace_stripped(self):
        spec = get_model_spec("  qwen2.5:7b  ")
        assert spec is not None
        assert spec.name == "qwen2.5:7b"

    def test_empty_string_returns_none(self):
        assert get_model_spec("") is None

    def test_unknown_returns_none(self):
        """'unknown' (LLMPort.default_model default) returns None."""
        assert get_model_spec("unknown") is None

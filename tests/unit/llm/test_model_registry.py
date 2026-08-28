"""Unit tests for model context registry (SIP-0073)."""

import pytest

from squadops.llm.model_registry import MODEL_SPECS, ModelSpec, get_model_spec


class TestModelSpec:
    """Tests for ModelSpec dataclass."""

    def test_frozen(self):
        spec = ModelSpec(
            name="test", context_window=8192, default_max_completion=4096, reasoning_control="none"
        )
        with pytest.raises(AttributeError):
            spec.name = "changed"  # type: ignore[misc]

    def test_every_spec_declares_a_known_reasoning_dial(self):
        """#927: an entry whose dial is missing or misspelled makes the vLLM
        mapping silently send nothing and the handler-side clamp silently drop
        the level — the reasoning channel stays on, unobserved."""
        from squadops.llm.model_registry import ReasoningControl

        known = {ReasoningControl.NONE, ReasoningControl.TOGGLE, ReasoningControl.EFFORT}
        for spec in MODEL_SPECS.values():
            assert spec.reasoning_control in known, spec.name

    def test_qwen3_family_is_switchable_and_qwen25_is_not(self):
        """The two families the profiles run: #924's dial exists on qwen3 and
        Ollama 400s on ``think: true`` for qwen2.5 — a swapped declaration either
        leaves the 13.9× channel on or 400s every qwen2.5 call."""
        from squadops.llm.model_registry import ReasoningControl

        assert MODEL_SPECS["qwen3.6:27b"].reasoning_control == ReasoningControl.TOGGLE
        assert MODEL_SPECS["qwen3.8:27b"].reasoning_control == ReasoningControl.TOGGLE
        assert MODEL_SPECS["qwen2.5:7b"].reasoning_control == ReasoningControl.NONE

    def test_the_atlas_served_id_is_registered_with_the_served_window(self):
        """Atlas names the weights by HF path; unregistered, the resolver sends no
        reasoning level (the channel stays on) and the prompt guard has no window —
        and the window must be the served one, since Atlas rejects prompts past it."""
        spec = MODEL_SPECS["Qwen/Qwen3.8-27B-FP8"]
        assert spec.context_window == 32_768
        assert spec.default_max_completion == MODEL_SPECS["qwen3.8:27b"].default_max_completion

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

    def test_spark_squad_model_registered(self):
        # Regression: full runs uniformly on
        # qwen3.6:27b. Missing this entry caused the per-model completion
        # clamp to no-op, so the python_cli fallback (4000 tokens) silently
        # capped React/fullstack dev work in cyc_4178f25a0dff (cycle 2).
        spec = get_model_spec("qwen3.6:27b")
        assert spec is not None
        assert spec.context_window == 131_072
        assert spec.default_max_completion == 8_192


def test_qwen38_clamps_identically_to_the_v7_arm():
    """V38 shakedown finding 3: with no registry entry, the per-model completion
    clamp never fires and 3.8 dev tasks run at capability ceilings (12,000) the
    3.6 arm never had — an undeclared inter-arm delta. The comparison is only
    honest if both arms share the clamp."""
    spec36 = get_model_spec("qwen3.6:27b")
    spec38 = get_model_spec("qwen3.8:27b")
    assert spec38 is not None
    assert spec38.default_max_completion == spec36.default_max_completion == 8_192
    assert spec38.context_window == 262_144

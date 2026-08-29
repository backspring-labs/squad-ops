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
        assert spec.context_window == 65_536
        assert spec.default_max_completion == MODEL_SPECS["qwen3.8:27b"].default_max_completion

    def test_the_atlas_windows_prompt_budget_covers_the_measured_prompts(self):
        """The guard spends ``context_window - default_max_completion`` on the prompt
        and silently drops the prior-analysis section above it (prompt_guard). The
        longest real prompt measured on these weights is 38,210 tokens (#1160 §1.4,
        n=1,145 off the Ollama arm), so a budget below that truncates the Atlas arm
        where the Ollama arm — same weights, 262K served — is never truncated, and
        the A/B reads a serve-line difference as an engine difference. The first
        recipe's 32,768 failed this by 13,634 tokens."""
        spec = MODEL_SPECS["Qwen/Qwen3.8-27B-FP8"]
        assert spec.context_window - spec.default_max_completion >= 38_210

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


class TestThinkingHeadroom:
    """#1173 — the output budget and the declared reasoning level are reconciled.

    `default_max_completion` budgets OUTPUT; its basis in the registry comment is
    wall-clock, not document size. Thinking is billed against the same wire budget
    and then discarded by every adapter. Until #1173 the two were set independently,
    so declaring HIGH silently shrank the answer: replaying a real merge_plan prompt
    three times on the production arm, a complete plan needed ~3,400 output tokens
    while thinking at HIGH cost 4,500 / 6,100 / 7,600 — one attempt in three fit.
    """

    def test_a_capability_that_does_not_think_gets_no_headroom(self):
        """The NONE capabilities are the majority (qa.test, builder.assemble, the
        data family): their budget must not move, or #1173 becomes a latency
        regression across the cycle for no benefit."""
        from squadops.llm.model_registry import thinking_headroom
        from squadops.llm.models import ReasoningLevel

        assert thinking_headroom(ReasoningLevel.NONE) == 0
        assert thinking_headroom(None) == 0

    def test_headroom_rises_with_the_declared_level(self):
        from squadops.llm.model_registry import thinking_headroom
        from squadops.llm.models import ReasoningLevel

        assert (
            thinking_headroom(ReasoningLevel.NONE)
            < thinking_headroom(ReasoningLevel.LOW)
            < thinking_headroom(ReasoningLevel.MEDIUM)
            < thinking_headroom(ReasoningLevel.HIGH)
        )

    def test_high_covers_the_measured_worst_case(self):
        """The number is not arbitrary: on the 27B arm a HIGH capability was
        measured spending 7,600 thinking tokens while its document needed ~3,400.
        Output budget plus HIGH headroom must cover that, or merge_plan keeps
        failing for the reason #1173 was filed about."""
        from squadops.llm.model_registry import MODEL_SPECS, thinking_headroom
        from squadops.llm.models import ReasoningLevel

        spec = MODEL_SPECS["qwen3.8:27b"]
        budget = spec.default_max_completion + thinking_headroom(ReasoningLevel.HIGH)
        assert budget >= 7_600 + 3_400

    def test_a_toggle_model_budgets_every_graded_level_the_same(self):
        """The dial decides, not the declaration. `OllamaAdapter` maps every graded
        level onto one boolean (`think = reasoning != NONE`), so on a TOGGLE model a
        MEDIUM capability thinks exactly as long as a HIGH one. Budgeting it by its
        declaration under-budgets `development.develop` and both repair capabilities
        on the production arm — the very failure #1173 was filed about."""
        from squadops.llm.model_registry import MODEL_SPECS, ReasoningControl, thinking_headroom
        from squadops.llm.models import ReasoningLevel

        spec = MODEL_SPECS["qwen3.8:27b"]
        assert spec.reasoning_control == ReasoningControl.TOGGLE  # premise
        assert thinking_headroom(ReasoningLevel.MEDIUM, spec) == thinking_headroom(
            ReasoningLevel.HIGH, spec
        )
        assert thinking_headroom(ReasoningLevel.MEDIUM, spec) > thinking_headroom(
            ReasoningLevel.MEDIUM
        ), "without the spec the declared level is read; with it, the dial is"

    def test_a_toggle_model_still_spends_nothing_on_none(self):
        """`think: false` is off, so NONE gets no headroom even on a toggle model —
        otherwise the collapse would hand every transcription capability 6k tokens
        it will never use."""
        from squadops.llm.model_registry import MODEL_SPECS, thinking_headroom
        from squadops.llm.models import ReasoningLevel

        assert thinking_headroom(ReasoningLevel.NONE, MODEL_SPECS["qwen3.8:27b"]) == 0

    def test_an_unknown_level_does_not_invent_a_budget(self):
        """A level the table has not been told about falls back to the pre-#1173
        wire, not to a guessed allowance — the same no-masking-fallback rule the
        provider factory follows."""
        from squadops.llm.model_registry import thinking_headroom

        assert thinking_headroom("hyper") == 0

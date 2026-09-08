"""The reasoning declaration and its resolution (#927).

The port carries a level; this is where the level comes from. Two classes of
bug: a capability generating with no declaration (the channel silently on —
#924's condition), and a resolved level reaching a model that cannot take it
(Ollama answers ``think: true`` with a 400 for a model without the channel).
"""

from __future__ import annotations

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.reasoning_policy import (
    REASONING_BY_TASK_TYPE,
    UndeclaredReasoningLevel,
    default_reasoning_level,
    reasoning_kwargs,
    resolve_reasoning_level,
)
from squadops.llm.models import REASONING_LEVELS, ReasoningLevel

pytestmark = [pytest.mark.domain_capabilities]


class TestDeclarations:
    @pytest.mark.parametrize(
        "handler_cls", [cls for cls, _ in HANDLER_CONFIGS], ids=lambda c: c.__name__
    )
    def test_every_registered_handler_declares_a_level(self, handler_cls):
        """A handler registered for dispatch without an entry would generate
        with the model's own posture — reasoning on, unread, unrecorded — which
        is exactly what #924 found on qa.test. This is the CI guard the policy
        module promises."""
        assert handler_cls().task_type in REASONING_BY_TASK_TYPE

    def test_every_declared_level_is_a_known_level(self):
        """A misspelt level ("hgih") would reach Ollama as ``think: true`` and
        vLLM as an invalid effort — neither side rejects it."""
        for task_type, level in REASONING_BY_TASK_TYPE.items():
            assert level in REASONING_LEVELS, task_type

    def test_undeclared_capability_raises_rather_than_defaults(self):
        with pytest.raises(UndeclaredReasoningLevel, match="no.such.capability"):
            default_reasoning_level("no.such.capability")

    def test_the_two_measured_anchors(self):
        """The two ends, and the one that MOVED — both anchored on measurements.

        `development.author_manifest` is #924's argument end and has not moved: stripping
        reasoning there takes it from the one output that chooses endpoints and statuses.

        `builder.assemble` stands in for #924's transcription end. `qa.test` used to, on
        #924's measurement of the qa FILL BRIEF: 413 completion tokens with the channel off
        against 5,727 with it on, the same eight fill fences — a 13.9x saving on an output
        whose answer is already in the prompt. That measurement was right about what it
        measured, and it is why every fill-shaped capability is still `NONE`.

        It moved because `qa.test` is two output shapes under one capability id. Authoring
        a suite from a PRD and a workspace is not transcription, and with the channel off
        the model returned a sentence of intent and stopped: fourteen attempts across the
        1.7.1 counted rolls, five of seven rolls shaped by it, zero in 1.6.6 — which ran
        the same squad on the wire that sent no `think` key at all. Measured live on the
        deployed model with the real prompt (1.7.2 plan §8a): `think: false` produced 1
        usable emission in 6, `think: true` produced 6 in 6.

        **The cost is real and is not hidden by this test.** On the authoring prompt the
        channel roughly doubles completion tokens; on a pure fill brief #924's 13.9x still
        applies, and `qa.test` pays it in fill mode because the declaration is per
        capability. Splitting the level by emission mode is the follow-up (#1285); this is
        the one change the plan's §8 allows, and prediction L1 is what reads it.
        """
        assert REASONING_BY_TASK_TYPE["qa.test"] == ReasoningLevel.MEDIUM
        assert REASONING_BY_TASK_TYPE["qa.test_repair"] == ReasoningLevel.MEDIUM
        assert REASONING_BY_TASK_TYPE["builder.assemble"] == ReasoningLevel.NONE
        assert REASONING_BY_TASK_TYPE["development.author_manifest"] == ReasoningLevel.HIGH


class TestResolution:
    def test_declaration_applies_on_a_switchable_model(self):
        assert (
            resolve_reasoning_level("qa.test", agent_overrides={}, model_name="qwen3.6:27b")
            == ReasoningLevel.MEDIUM
        )
        assert (
            resolve_reasoning_level(
                "builder.assemble", agent_overrides={}, model_name="qwen3.6:27b"
            )
            == ReasoningLevel.NONE
        )

    def test_agent_override_beats_the_declaration(self):
        level = resolve_reasoning_level(
            "qa.test", agent_overrides={"reasoning": "high"}, model_name="qwen3.6:27b"
        )
        assert level == ReasoningLevel.HIGH

    @pytest.mark.parametrize("model", ["qwen2.5:7b", "unregistered:1b", None])
    def test_a_model_without_the_dial_gets_no_level(self, model):
        """qwen2.5 has no channel and Ollama 400s on ``think: true`` for it; an
        unregistered model is #1145's preflight finding, not a guess here; no
        model at all means the adapter's default, whose dial is unknown."""
        assert (
            resolve_reasoning_level(
                "development.author_manifest", agent_overrides={}, model_name=model
            )
            is None
        )

    def test_override_does_not_beat_the_model(self):
        """An operator cannot request reasoning from a model that has none —
        the clamp is the last word, as it is for the completion budget."""
        assert (
            resolve_reasoning_level(
                "qa.test", agent_overrides={"reasoning": "high"}, model_name="qwen2.5:7b"
            )
            is None
        )

    def test_reasoning_kwargs_is_empty_for_nothing_and_one_key_otherwise(self):
        assert reasoning_kwargs(None) == {}
        assert reasoning_kwargs(ReasoningLevel.LOW) == {"reasoning": "low"}


class TestACapabilityWithTwoOutputsDeclaresOneLevelPerOutput:
    """#1285: `qa.test` is two output shapes under one capability id.

    In **fill mode** the shells, the contract and the envelope are all in the prompt and
    the answer is a fixed format — transcription. #924 measured it: 5,727 completion
    tokens with the channel on against 413 with it off, for the same eight fill fences.
    In **authoring mode** the suite is written from a PRD and a workspace, choosing what
    to assert and against which surface — an argument, and with the channel off the model
    returned a sentence of intent and stopped (fourteen attempts across the 1.7.1 counted
    rolls; live, 1 usable emission of 6 with `think: false` against 6 of 6 with it on).

    #1268 moved the capability to MEDIUM for the shape that was failing. That was right,
    and it also made fill mode pay for a channel it does not use.
    """

    def test_fill_mode_declares_no_reasoning(self):
        from squadops.capabilities.reasoning_policy import default_reasoning_level

        assert default_reasoning_level("qa.test", output_shape="fill") == "none"
        assert default_reasoning_level("qa.test_repair", output_shape="fill") == "none"

    def test_authoring_mode_is_unchanged(self):
        """#1268's fix is the reason the authoring level is not touched — the shape that
        was failing keeps exactly what it was given."""
        from squadops.capabilities.reasoning_policy import default_reasoning_level

        assert default_reasoning_level("qa.test") == "medium"
        assert default_reasoning_level("qa.test", output_shape=None) == "medium"

    def test_a_shape_the_capability_does_not_declare_falls_back_to_its_one_level(self):
        """An unknown shape is not an error: the capability has one declaration and it
        applies. A capability that grows a second output adds a row, not a branch."""
        from squadops.capabilities.reasoning_policy import default_reasoning_level

        assert default_reasoning_level("qa.test", output_shape="something_else") == "medium"
        assert default_reasoning_level("development.develop", output_shape="fill") == "medium"

    def test_every_shaped_row_names_a_capability_that_declares_a_single_level_too(self):
        """The per-shape table refines a declaration; it never replaces one. A row for a
        capability absent from the main table would make the fallback raise for its other
        shape, which is the undeclared-level condition this module exists to end."""
        from squadops.capabilities.reasoning_policy import (
            REASONING_BY_OUTPUT_SHAPE,
            REASONING_BY_TASK_TYPE,
        )

        for task_type, _shape in REASONING_BY_OUTPUT_SHAPE:
            assert task_type in REASONING_BY_TASK_TYPE, task_type

    def test_an_agent_override_still_wins_over_the_shaped_declaration(self):
        """The resolution chain is unchanged: declaration → override → the model's dial."""
        from squadops.capabilities.reasoning_policy import resolve_reasoning_level

        assert (
            resolve_reasoning_level(
                "qa.test",
                agent_overrides={"reasoning": "high"},
                model_name="qwen3.6:27b",
                output_shape="fill",
            )
            == "high"
        )


class TestTheHandlerDeclaresItsOwnShape:
    """#1285's wiring. A per-shape declaration the handler never passes is a declaration
    that does nothing — and the shape is the CAPABILITY's fact, not shared code's: reading
    `verification_scaffold` in `_build_chat_kwargs` for everyone broke the manifest
    author's input contract, correctly, and `test_the_author_reads_nothing_outside_its_
    declared_input_contract` is what caught it.
    """

    def _repair_handler(self):
        from squadops.capabilities.handlers.impl.repair_handlers import QATestRepairHandler

        return QATestRepairHandler()

    def test_the_qa_repair_calls_itself_a_fill_when_it_carries_a_scaffold(self):
        assert self._repair_handler()._output_shape({"verification_scaffold": {"files": []}}) == (
            "fill"
        )

    def test_the_qa_repair_without_a_scaffold_declares_no_shape(self):
        assert self._repair_handler()._output_shape({}) is None

    def test_a_single_shape_capability_declares_none(self):
        """Every other handler answers None, so its resolution is byte-for-byte what it
        was — the property that makes this safe to land mid-line."""
        from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler

        assert DevelopmentDevelopHandler()._output_shape({"verification_scaffold": {}}) is None

    def test_the_shaped_kwargs_carry_no_reasoning_for_a_fill_repair(self, monkeypatch):
        """The end of the wire: what `_build_chat_kwargs` actually puts on the call."""
        from types import SimpleNamespace

        monkeypatch.setattr(
            "squadops.capabilities.reasoning_policy.get_model_spec",
            lambda _n: SimpleNamespace(reasoning_control="level", max_completion_tokens=None),
        )
        handler = self._repair_handler()
        fill = handler._build_chat_kwargs(
            {
                "agent_model": "qwen3.6:27b",
                "agent_config_overrides": {},
                "verification_scaffold": {"files": []},
            }
        )
        authoring = handler._build_chat_kwargs(
            {"agent_model": "qwen3.6:27b", "agent_config_overrides": {}}
        )
        assert fill.get("reasoning") in (None, "none"), fill
        assert authoring.get("reasoning") == "medium", authoring

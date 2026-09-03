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
    REASONING_BY_CAPABILITY,
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
        assert handler_cls().capability_id in REASONING_BY_CAPABILITY

    def test_every_declared_level_is_a_known_level(self):
        """A misspelt level ("hgih") would reach Ollama as ``think: true`` and
        vLLM as an invalid effort — neither side rejects it."""
        for capability_id, level in REASONING_BY_CAPABILITY.items():
            assert level in REASONING_LEVELS, capability_id

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
        assert REASONING_BY_CAPABILITY["qa.test"] == ReasoningLevel.MEDIUM
        assert REASONING_BY_CAPABILITY["qa.test_repair"] == ReasoningLevel.MEDIUM
        assert REASONING_BY_CAPABILITY["builder.assemble"] == ReasoningLevel.NONE
        assert REASONING_BY_CAPABILITY["development.author_manifest"] == ReasoningLevel.HIGH


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

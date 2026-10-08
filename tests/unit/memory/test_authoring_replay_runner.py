"""The authoring replay runner (SIP-0110 §0.11; slice 2, #2106), entered at ``replay`` with a proposal
envelope captured as the live agent captures it, the real handler and prompt assets, and a scripted
model.

What bugs would these catch? A case authored before its instrument validity is checked; a memory
arm whose prompt differs from the baseline by more than the lessons; an authoring that records an
envelope or writes anywhere but its own records (isolation); a scheduled arm silently skipped.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from squadops.llm.models import ChatMessage
from squadops.memory.authoring_envelope import envelope_id
from tests.unit.capabilities.test_strategy_propose_increment import _REFERENCE, _fenced
from tests.unit.memory.test_authoring_reconstruct import _captured_envelope, _tools

pytestmark = [pytest.mark.domain_memory]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "authoring_replay.py"
_spec = importlib.util.spec_from_file_location("authoring_replay", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
sys.modules["authoring_replay"] = _module
_spec.loader.exec_module(_module)


class _Model:
    default_model = "m"

    def __init__(self) -> None:
        self.asked = 0

    async def chat_stream_with_usage(self, messages, **kwargs):
        self.asked += 1
        return ChatMessage(role="assistant", content=_fenced(_REFERENCE))


def _payload(envelope: dict, **change) -> dict:
    envelope = {**envelope, "envelope_id": envelope_id(envelope)}
    return {
        "experiment_id": "proposals-v1",
        "cases": [envelope],
        "lessons": [{"revision_id": "pat_a@1", "text": "Name the manifest element it checks."}],
        "case_lessons": {envelope["envelope_id"]: ["pat_a@1"]},
        "static_guidance": "Check the manifest before naming a criterion.",
        "arms": ["baseline", "scoped_memory", "static_guidance"],
        "schedule": [
            [envelope["envelope_id"], "scoped_memory", 0],
            [envelope["envelope_id"], "baseline", 0],
            [envelope["envelope_id"], "static_guidance", 0],
        ],
        **change,
    }


async def test_a_valid_case_is_authored_under_every_scheduled_arm_and_writes_nowhere():
    envelope = await _captured_envelope()
    registry, prompt_service, renderer = _tools()
    model = _Model()

    records = await _module.replay(_payload(envelope), registry, prompt_service, renderer, model)

    [check] = [r for r in records if r["record"] == "validity"]
    authored = [r for r in records if r["record"] == "authoring"]
    assert (check["baseline_exact"], check["memory_differs_only_by_its_section"]) == (True, True)
    assert [r["arm"] for r in authored] == ["scoped_memory", "baseline", "static_guidance"]
    assert all(r["success"] and r["artifacts"] for r in authored)
    assert len({r["calls"][0]["messages_sha256"] for r in authored}) == 3  # three prompts
    assert model.asked == 3


async def test_the_baseline_authoring_records_that_its_call_was_the_captured_prompt():
    """Bug caught: a call record hashed differently from the envelope, so the scored baseline's
    fidelity cannot be read from the records (the exploratory run's first records, #2106); or a
    baseline whose real call is not the capture. Only the baseline claims it."""
    envelope = await _captured_envelope()
    registry, prompt_service, renderer = _tools()

    records = await _module.replay(_payload(envelope), registry, prompt_service, renderer, _Model())

    by_arm = {r["arm"]: r for r in records if r["record"] == "authoring"}
    assert by_arm["baseline"]["calls"][0]["messages_sha256"] == envelope["messages_sha256"]
    assert by_arm["baseline"]["first_call_is_the_capture"] is True
    assert [arm for arm, r in by_arm.items() if "first_call_is_the_capture" in r] == ["baseline"]
    assert by_arm["scoped_memory"]["calls"][0]["messages_sha256"] != envelope["messages_sha256"]


async def test_a_case_whose_reproduction_differs_is_reported_and_never_authored():
    """Bug caught: a replay scored on an envelope whose inputs no longer produce its prompt, so the
    baseline arm authors from a different prompt than the model saw."""
    envelope = await _captured_envelope()
    envelope["inputs"]["prd"] = "## Expansion Tier 1\n1. Something else entirely"
    registry, prompt_service, renderer = _tools()
    model = _Model()

    records = await _module.replay(_payload(envelope), registry, prompt_service, renderer, model)

    [check] = records
    assert (check["record"], check["valid"], check["baseline_exact"]) == ("validity", False, False)
    assert model.asked == 0


async def test_validity_only_checks_without_calling_the_model():
    envelope = await _captured_envelope()
    registry, prompt_service, renderer = _tools()
    model = _Model()

    records = await _module.replay(
        _payload(envelope, validity_only=True), registry, prompt_service, renderer, model
    )

    assert [r["record"] for r in records] == ["validity"] and model.asked == 0

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


# --- skills cases (SIP-0116 §17p) ------------------------------------------------------------

_STOP_LINE = "no scenario: the total shows itself as a sound, which roblox-studio/1 can't observe"


class _SkilledModel:
    """Answers a prompt that shows the scenario skill with ``with_skill``, and any other with the
    reference proposal."""

    default_model = "m"

    def __init__(self, with_skill: str) -> None:
        self.with_skill = with_skill
        self.prompts: list[str] = []

    async def chat_stream_with_usage(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        self.prompts.append(prompt)
        skilled = "Play scenarios for a Roblox game" in prompt
        return ChatMessage(
            role="assistant", content=self.with_skill if skilled else _fenced(_REFERENCE)
        )


def _skills_payload(envelope: dict, **case) -> dict:
    envelope = {**envelope, "envelope_id": envelope_id(envelope) + "#strategy-case"}
    return {
        "experiment_id": "roblox-skills-v1",
        "cases": [envelope],
        "arms": ["baseline", "skills"],
        "schedule": [
            [envelope["envelope_id"], "skills", 0],
            [envelope["envelope_id"], "baseline", 0],
        ],
        "skill_cases": {
            envelope["envelope_id"]: {
                "case": "strategy-case",
                "skillset": "roblox-increment-design",
                "swaps": [],
                **case,
            }
        },
    }


async def test_a_skills_case_is_authored_with_and_without_the_skills_its_cycle_would_hand():
    """Entered at ``replay`` with a captured proposal, the real handler and prompt assets and the
    packaged skillsets. Bug caught: a skills arm that hands the task no skill, or changes its
    prompt elsewhere, so the comparison isn't the skill's."""
    envelope = await _captured_envelope()
    model = _SkilledModel(_fenced(_REFERENCE))

    records = await _module.replay(_skills_payload(envelope), *_tools(), model)

    [check] = [r for r in records if r["record"] == "validity"]
    assert (check["case"], check["capture_checked"], check["valid"]) == (
        "strategy-case",
        True,
        True,
    )
    assert (check["baseline_exact"], check["skills_differ_only_by_their_section"]) == (True, True)
    assert list(check["skills"]) == ["roblox-increment-design/play-scenario-authoring"]
    assert check["prompt_chars"]["skills"] > check["prompt_chars"]["baseline"] > 0
    by_arm = {r["arm"]: r for r in records if r["record"] == "authoring"}
    assert sorted(by_arm) == ["baseline", "skills"]
    assert by_arm["baseline"]["first_call_is_the_capture"] is True
    assert [r["skill_stop"] for r in by_arm.values()] == [None, None]
    assert all(r["success"] and r["case"] == "strategy-case" for r in by_arm.values())
    assert sum("Play scenarios for a Roblox game" in p for p in model.prompts) == 1


async def test_a_skills_arm_answered_with_its_skills_stop_records_the_stop_and_asks_once():
    """Bug caught: the stop lost between ``_llm_call`` and the record, so a stop case can only be
    judged by the handler's failure, which any refusal also produces."""
    envelope = await _captured_envelope()
    model = _SkilledModel(f"`{_STOP_LINE}`")

    records = await _module.replay(_skills_payload(envelope), *_tools(), model)

    by_arm = {r["arm"]: r for r in records if r["record"] == "authoring"}
    assert by_arm["skills"]["success"] is False
    assert by_arm["skills"]["skill_stop"] == {
        "skillset": "roblox-increment-design",
        "skill": "play-scenario-authoring",
        "opening": "no scenario:",
        "line": _STOP_LINE,
    }
    assert len(by_arm["skills"]["calls"]) == 1
    assert (by_arm["baseline"]["success"], by_arm["baseline"]["skill_stop"]) == (True, None)


async def test_a_swapped_case_is_checked_against_its_own_baseline_and_claims_no_capture():
    """Bug caught: a swapped case failing validity because its prompt isn't the capture's (so no
    swapped case could ever run), or its baseline claiming to be the captured prompt."""
    envelope = await _captured_envelope()
    path = ["resolved_config", "campaign_proposal", "objective", "statement"]
    swaps = [{"path": path, "value": "A chime plays when a run is saved."}]
    model = _SkilledModel(_fenced(_REFERENCE))

    records = await _module.replay(_skills_payload(envelope, swaps=swaps), *_tools(), model)

    [check] = [r for r in records if r["record"] == "validity"]
    assert (check["capture_checked"], check["baseline_exact"], check["valid"]) == (
        False,
        None,
        True,
    )
    assert check["skills_differ_only_by_their_section"] is True
    by_arm = {r["arm"]: r for r in records if r["record"] == "authoring"}
    assert "first_call_is_the_capture" not in by_arm["baseline"]
    assert all("A chime plays when a run is saved." in p for p in model.prompts)
    assert len(model.prompts) == 2


@pytest.mark.parametrize(
    ("case", "says"),
    [
        ({"skillset": "roblox-studio-qa"}, "is for qa, not"),
        ({"skillset": "absent"}, "holds no skillset absent"),
        ({"swaps": [{"path": ["absent"], "value": "x"}]}, "hold no absent to swap"),
        ({"vocabulary_skillset": "roblox-studio-qa"}, "hold no product_proposal"),
    ],
    ids=["another-roles-skillset", "unknown-skillset", "a-swap-of-nothing", "nowhere-for-it"],
)
async def test_a_skills_case_that_cant_be_built_is_reported_and_never_authored(case, says):
    """Bug caught: a mistyped case authored anyway, with no skills or with the capture's own
    task, and recorded under the case's name."""
    envelope = await _captured_envelope()
    model = _SkilledModel(_fenced(_REFERENCE))

    records = await _module.replay(_skills_payload(envelope, **case), *_tools(), model)

    [check] = records
    assert (check["record"], check["valid"]) == ("validity", False)
    assert says in check["reason"]
    assert model.prompts == []

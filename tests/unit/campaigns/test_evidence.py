"""A campaign's evidence package and digest (SIP-0109 §14; #1710).

The wiring test enters at ``CampaignProgress.cycle_ended`` — the completion boundary's campaign
call — where a rejected calibration closes the campaign, and reads the vault after it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.continuation import ContinuationDecision, CycleEnding, PendingAction
from squadops.campaigns.evidence import CycleRecords, digest, package, serialized, size_bound
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import CampaignState
from squadops.campaigns.progress import (
    EVIDENCE_ARTIFACT_TYPE,
    CampaignProgress,
    decision_transition,
)
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from tests.unit.campaigns.builders import campaign, move, policy

NOW = datetime(2026, 10, 2, 17, 0, tzinfo=UTC)
CID = "cmp_evid00000001"


def _assessment(cycle_id: str):
    run = RunRecord("run_impl", 1, "implementation", "completed", NOW, NOW)
    outcome = CycleOutcome(
        verdict=RunVerdict.REJECTED,
        verified=(),
        failed=("tests_pass",),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    return assess(
        outcome,
        CycleEvidence(cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_impl",)),
        assessor=AssessorIdentity("2.0.0", None),
    )


class _Vault:
    def __init__(self) -> None:
        self.stored: dict[str, tuple] = {}

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, *, project_id=None, artifact_type=None, **_):
        return [r for r, _ in self.stored.values() if r.artifact_type == artifact_type]


@pytest.fixture
async def closed():
    campaigns, cycles, vault = MemoryCampaignRegistry(), MemoryCycleRegistry(), _Vault()
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=vault,
        assess=AsyncMock(side_effect=_assessment),
        launch=AsyncMock(),
        clock=lambda: NOW + timedelta(hours=1),
    )
    draft = campaign(CID, policy=policy(calibration_profile="framing"))
    await campaigns.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await campaigns.transition(
        CID,
        start_transition(
            draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start"
        ),
    )
    cycle = Cycle(
        cycle_id="cyc_cal",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        campaign_id=CID,
        kind="calibration",
    )
    await cycles.create_cycle(cycle)
    run = Run(
        "run_impl", "cyc_cal", 1, "completed", "system", "cfg", workload_type="implementation"
    )
    await cycles.create_run(run)
    [intent] = await campaigns.pending_launch_intents()
    await campaigns.mark_launch_intent_launched(intent.launch_id, "cyc_cal", actor="l")
    await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    return progress, campaigns, vault


async def test_a_closed_campaign_leaves_its_package_and_digest_once(closed):
    """§14, #1710. Bugs caught: a campaign that closes leaving nothing a frontier reader can
    triage, or a re-materialization storing a second copy of the same records."""
    progress, campaigns, vault = closed

    again = await progress.materialize_package(CID)

    parts = {r.metadata["part"]: (r, c) for r, c in vault.stored.values()}
    doc = json.loads(parts["package"][1])
    assert (await campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert len(vault.stored) == 2
    assert again == (
        doc["identity"],
        parts["package"][0].artifact_id,
        parts["digest"][0].artifact_id,
    )
    assert [c["cycle_id"] for c in doc["cycles"]] == ["cyc_cal"]
    assert doc["cycles"][0]["decision"]["row"] == 2  # a rejected calibration stops the campaign
    assert all(r.artifact_type == EVIDENCE_ARTIFACT_TYPE for r, _ in vault.stored.values())


async def test_the_package_carries_each_runs_revision_forms_from_its_persisted_summary(closed):
    """#1710, entered at ``materialize_package``. Bugs caught: the forms left in the agents' logs,
    which the next rebuild destroys; or a run whose summary predates them read as one that took
    no revision form."""
    from squadops.cycles.llm_usage import RunUsageAccumulator
    from squadops.cycles.run_loop_summary import RunLoopSummary

    progress, _campaigns, vault = closed
    forms = ({"kind": "repair", "task_id": "t-1", "task_type": "qa.test_repair", "form": "edits"},)
    at_close = {
        json.loads(c)["identity"]: json.loads(c)
        for r, c in vault.stored.values()
        if r.metadata["part"] == "package"
    }
    await progress._cycles.record_run_loop_summary(
        "run_impl",
        RunLoopSummary(
            run_id="run_impl", usage=RunUsageAccumulator().summary(), revision_forms=forms
        ),
    )

    identity, _package_id, _digest_id = await progress.materialize_package(CID)

    [(before,)] = [[c["revision_forms"] for c in d["cycles"]] for d in at_close.values()]
    after = {
        json.loads(c)["identity"]: json.loads(c)
        for r, c in vault.stored.values()
        if r.metadata["part"] == "package"
    }[identity]
    assert before == [{"run_id": "run_impl", "workload_type": "implementation", "forms": None}]
    assert after["cycles"][0]["revision_forms"] == [
        {"run_id": "run_impl", "workload_type": "implementation", "forms": list(forms)}
    ]


async def test_the_package_carries_each_runs_lint_reading_from_its_persisted_summary(closed):
    """#1937, entered at ``materialize_package``. Bug caught: the reading left in the qa task's
    reply, which no record keeps; or a run whose summary predates it read as an app with no
    findings."""
    from squadops.cycles.llm_usage import RunUsageAccumulator
    from squadops.cycles.run_loop_summary import RunLoopSummary

    progress, _campaigns, vault = closed
    found = {"task_id": "t-qa", "version": 1, "total": 3, "by_rule": {"ruff:F401": 3}}
    at_close = {
        json.loads(c)["identity"]: json.loads(c)
        for r, c in vault.stored.values()
        if r.metadata["part"] == "package"
    }
    await progress._cycles.record_run_loop_summary(
        "run_impl",
        RunLoopSummary(
            run_id="run_impl", usage=RunUsageAccumulator().summary(), lint_findings=found
        ),
    )

    identity, _package_id, _digest_id = await progress.materialize_package(CID)

    [(before,)] = [[c["lint_findings"] for c in d["cycles"]] for d in at_close.values()]
    after = {
        json.loads(c)["identity"]: json.loads(c)
        for r, c in vault.stored.values()
        if r.metadata["part"] == "package"
    }[identity]
    assert before == [{"run_id": "run_impl", "workload_type": "implementation", "findings": None}]
    assert after["cycles"][0]["lint_findings"] == [
        {"run_id": "run_impl", "workload_type": "implementation", "findings": found}
    ]
    assert after["package_version"] == 3


async def test_the_digest_says_how_the_campaign_ended_and_what_failed(closed):
    _progress, _campaigns, vault = closed

    [text] = [c.decode() for r, c in vault.stored.values() if r.metadata["part"] == "digest"]

    assert f"# Campaign {CID}: completed (failure)" in text
    assert "- nothing was accepted" in text
    assert (
        "| `cyc_cal` | calibration | assessed | rejected | row 2: failure | unattributed |" in text
    )


def test_the_identity_is_the_records_and_moves_with_them():
    """Bug caught: an identity that does not move when a record does — two different packages
    reading as one, and the second never stored."""
    c = campaign(CID)
    one = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "accepted"}, ())])
    same = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "accepted"}, ())])
    other = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "rejected"}, ())])

    assert one["identity"] == same["identity"] != other["identity"]


async def test_an_escalated_campaign_tells_the_owner_what_to_rule():
    registry = MemoryCampaignRegistry()
    await registry.create_campaign(
        campaign(CID), actor="o", actor_role="admin", reason="r", idempotency_key="k"
    )
    await registry.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    stored = await registry.get_campaign(CID)
    await registry.transition(
        CID,
        decision_transition(
            stored,
            ContinuationDecision("cyc_1", 9, action=PendingAction.ESCALATE),
            ending=CycleEnding.ASSESSED,
            verdict=RunVerdict.BLOCKED_UNVERIFIED,
            launch=None,
        ),
    )

    text = digest(
        package(await registry.get_campaign(CID), await registry.control_log(CID), [], [])
    )

    assert "The campaign is escalated (§10 row 9). Resume it naming an action, or abort it." in text


#: The 2.0 counted set's campaign 2 package, exactly as stored at its close (art_032ca67041af).
REAL_PACKAGE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "campaigns" / "package-cmp_97a4a15f360f.json"
)


def _real_package() -> dict:
    return json.loads(REAL_PACKAGE.read_text())


def test_the_digest_says_what_each_increment_shipped_and_how_each_proposal_was_ruled():
    """Read from a real package. Bug caught: the 2.0 set's own digests named each accepted increment
    by its tree hash alone (983 bytes, no feature, no returned proposal), so a morning reader had to
    open the 110 KB package to learn what shipped or what was sent back."""
    text = digest(_real_package())

    assert (
        "- calibration `cyc_6d6b0d848596`: tree `8b03e89612ce`, 26 files\n"
        "- increment `cyc_359d44170982`: tree `1235e7c9db22`, 30 files\n"
        "  - froze T1: A run created with capacity 2 returns that capacity in the response\n"
        "  - froze T2: A third join to a run with capacity 2 is refused with capacity_reached\n"
        "  - froze T3: A run created without a capacity field returns capacity as null\n"
    ) in text
    assert (
        "- `prop_450986544201` v1: returned_for_revision; classified `ambiguous_manifest_delta`\n"
        "- `prop_450986544201` v2: approved\n"
        "- `prop_a9de76329e08` v1: approved\n"
        "- `prop_af32087c5b6e` v1: approved\n"
    ) in text


def test_a_version_at_the_gate_with_no_ruling_reads_as_waiting():
    """Bug caught: a submitted version read as ruled, or left out, while the gate still waits."""
    doc = _real_package()
    doc["control_log"] = [r for r in doc["control_log"] if r["seq"] <= 7]  # up to v1's submit

    text = digest(doc)

    assert "- `prop_450986544201` v1: awaiting a ruling\n" in text
    assert "- `prop_450986544201` v2" not in text


@pytest.mark.parametrize("max_cycles, over", [(9, False), (1, True)])
def test_a_package_past_its_size_bound_is_named_and_kept_whole(max_cycles, over):
    """Bug caught: a size bound that is only a number. The real package (110 KB, four cycles) sits
    inside its nine-cycle bound and outside a one-cycle one, and over the bound the digest says so
    while the package keeps every record."""
    doc = _real_package()
    doc["campaign"]["policy"]["max_cycles"] = max_cycles

    text = digest(doc)

    bound = size_bound(doc["campaign"]["policy"])
    assert f"**Size:** 110 KB of its {bound // 1024} KB bound ({max_cycles} cycles at most)" in text
    assert ("over its" in text) is over


def test_the_size_read_is_the_stored_form():
    """Bug caught: the digest measuring a different serialization than ``materialize_package``
    stores, so the reported size and the bound check drift from the bytes a reader downloads."""
    assert serialized(_real_package()) == REAL_PACKAGE.read_bytes()


@pytest.mark.parametrize(
    ("operation", "binding", "asked"),
    [
        (
            "launch_refused",
            {"launch_id": "lnc_1", "refusal": "PREFLIGHT_REJECTED: model x is not pulled"},
            "the cycle-create path refused launch `lnc_1` (PREFLIGHT_REJECTED: model x is not "
            "pulled). Fix what it names and resume without an action to retry it, or abort.",
        ),
        (
            "launch_blocked",
            {"launch_id": "lnc_2", "attempt": 6, "refusal": "box_held"},
            "the box refused launch `lnc_2` 6 times (box_held). Resume without an action to "
            "retry it, or abort.",
        ),
    ],
    ids=["refused-launch", "blocked-launch"],
)
def test_a_launch_escalation_asks_for_a_resume_without_an_action(operation, binding, asked):
    """#1971. A launch escalation resumes without an action: the launch is still pending, and an
    action would write a second one. Bug caught: the digest telling the owner to name an action,
    and quoting a §10 row that does not exist ("§10 row None")."""
    from squadops.campaigns.evidence import _questions

    [question] = _questions(
        {"state": CampaignState.ESCALATED, "policy": {}},
        [{"operation": operation, "outcome": "applied", "binding": binding}],
    )

    assert question == f"The campaign is escalated: {asked}"

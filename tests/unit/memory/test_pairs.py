"""A paired comparison's arms, read from what each unit pinned and bound (SIP-0110 §3.7, T16).

Bug classes guarded: a pair whose arms were handed different requirements read as valid, so a
difference between their results is credited to the arms when it is the binding's; a campaign
cycle read by its campaign's ``@current`` references instead of its own binding of them (§5ad);
an arm with no snapshot read as one that pinned nothing; and only the first difference named.
Entered at ``read_arm``, as ``memory_exposure_report.py --pair`` calls it, over the in-memory
store and records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.memory.lessons import Snapshot, UnitKind
from squadops.memory.pairs import PairUnreadable, pair_differences, read_arm
from squadops.memory.records import (
    InstructionApplicability,
    PinnedInstruction,
    Reference,
    Revision,
    Source,
    TaskTarget,
    new_record,
)

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
_APPLIES = InstructionApplicability(("development.develop",), ("*",), ("*",))
_CONTRIB = "repo:file:CONTRIBUTING.md"


def _pinned(
    revision: int = 1, commit: str = "433f6c51", digest: str = "sha256:old"
) -> PinnedInstruction:
    return PinnedInstruction(
        record_id="mrec_p16", revision=revision, text="Follow the contributing guide.",
        applicability=_APPLIES,
        references=(Reference(f"{_CONTRIB}@{commit}", True, digest, f"{_CONTRIB}@current"),),
    )  # fmt: skip


def _task(
    record_id: str, cycle_id: str, text: str = "Keep to the guide.", commit: str = "433f6c51"
):
    return new_record(
        record_id=record_id, kind="instruction", scope="task", project_id="prj-shelfnote",
        owner_id="ada",
        revision=Revision(
            number=1, body=text, author="ada", created_at=T0, source=Source("cycle_request"),
            confirmed_by="ada",
            target=TaskTarget(cycle_id=cycle_id, task_types=("development.develop",)),
            references=(
                Reference(f"{_CONTRIB}@{commit}", True, f"sha256:{commit}", f"{_CONTRIB}@current"),
            ),
        ),
    )  # fmt: skip


class _Cycles:
    def __init__(self, campaigns: dict[str, str] | None = None) -> None:
        self._campaigns = campaigns or {}

    async def get_cycle(self, cycle_id: str):
        return SimpleNamespace(cycle_id=cycle_id, campaign_id=self._campaigns.get(cycle_id))


def _subjects(found: list[str]) -> list[str]:
    """What each difference is about: its line before the first ``": "``."""
    return [line.split(": ", 1)[0] for line in found]


async def _arms(store, records, cycles, a="cyc_a", b="cyc_b"):
    ports = {"project_id": "prj-shelfnote", "store": store, "records": records, "cycles": cycles}
    return [await read_arm(c, **ports) for c in (a, b)]


async def _standalone(store, cycle_id: str, *pinned: PinnedInstruction) -> None:
    await store.record_snapshot(
        Snapshot(f"snp_{cycle_id}", UnitKind.CYCLE, cycle_id, T0, False, instructions=pinned)
    )


@pytest.mark.parametrize(
    ("b_pinned", "b_task_commit", "differs"),
    [
        (_pinned(), "433f6c51", []),
        (_pinned(revision=2), "433f6c51", ["project instruction mrec_p16"]),
        (_pinned(commit="0abef4ea", digest="sha256:new"), "433f6c51", [_CONTRIB]),
        (_pinned(), "0abef4ea", [_CONTRIB]),
    ],
    ids=[
        "the-same-bindings",
        "another-revision",
        "a-project-reference-rebound",
        "a-task-reference-rebound",
    ],
)
async def test_a_pair_is_valid_only_when_both_arms_were_handed_the_same_bindings(
    b_pinned, b_task_commit, differs
):
    """T16, live on the Mac: CONTRIBUTING.md changed between two arms' admissions, so one bound it
    at 433f6c51 and the other at 0abef4ea. Bug caught: that pair read as valid."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _standalone(store, "cyc_a", _pinned())
    await _standalone(store, "cyc_b", b_pinned)
    await records.create(_task("mrec_ta", "cyc_a"))
    await records.create(_task("mrec_tb", "cyc_b", commit=b_task_commit))

    found = pair_differences(*await _arms(store, records, _Cycles()))

    assert _subjects(found) == differs


async def test_every_difference_is_named_not_only_the_first():
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _standalone(store, "cyc_a", _pinned())
    await _standalone(store, "cyc_b", _pinned(revision=2, commit="0abef4ea", digest="sha256:new"))
    await records.create(_task("mrec_ta", "cyc_a"))

    found = pair_differences(*await _arms(store, records, _Cycles()))

    assert _subjects(found) == [
        "project instruction mrec_p16",
        "task instruction for development.develop given to cyc_a only",
        _CONTRIB,
    ]


async def test_a_campaign_cycle_is_read_by_its_own_binding_of_its_campaigns_references():
    """§5ad: a campaign's cycles bind its ``@current`` references at their own commits. Bug caught:
    both read by the campaign's snapshot alone, so two cycles bound to different commits read as
    the same."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    current = PinnedInstruction(
        record_id="mrec_p16", revision=1, text="Follow the contributing guide.",
        applicability=_APPLIES, references=(Reference(f"{_CONTRIB}@current", True),),
    )  # fmt: skip
    await store.record_snapshot(
        Snapshot("snp_cmp", UnitKind.CAMPAIGN, "cmp_1", T0, False, instructions=(current,))
    )
    await store.record_cycle_bindings("cyc_a", "campaign", "cmp_1", [_pinned()], T0)
    await store.record_cycle_bindings(
        "cyc_b", "campaign", "cmp_1", [_pinned(commit="0abef4ea", digest="sha256:new")], T0
    )

    found = pair_differences(
        *await _arms(store, records, _Cycles({"cyc_a": "cmp_1", "cyc_b": "cmp_1"}))
    )

    assert _subjects(found) == [_CONTRIB]


async def test_an_arm_with_no_snapshot_is_refused_not_read_as_pinning_nothing():
    """Bug caught: a unit that never pinned read as one that pinned no instruction, so its pair
    with an arm that pinned none read as valid."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _standalone(store, "cyc_a")

    with pytest.raises(PairUnreadable, match="cyc_b"):
        await _arms(store, records, _Cycles())

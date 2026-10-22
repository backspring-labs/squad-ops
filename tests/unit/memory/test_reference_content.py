"""A bound reference's content, read at a dispatch (SIP-0110 Appendix A §3.6; #2179).

Entered where the live composer supplies (``supply_lessons`` through ``SnapshotRecall``), with a
resolver standing in for a family's (the repository's is Project Lifecycle Management's), and at an
authoring handler's real ``handle()`` on the shipped assets, for what the model is shown.
"""

from __future__ import annotations

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.records import Reference, Source
from squadops.memory.task_instructions import (
    TASK_INSTRUCTIONS_INPUT,
    TaskInstructionsUnavailable,
    admitted,
)
from squadops.ports.memory.references import (
    BoundReference,
    ReferenceResolverPort,
    ReferenceUnresolved,
)
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan
from tests.unit.memory.test_project_instructions import DESIGN, T0, _instruction

pytestmark = [pytest.mark.domain_memory]

SPEC = "# The spec\n\nEvery route is named for its resource.\n\n```py\nroute('/runs')\n```\n"


class _Reading(ReferenceResolverPort):
    """A family whose content the test sets, and which can refuse or fail."""

    family = "fake"

    def __init__(self, content: str = SPEC) -> None:
        self.content, self.refuse, self.fail, self.reads = content, None, None, []

    async def bind(self, ref: str, ctx) -> BoundReference:
        return BoundReference(f"{ref.rsplit('@', 1)[0]}@r1", "r1", "sha256:r1")

    async def read(self, bound: BoundReference, ctx) -> str:
        self.reads.append((bound.ref, bound.revision, bound.digest, ctx.project_id))
        if self.refuse:
            raise ReferenceUnresolved(self.refuse)
        if self.fail:
            raise RuntimeError(self.fail)
        return self.content


async def _world(section: str, *, required: bool = True):
    """A cycle whose design task is handed one instruction naming ``fake:doc:spec``: a project
    instruction bound at admission, or a task instruction written with its revision."""
    store, records, resolver = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords(), _Reading()
    cycle = _framing_cycle()
    if section == "project":
        ref = Reference("fake:doc:spec@current", required)
        await records.create(_instruction("mrec_p", DESIGN, references=(ref,)))
    else:
        [record] = admitted(
            [{"text": "Name each run by its route.", "task_types": [DESIGN],
              "references": [{"ref": "fake:doc:spec@r1", "required": required}]}],
            project_id="group_run", cycle_id=cycle.cycle_id, actor="ada", now=T0,
            instructable=lambda t: True, source=Source("cycle_request", {"cycle_id": cycle.cycle_id}),
        )  # fmt: skip
        await records.create(record)
    await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
        pinned_at=T0, disabled=False, records=records, resolvers={"fake": resolver},
    )  # fmt: skip
    return store, records, resolver, cycle


async def _supplied(store, records, resolver, cycle):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(store, records=records, resolvers={"fake": resolver}),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id="run_ref000001", now=T0,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [exposure] = [
        e for e in await store.list_exposures("run_ref000001") if e.query.task_type == DESIGN
    ]
    return design, exposure


_INPUT = {"project": PROJECT_INSTRUCTIONS_INPUT, "task": TASK_INSTRUCTIONS_INPUT}


@pytest.mark.parametrize("section", ["project", "task"])
async def test_the_task_is_shown_the_reference_as_it_reads_at_the_revision_bound(section):
    """Wiring, from the composer to the design author's prompt. Bugs caught: the task handed only a
    reference's name, so the model never sees the record the instruction tells it to follow; the
    content read at whatever the record says now rather than at the revision bound; a file with its
    own fenced block shown in a fence that block closes early."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler
    from tests.unit.campaigns.test_prior_cycle import _rendered

    store, records, resolver, cycle = await _world(section)

    design, _ = await _supplied(store, records, resolver, cycle)

    [instruction] = design.inputs[_INPUT[section]]["instructions"]
    assert [r["content"] for r in instruction["references"]] == [SPEC]
    digest = "sha256:r1" if section == "project" else ""
    assert resolver.reads == [("fake:doc:spec@r1", "r1", digest, "group_run")]
    prompt = await _rendered(
        DevelopmentDesignPlanHandler(), {"prd": "the PRD", "resolved_config": {}, **design.inputs}
    )
    block = "Instruction 1 names fake:doc:spec@r1. At that revision it reads:\n\n````\n" + SPEC
    assert block + "````" in prompt
    assert prompt.index("1. Name each run by its route.") < prompt.index(block)


@pytest.mark.parametrize(
    ("section", "required", "fails", "holds"),
    [
        ("project", True, "refuse", "input"),
        ("project", True, "fail", "store"),
        ("task", True, "refuse", "input"),
        ("project", False, "refuse", None),
    ],
    ids=["required-refused", "required-resolver-failed", "task-required-refused", "optional"],
)
async def test_a_reference_that_cant_be_read(section, required, fails, holds):
    """§3.6. Bugs caught: a task dispatched with a required reference it was never shown; a
    resolver's failure held as the operator's input, so a Campaign's expiry escalates an outage,
    or a refusal held as the store's; an optional one that couldn't be read failing the task, or
    dropped without its exposure saying so."""
    store, records, resolver, cycle = await _world(section, required=required)
    resolver.refuse = (
        "the content at r1 no longer matches the digest bound" if fails == "refuse" else None
    )
    resolver.fail = "the clone is unreachable" if fails == "fail" else None

    if holds:
        with pytest.raises(TaskInstructionsUnavailable, match="can't be read at its bound") as held:
            await _supplied(store, records, resolver, cycle)
        assert {kind for *_, kind in held.value.unresolved} == {holds}
        assert held.value.sections == (f"{section}_instructions",)
        return
    design, exposure = await _supplied(store, records, resolver, cycle)
    [instruction] = design.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    assert instruction["references"] == []
    assert instruction["unread"] == [{"ref": "fake:doc:spec@r1", "why": resolver.refuse}]
    assert exposure.project_instructions["omitted_references"] == [
        {"record_id": "mrec_p", "ref": "fake:doc:spec@r1", "why": resolver.refuse}
    ]


async def test_a_references_content_counts_toward_its_section():
    """§3.6: a binding section's size includes what it references, and it is never cut. Bug
    caught: an instruction that fits handed a reference that doesn't, so the prompt overflows or is
    truncated past the record the task was told to follow."""
    store, records, resolver, cycle = await _world("project")
    resolver.content = "x" * 2_000_000

    with pytest.raises(TaskInstructionsUnavailable, match="project instructions take"):
        await _supplied(store, records, resolver, cycle)


@pytest.mark.parametrize(("required", "status"), [(True, 422), (False, 201)])
def test_a_required_reference_no_resolver_reads_is_refused_at_write(required, status):
    """Bug caught: an instruction naming a required record no resolver can read stored, so every
    task it applies to holds at dispatch for a reason its writer could have fixed when writing it.
    An optional one is stored: a dispatch omits it and says so."""
    from tests.unit.api.test_rebinding import RECORDS, WHERE, _World

    world = _World()
    body = {"kind": "instruction", "scope": "project", "project_id": "group_run",
            "body": "Follow the spec.", "applicability": WHERE,
            "references": [{"ref": "nobody:doc:spec@3", "required": required}]}  # fmt: skip

    response = world.client.post(RECORDS, json=body)

    assert response.status_code == status, response.text
    if status == 422:
        assert (
            "no resolver reads nobody:doc:spec@3" in response.json()["detail"]["error"]["message"]
        )

"""A scenario's fields, named by concept and resolved per delivery (SIP-0113 §10c; #2464).

Deliveries name the same field differently: ``meeting_location`` in most of the canonical stack's,
``location`` in some, ``meetingLocation`` in some of Next.js's (read from the Spark's vault,
2026-10-18). A scenario names the concept, lists the names, and the evaluation service resolves it
against the evaluated delivery's own manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.scenarios import evaluate
from squadops.scenarios.evaluation import BlockedReason, ScenarioResult
from squadops.scenarios.fields import FieldAbsent, resolve
from squadops.scenarios.models import ScenarioInvalid, parse_scenario, parse_suite
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite

T0 = datetime(2026, 10, 18, 23, 0, tzinfo=UTC)
_REFERENCE_MANIFEST = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
LOCATION = {"Run:location": ["meeting_location", "location", "meetingLocation"]}


def _scenario(**change) -> dict:
    return {
        "scenario_id": "a-created-run-reads-back",
        "goal": "A run once created can be read back with where it meets.",
        "surfaces": [{"kind": "http_endpoint", "method": "POST", "path": "/runs"}],
        "steps": [
            {
                "action": "http",
                "method": "POST",
                "path": "/runs",
                "save": {"run": "id"},
                "json": {"title": "Dawn 5k", "@Run:location": "Riverside"},
            },
            {"action": "http", "method": "GET", "path": "/runs/{run}"},
        ],
        "checks": [{"check": "json", "step": 2, "path": "@Run:location", "equals": "Riverside"}],
        "fields": LOCATION,
        **change,
    }


@pytest.mark.parametrize(
    ("declared", "name"),
    [
        ({"meeting_location", "title"}, "meeting_location"),
        ({"location", "title"}, "location"),
        ({"meetingLocation", "location"}, "location"),
    ],
    ids=["the-canonical-stacks-usual", "the-references", "the-first-listed-wins"],
)
def test_a_concept_resolves_to_the_name_the_delivery_declares(declared, name):
    """Bug caught: a create step sending ``location`` to a delivery that declares
    ``meeting_location``, failing at step 1 as though the product couldn't create a run."""
    content = parse_scenario(_scenario()).content()

    resolved = resolve(content, LOCATION, {"Run": declared})

    assert resolved["steps"][0]["json"] == {"title": "Dawn 5k", name: "Riverside"}
    assert resolved["checks"][0]["path"] == name


def test_a_concept_inside_a_dotted_json_path_resolves_as_one_segment():
    """Bug caught: a check reading ``participants.0.@Participant:name`` literally, or the
    concept's colon mistaken for part of the path."""
    fields = {"Participant:name": ["display_name", "name"]}

    resolved = resolve(
        {"path": "participants.0.@Participant:name"}, fields, {"Participant": {"name"}}
    )

    assert resolved == {"path": "participants.0.name"}


def test_a_concept_the_delivery_doesnt_declare_is_absent():
    with pytest.raises(FieldAbsent, match="Run:location"):
        resolve({}, LOCATION, {"Run": {"title"}})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"fields": {}}, "undeclared fields"),
        ({"fields": {**LOCATION, "Run:pace": ["pace"]}}, "unused fields"),
        ({"fields": {"run.location": ["location"]}}, "Entity:concept"),
        ({"fields": {"Run:location": []}}, "lists the names"),
    ],
    ids=["a-reference-not-declared", "a-declaration-not-used", "a-malformed-concept", "no-names"],
)
def test_a_scenarios_fields_must_match_what_it_refers_to(change, message):
    """Bug caught: a concept the steps use with no names to resolve it by, sent literally; or a
    stray declaration the owner approves without anything reading it."""
    with pytest.raises(ScenarioInvalid, match=message):
        parse_scenario(_scenario(**change))


def test_a_scenario_without_fields_keeps_its_content_and_version():
    """Bug caught: every stored scenario's version moving because the content gained an empty
    ``fields`` key, so each approved suite's digest names content nobody approved."""
    plain = {
        k: v
        for k, v in _scenario(
            steps=[{"action": "http", "method": "GET", "path": "/runs"}],
            checks=[{"check": "status", "step": 1, "equals": 200}],
        ).items()
        if k != "fields"
    }

    assert "fields" not in parse_scenario(plain).content()


@dataclass
class _Ref:
    artifact_id: str
    filename: str


class _Vault:
    """The cycle's stored manifest beside its delivered tree, newest first."""

    def __init__(self, manifest: bytes):
        self._files = {"tree": b"app = 1\n", "manifest": manifest}

    async def list_artifacts(self, *, cycle_id):
        return [_Ref("manifest", "interface_manifest.yaml"), _Ref("tree", "backend/main.py")]

    async def retrieve(self, artifact_id):
        return None, self._files[artifact_id]


class _Cycle:
    cycle_id, project_id = "cyc_fields000001", "group_run"

    def resolved_config(self):
        return {"build_profile": "fullstack_fastapi_react"}


class _Runner:
    def __init__(self):
        self.scenarios = None

    async def evaluate_tree(self, **kw):
        self.scenarios = kw["scenarios"]
        return TreeEvaluation(
            kw["tree_identity"],
            started=True,
            runs=tuple(
                ScenarioRun(s["scenario_id"], "passed", steps_taken=2) for s in kw["scenarios"]
            ),
        )


async def test_the_evaluation_resolves_each_scenario_against_the_deliverys_own_manifest(
    monkeypatch,
):
    """The wiring test (#2464): entered at ``evaluate_cycle``, with ``group_run``'s reference
    manifest stored as the cycle's. Bug caught: a concept sent to the runner unresolved; or a
    scenario whose field the delivery doesn't declare run anyway, failing, and read as the
    product's failure rather than a surface it doesn't have."""

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    colour = _scenario(
        scenario_id="a-run-keeps-its-colour",
        steps=[
            {"action": "http", "method": "POST", "path": "/runs", "json": {"@Run:colour": "red"}}
        ],
        checks=[{"check": "status", "step": 1, "equals": 201}],
        fields={"Run:colour": ["colour", "color"]},
    )
    suite = parse_suite({"name": "fields", "scenarios": [_scenario(), colour]})
    store, runner = MemoryScenarioStore(), _Runner()
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=runner,
        # Shaped as a delivery's: every delivered manifest read names the entity ``Run``; only the
        # hand-written reference says ``RunEvent``.
        vault=_Vault(_REFERENCE_MANIFEST.read_bytes().replace(b"RunEvent", b"Run")),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )

    [sent] = runner.scenarios
    assert sent["steps"][0]["json"] == {"title": "Dawn 5k", "location": "Riverside"}
    assert "fields" not in sent
    outcomes = {o.scenario_id: (o.result, o.blocked_reason) for o in record.outcomes}
    assert outcomes == {
        "a-created-run-reads-back": (ScenarioResult.PASSED, None),
        "a-run-keeps-its-colour": (ScenarioResult.BLOCKED_UNVERIFIED, BlockedReason.SURFACE_ABSENT),
    }

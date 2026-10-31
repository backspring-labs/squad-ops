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
from squadops.scenarios.fields import resolve
from squadops.scenarios.models import ScenarioInvalid, parse_scenario, parse_suite
from squadops.scenarios.runner import DeclaredStart, TreeEvaluation
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


@pytest.mark.parametrize(
    ("declared", "name"),
    [
        ({"RunEvent": {"meetingLocation", "title"}, "RunSummary": {"meetingLocation"}}, "meetingLocation"),
        ({"Run": {"location"}, "RunEvent": {"meetingLocation"}}, "location"),
        ({"Event": {"meeting_location"}, "Participant": {"name"}}, "meeting_location"),
        ({}, "meeting_location"),
    ],
    ids=["named-runevent-as-round-7", "an-exact-entity-wins", "named-unrelatedly", "nothing-declared"],
)  # fmt: skip
def test_a_concept_resolves_on_the_entity_the_delivery_named_itself(declared, name):
    """The 2.4 Next.js shakeout's round 7 (``cyc_2ba73ff40024``). Bug caught: a delivery naming its
    run ``RunEvent``, so ``Run:location`` found no entity and went out as ``meeting_location`` to an
    app declaring ``meetingLocation``: every create refused, 12 scenarios failed at step 1."""
    content = parse_scenario(_scenario()).content()

    resolved = resolve(content, LOCATION, declared)

    assert resolved["steps"][0]["json"] == {"title": "Dawn 5k", name: "Riverside"}


def test_a_concept_named_in_a_where_check_resolves_to_the_deliverys_name():
    """#2464: "a created run appears in the list" finds the run by its title and meeting place.
    Bug caught: the ``where`` check's concept key left unresolved, so it looks for a field named
    ``@Run:location`` in every element and fails a delivery that lists the run."""
    where = {
        "check": "json",
        "step": 2,
        "path": "",
        "where": {"title": "Dawn 5k", "@Run:location": "Riverside"},
    }
    content = parse_scenario(_scenario(checks=[where])).content()

    resolved = resolve(content, LOCATION, {"Run": {"meeting_location", "title"}})

    assert resolved["checks"][0]["where"] == {"title": "Dawn 5k", "meeting_location": "Riverside"}


def test_a_concept_inside_a_dotted_json_path_resolves_as_one_segment():
    """Bug caught: a check reading ``participants.0.@Participant:name`` literally, or the
    concept's colon mistaken for part of the path."""
    fields = {"Participant:name": ["display_name", "name"]}

    resolved = resolve(
        {"path": "participants.0.@Participant:name"}, fields, {"Participant": {"name"}}
    )

    assert resolved == {"path": "participants.0.name"}


def test_a_concept_the_delivery_doesnt_declare_is_sent_under_its_first_name():
    """A manifest's fields are a hint (read live: an increment implementing capacity stored no
    manifest, and the one it built on lacked the field). Bug caught: a feature the app has, read
    as a surface it doesn't, so an increment that adds it reads as no change."""
    resolved = resolve({"json": {"@Run:location": "Pier"}}, LOCATION, {"Run": {"title"}})

    assert resolved == {"json": {"meeting_location": "Pier"}}


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


@pytest.mark.parametrize("entity", [b"Run", b"RunEvent"])
async def test_the_evaluation_resolves_each_scenario_against_the_deliverys_own_manifest(
    monkeypatch, entity
):
    """The wiring test (#2464): entered at ``evaluate_cycle``, with ``group_run``'s reference
    manifest stored as the cycle's. Bug caught: a concept sent to the runner unresolved, or a
    concept the manifest doesn't declare kept from the runner, though the app may hold it."""

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
        # A delivery names its own entity: ``Run`` in most, ``RunEvent`` as the reference and the
        # 2.4 Next.js shakeout's round 7 did; either resolves the suite's ``Run`` concepts.
        vault=_Vault(_REFERENCE_MANIFEST.read_bytes().replace(b"RunEvent", entity)),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )

    sent = {s["scenario_id"]: s for s in runner.scenarios}
    assert sent["a-created-run-reads-back"]["steps"][0]["json"] == {
        "title": "Dawn 5k",
        "location": "Riverside",
    }
    assert sent["a-run-keeps-its-colour"]["steps"][0]["json"] == {"colour": "red"}
    assert all("fields" not in s for s in runner.scenarios)
    assert {o.result for o in record.outcomes} == {ScenarioResult.PASSED}


@pytest.mark.parametrize(
    ("stack", "manifest_paths", "outcome"),
    [
        ("fullstack_fastapi_react", b"/runs/{run_id}/join", ScenarioResult.PASSED),
        ("nextjs_ts", b"/api/runs/{run_id}/join", ScenarioResult.PASSED),
        (
            "fullstack_fastapi_react",
            b"/runs/{run_id}/participants",
            ScenarioResult.BLOCKED_UNVERIFIED,
        ),
    ],
    ids=["the-canonical-stack", "nextjs-under-its-prefix", "a-join-at-participants"],
)
async def test_an_endpoint_the_delivery_doesnt_declare_reads_absent_not_failed(
    monkeypatch, stack, manifest_paths, outcome
):
    """#2464: 6 of 38 deliveries take a join at ``/participants``, not ``/join``. Bug caught: a
    join scenario run against one and read as the product failing to join; or a Next.js
    delivery's ``/api`` paths read as missing."""

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    manifest = _REFERENCE_MANIFEST.read_bytes().replace(b"RunEvent", b"Run")
    manifest = manifest.replace(b'"/runs/{run_id}/join"', b'"' + manifest_paths + b'"')
    if stack == "nextjs_ts":
        manifest = manifest.replace(b"path: /runs", b"path: /api/runs").replace(
            b'path: "/runs/', b'path: "/api/runs/'
        )
    join = _scenario(
        scenario_id="a-runner-joins",
        surfaces=[{"kind": "http_endpoint", "method": "POST", "path": "/runs/{run_id}/join"}],
        steps=[
            {"action": "http", "method": "POST", "path": "/runs/r1/join", "json": {"name": "Ada"}}
        ],
        checks=[{"check": "status", "step": 1, "in": [200, 201]}],
        fields={},
    )
    join.pop("fields")
    suite = parse_suite({"name": "endpoints", "scenarios": [join]})
    store, runner = MemoryScenarioStore(), _Runner()
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    class _StackCycle(_Cycle):
        def resolved_config(self):
            return {"build_profile": stack}

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=runner,
        vault=_Vault(manifest),
        cycle=_StackCycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )

    [result] = record.outcomes
    assert result.result is outcome
    if outcome is ScenarioResult.BLOCKED_UNVERIFIED:
        # #2416: the app is still started, for its pages, and the absent scenario isn't sent.
        assert result.blocked_reason is BlockedReason.SURFACE_ABSENT and runner.scenarios == []


async def test_a_declared_project_resolves_by_the_suites_names_and_reads_no_manifest(monkeypatch):
    """SIP-0112 §8.3 item 2: an external product has no interface manifest, so a declared
    Project's concept goes under the suite's first name and its endpoints aren't checked. Bug
    caught: a sample app's manifest, stored beside the tree, read for a declared Project, so its
    field names (``location``) and its endpoints (none at ``/runs``) decide what an unrelated
    product is sent and whether its scenarios run."""

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    manifest = _REFERENCE_MANIFEST.read_bytes().replace(b"RunEvent", b"Run")
    vault = _Vault(manifest.replace(b"path: /runs", b"path: /elsewhere"))
    listed: list = []
    real_list = vault.list_artifacts

    async def list_artifacts(*, cycle_id):
        listed.append(cycle_id)
        return await real_list(cycle_id=cycle_id)

    vault.list_artifacts = list_artifacts
    suite = parse_suite({"name": "declared", "scenarios": [_scenario()]})
    store, runner = MemoryScenarioStore(), _Runner()
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=runner,
        vault=vault,
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
        declared=DeclaredStart(
            start=("./serve",),
            port=8080,
            ready_kind="tcp",
            ready_path="",
            ready_timeout_seconds=30,
            api_port=8080,
        ),
        served=evaluate.declared_surfaces([{"kind": "http_base"}]),
    )

    [sent] = runner.scenarios
    assert sent["steps"][0]["json"] == {"title": "Dawn 5k", "meeting_location": "Riverside"}
    assert sent["checks"][0]["path"] == "meeting_location"
    assert listed == []
    assert [o.result for o in record.outcomes] == [ScenarioResult.PASSED]


@pytest.mark.parametrize(
    "stored",
    [b"version: 1\nentities: []\n", b"- not\n- a mapping\n", b"key: [unclosed\n", b"\xff\xfe"],
    ids=["missing-keys", "not-a-mapping", "bad-yaml", "not-utf-8"],
)
async def test_a_manifest_that_cant_be_read_still_gets_its_record(monkeypatch, stored):
    """The record is written whatever happened (the service's rule 5). Bug caught: a delivery's
    own malformed manifest raising out of the evaluation, so the hook at a cycle's end logs it and
    the increment has no record; read live when #2467 met the campaign hook's fixture."""

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    suite = parse_suite({"name": "unreadable", "scenarios": [_scenario()]})
    store, runner = MemoryScenarioStore(), _Runner()
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=runner,
        vault=_Vault(stored),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )

    [sent] = runner.scenarios
    assert sent["steps"][0]["json"] == {"title": "Dawn 5k", "meeting_location": "Riverside"}
    assert await store.evaluations_for_cycle(_Cycle.cycle_id) == [record]

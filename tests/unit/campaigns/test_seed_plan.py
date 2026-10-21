"""The seeded quality reading's planner (SIP-0113 §10j, §10n; #2562), on real deliveries'
manifests: the 2.4 window's FastAPI increment (an API under ``base_path: /api``, endpoints written
without it) and the 2.1 rebuild's Next.js app (endpoints written under ``/api``, no base path).

What bugs would these catch?
- a seed request sent to a path the app doesn't serve: the base added to a path the backend serves
  at its root, or a Next.js prefix dropped;
- a seed value placed under a field the request doesn't take, or an aliased one dropped silently;
- every member joining the first record, so no run reaches its capacity;
- a parameterised page measured once with "the first record", or keyed by a filled URL that differs
  on every instance, so no two trees' pages ever compare;
- one record's refusal voiding the whole seed;
- a route the seed can't fill measured anyway, or silently left out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from squadops.campaigns import seed_plan
from squadops.campaigns.seed_plan import SeededPage, SeedRefused
from squadops.stacks.scaffold import InterfaceManifest

ROOT = Path(__file__).resolve().parents[3]
REPLAYS = ROOT / "tests/fixtures/roll_replays"
SEED = ROOT / "examples/03_group_run/quality_seed.json"


def _manifest(name: str, **routes_extra) -> InterfaceManifest:
    doc = yaml.safe_load((REPLAYS / name).read_text(encoding="utf-8"))
    for path in routes_extra.get("routes", ()):
        doc["frontend"]["routes"].append({"path": path, "view": "Extra", "testids": []})
    return InterfaceManifest.from_dict(doc)


def _seed(**change) -> tuple[dict, bytes]:
    doc = json.loads(SEED.read_bytes())
    doc.update(change)
    raw = json.dumps(doc).encode()
    return doc, raw


FASTAPI = "2-4-0-window-c1-increment-2-interface_manifest.yaml"
NEXTJS = "2-1-0-rebuild2-nextjs-interface_manifest.yaml"


@pytest.mark.parametrize(
    ("manifest", "create", "join", "route"),
    [
        (FASTAPI, "/runs", "/runs/{run_id}/join", "/runs/:run_id"),
        (NEXTJS, "/api/runs", "/api/runs/{run_id}/join", "/runs/{run_id}"),
    ],
    ids=["fastapi-under-a-base-path", "nextjs-under-a-written-prefix"],
)
def test_the_seed_is_written_through_each_deliverys_own_endpoints(manifest, create, join, route):
    """Each record is created at the path the manifest writes, with its values under the shape's
    names (``location`` as ``meeting_location``), and its own members join it at the member
    action's path, its parameter kept for the record's id."""
    doc, raw = _seed()

    plan = seed_plan.plan(_manifest(manifest), doc, raw)

    partial, at_capacity, unjoined = plan.records
    assert [r.label for r in plan.records] == ["partial", "at_capacity", "unjoined"]
    assert {r.create.path for r in plan.records} == {create}
    assert partial.create.json["meeting_location"] == "Harbor footbridge, north end"
    assert [m.json for m in at_capacity.members] == [
        {"name": "Wrenna"}, {"name": "Calloway"}, {"name": "Ines"}
    ]  # fmt: skip
    assert {m.path for m in partial.members + at_capacity.members} == {join}
    assert unjoined.members == ()
    assert plan.unfilled == () and plan.refused == ()
    assert [p for p in plan.pages if p.record] == [
        SeededPage(route, "partial", route.split("/")[-1]),
        SeededPage(route, "at_capacity", route.split("/")[-1]),
    ]


def test_a_parameterised_page_is_keyed_by_its_route_and_record_never_its_filled_url():
    """Two trees that spell the parameter apart, and two instances whose ids differ, compare."""
    doc, raw = _seed()
    fastapi = seed_plan.plan(_manifest(FASTAPI), doc, raw)
    nextjs = seed_plan.plan(_manifest(NEXTJS), doc, raw)

    keys = {p.key for p in fastapi.pages if p.record}

    assert (
        keys
        == {p.key for p in nextjs.pages if p.record}
        == {
            "/runs/{id}#partial",
            "/runs/{id}#at_capacity",
        }
    )
    page = next(p for p in fastapi.pages if p.record == "partial")
    assert seed_plan.fill(page.route, page.segment, "r-41") == "/runs/r-41"
    assert fastapi.version == f"seed:{seed_plan.seed_sha256(raw)[:12]}:plan-v1"


def test_a_value_no_field_takes_is_a_note_never_dropped_silently():
    """The Next.js app's create takes no ``capacity``: the seed still writes, and says so."""
    doc, raw = _seed()

    plan = seed_plan.plan(_manifest(NEXTJS), doc, raw)

    assert "partial: capacity dropped, not a field of RunCreate" in plan.notes
    assert "capacity" not in plan.records[0].create.json


def test_a_record_the_interface_cant_take_is_refused_alone_and_its_pages_say_so():
    """§10n ruling 7: a record missing a required field is refused; the others are written, and
    the pages it would have filled read ``seed_refused``."""
    doc, raw = _seed()
    doc["records"][1]["values"].pop("datetime")

    plan = seed_plan.plan(_manifest(FASTAPI), doc, raw)

    assert [r.label for r in plan.records] == ["partial", "unjoined"]
    assert [label for label, _ in plan.refused] == ["at_capacity"]
    assert "requires 'datetime'" in plan.refused[0][1]
    assert ("/runs/:run_id#at_capacity", seed_plan.SEED_REFUSED) in plan.unfilled


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"create": ["POST /races"]}, "none of the seed's create endpoints"),
        (
            {"member_action": ["POST /runs/{id}/cheer"]},
            "none of the seed's member action endpoints",
        ),
    ],
    ids=["no-create-declared", "no-member-action-declared"],
)
def test_a_seed_the_interface_cant_take_at_all_is_refused(change, why):
    """§10j's ``seed_refused``, before any request is sent."""
    doc, raw = _seed(**change)

    with pytest.raises(SeedRefused, match=why):
        seed_plan.plan(_manifest(FASTAPI), doc, raw)


def test_a_route_the_seed_cant_fill_reads_no_seed_value_and_the_rest_are_measured():
    """A route with two parameters, or one the seed names no record for, is listed with why,
    never measured with a guessed id, and never silently left out."""
    doc, raw = _seed()
    manifest = _manifest(FASTAPI, routes=["/runs/:run_id/members/:member_id", "/clubs/:club_id"])

    plan = seed_plan.plan(manifest, doc, raw)

    assert ("/runs/:run_id/members/:member_id", seed_plan.NO_SEED_VALUE) in plan.unfilled
    assert ("/clubs/:club_id", seed_plan.NO_SEED_VALUE) in plan.unfilled
    assert [p.route for p in plan.pages if p.record is None] == ["/", "/create"]


def test_a_seed_file_not_in_the_labelled_shape_is_refused():
    """The release screenshots' seed (unlabelled records, one global member list) isn't a quality
    seed: read as one, every member would join the first run."""
    screenshots = (ROOT / "examples/03_group_run/screenshot_seed.json").read_bytes()

    with pytest.raises(SeedRefused, match="a quality seed is"):
        seed_plan.load(screenshots)
    assert seed_plan.load(SEED.read_bytes())["records"][0]["label"] == "partial"

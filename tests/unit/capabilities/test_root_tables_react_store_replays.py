"""#1087 (stack #1 half) / #1112 — the React store replayed against stored manifests.

The rule is unit-tested in ``test_root_persisted_entities.py``; this file runs the frozen
``backend/store.py`` the React expander emits against the manifests real rolls framed, so
each expectation names the tables a roll actually handed its authors and what changes.

Bug classes guarded: a shape or projection getting a store (the 1.6.6 rolls' texture — three
stores kept in sync by hand on roll 4); a genuine root losing its store (roll 6 / the
reference, which must not move except by the one dropped shape); the routes stub importing
a name the store no longer defines (an ImportError on the frozen skeleton); the dev brief
naming a handle the module does not export.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadops.capabilities import stack_fastapi_react
from squadops.capabilities.scaffold import (
    InterfaceManifest,
    expand,
    model_surface_instructions,
    root_persisted_entities,
)

pytestmark = [pytest.mark.domain_capabilities]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _manifest(name: str) -> InterfaceManifest:
    return InterfaceManifest.from_yaml((_FIXTURES / name).read_text(encoding="utf-8"))


def _expanded(manifest: InterfaceManifest) -> dict[str, str]:
    return {f["name"]: f["content"] for f in expand(manifest)}


def _stores(store_py: str) -> list[str]:
    return re.findall(r"^(\w+_store): dict\[str, \w+\] = \{\}$", store_py, re.M)


@pytest.mark.parametrize(
    ("fixture", "stores", "shapes"),
    [
        # 1.6.6 roll 1 (accepted): Participant is Run.participants' element, RunSummary the
        # list projection — both had a store; the fills touched neither.
        (
            "1-6-6-react-roll-1-interface_manifest.yaml",
            ["run_store"],
            "Participant, RunSummary",
        ),
        # 1.6.6 roll 3 (rejected on other grounds): JoinResult {id, participants} is Run
        # after a join — a projection; LeaveResult carries `removed`, which nothing else
        # declares, so it is not provably a shape and keeps its store (the #1112 edge that
        # remains, stated). The fill wrote join_result_store[run_id] = result once.
        (
            "1-6-6-react-roll-3-interface_manifest.yaml",
            ["run_store", "leave_result_store"],
            "RunSummary, JoinResult",
        ),
        # 1.6.6 roll 4 (accepted, green by repair): the create returned Run {…,
        # participant_count}, the read-by-id RunDetail {…, participants}; the fill kept
        # run_store, run_detail_store and participant_store in sync by hand. The detail is
        # the row; Run is it without its participants.
        (
            "1-6-6-react-roll-4-interface_manifest.yaml",
            ["run_detail_store"],
            "Run, Participant",
        ),
        # 1.7.0 roll 6 (the gating roll): Run created and read by id; Participant embedded.
        (
            "1-7-0-react-roll-6-interface_manifest.yaml",
            ["run_store"],
            "Participant",
        ),
    ],
)
def test_the_frozen_store_exports_a_dict_per_root_and_names_the_shapes(fixture, stores, shapes):
    manifest = _manifest(fixture)
    files = _expanded(manifest)
    store = files["backend/store.py"]

    assert _stores(store) == stores
    assert f"never rows themselves: {shapes}." in store
    compile(store, "backend/store.py", "exec")
    # reset() clears exactly the stores that exist — no stale `.clear()` on a dropped name.
    assert re.findall(r"^    (\w+_store)\.clear\(\)$", store, re.M) == stores


@pytest.mark.parametrize(
    "fixture",
    [
        "1-6-6-react-roll-1-interface_manifest.yaml",
        "1-6-6-react-roll-3-interface_manifest.yaml",
        "1-6-6-react-roll-4-interface_manifest.yaml",
        "1-7-0-react-roll-6-interface_manifest.yaml",
    ],
)
def test_the_routes_stub_and_the_brief_name_only_the_stores_the_module_defines(fixture):
    """A frozen stub importing a name the store dropped would fail at import — before any
    fill — and a brief naming it would send the developer to a handle that is not there."""
    manifest = _manifest(fixture)
    files = _expanded(manifest)
    defined = set(_stores(files["backend/store.py"]))

    (import_line,) = [ln for ln in files["backend/routes.py"].splitlines() if ".store import" in ln]
    imported = {name.strip() for name in import_line.split("import", 1)[1].split(",")}
    assert imported == defined

    brief = " ".join(model_surface_instructions(manifest))
    assert set(re.findall(r"`(\w+_store)`", brief)) == defined
    for name in root_persisted_entities(manifest):
        assert f"`{stack_fastapi_react._snake(name)}_store`" in brief


def test_roll_4s_stored_fill_imported_two_stores_no_correct_app_needs():
    """The evidence for the rule, from the vault: 1.6.6 roll 4's final ``backend/routes.py``
    (``art_a8c0cdaa1b93``) imports three stores and keeps them in sync by hand — a
    ``participant_store`` keyed by a composite string and a ``run_store`` mirrored from the
    detail on every join and leave. Under the root-table store two of the three names do
    not exist, so the same fill fails at import with the real store named, instead of
    persisting one run three ways."""
    fill = (_FIXTURES / "1-6-6-react-roll-4-routes-fill.py.txt").read_text(encoding="utf-8")
    manifest = _manifest("1-6-6-react-roll-4-interface_manifest.yaml")
    store = _expanded(manifest)["backend/store.py"]

    (import_line,) = [ln for ln in fill.splitlines() if ln.startswith("from .store import")]
    imported = [name.strip() for name in import_line.split("import", 1)[1].split(",")]
    assert imported == ["run_store", "run_detail_store", "participant_store"]
    assert "run_store[run_id].participant_count = run_detail.participant_count" in fill
    assert "participant_store[part_key] = participant" in fill

    defined = set(_stores(store))
    assert defined == {"run_detail_store"}
    assert sorted(set(imported) - defined) == ["participant_store", "run_store"]

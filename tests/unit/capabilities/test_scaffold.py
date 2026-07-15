"""Tests for the contract-first scaffold expander (SIP-Contract-First-Build-Scaffolding).

These assert the two load-bearing properties of the Phase-0.5 spike: the manifest
parses into the typed contract, and the expander materializes a *wired* skeleton
(App.jsx imports the views it routes to; routes.py defines every declared endpoint;
the generated Python is syntactically valid). The build+boot proof is a separate
CI/local gate; these guard the expander logic itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest, expand

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _group_run_manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _by_name(files: list[dict[str, str]]) -> dict[str, str]:
    return {f["name"]: f["content"] for f in files}


def test_parses_group_run_manifest_structure():
    m = _group_run_manifest()

    assert [e.name for e in m.entities] == ["Participant", "RunEvent"]
    run_event = next(e for e in m.entities if e.name == "RunEvent")
    assert [f.name for f in run_event.fields] == [
        "id",
        "title",
        "datetime",
        "location",
        "distance",
        "pace_target",
        "route_notes",
        "participants",
    ]
    # participants is a list-of-entity with a [] default; distance is optional
    participants = next(f for f in run_event.fields if f.name == "participants")
    assert participants.type == "list[Participant]"
    assert participants.has_default is True
    assert next(f for f in run_event.fields if f.name == "distance").required is False

    assert {(e.method, e.path) for e in m.api.endpoints} == {
        ("GET", "/runs"),
        ("POST", "/runs"),
        ("GET", "/runs/{id}"),
        ("POST", "/runs/{id}/join"),
        ("POST", "/runs/{id}/leave"),
    }
    assert [r.view for r in m.frontend.routes] == [
        "RunsListView",
        "CreateRunView",
        "RunDetailView",
    ]
    assert m.persistence == "in_memory"


def test_expand_wires_frontend_routes_to_view_imports():
    files = _by_name(expand(_group_run_manifest()))

    app = files["frontend/src/App.jsx"]
    # Every routed view must be imported AND routed — the exact #376 regression
    # (App.jsx rendered inline stubs and imported nothing) is structurally impossible.
    for view in ("RunsListView", "CreateRunView", "RunDetailView"):
        assert f"import {view} from './views/{view}.jsx'" in app
        assert f"element={{<{view} />}}" in app
        assert f"frontend/src/views/{view}.jsx" in files
        assert f"export default function {view}()" in files[f"frontend/src/views/{view}.jsx"]

    assert '<Route path="/" element={<RunsListView />} />' in app
    assert '<Route path="/runs/:id" element={<RunDetailView />} />' in app


def test_expand_defines_every_declared_endpoint_and_model():
    files = _by_name(expand(_group_run_manifest()))

    routes = files["backend/routes.py"]
    assert '@router.get("/runs", response_model=list[RunEvent])' in routes
    assert '@router.post("/runs", response_model=RunEvent)' in routes
    assert '@router.post("/runs/{id}/join", response_model=RunEvent)' in routes
    assert "payload: RunEventCreate" in routes
    assert "payload: ParticipantName" in routes
    # only referenced models are imported (no unused-import lint failure)
    assert "from .models import ParticipantName, RunEvent, RunEventCreate" in routes

    models = files["backend/models.py"]
    assert "class Participant(BaseModel):" in models
    assert "class RunEvent(BaseModel):" in models
    assert "participants: list[Participant] = Field(default_factory=list)" in models
    assert "distance: str | None = None" in models

    main = files["backend/main.py"]
    assert '@app.get("/health")' in main
    assert "app.include_router(router)" in main


def test_generated_python_is_syntactically_valid():
    files = _by_name(expand(_group_run_manifest()))
    for name, content in files.items():
        if name.endswith(".py"):
            compile(content, name, "exec")  # raises SyntaxError on a bad template


def test_output_matches_materialize_artifacts_contract():
    # Every entry must be a {name, content} pair with a relative name — the shape
    # patch_verification.materialize_artifacts consumes; an absolute name is dropped.
    for f in expand(_group_run_manifest()):
        assert set(f) == {"name", "content"}
        assert f["name"] and not Path(f["name"]).is_absolute()
        assert isinstance(f["content"], str)


def test_unknown_stack_raises():
    m = _group_run_manifest()
    bad = InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )
    with pytest.raises(ValueError, match="no scaffold expander"):
        expand(bad)
    # sanity: the real stack does resolve
    assert expand(m)


def test_missing_required_key_raises():
    with pytest.raises(ValueError, match="missing required keys"):
        InterfaceManifest.from_dict({"version": 1, "kind": "interface_manifest"})

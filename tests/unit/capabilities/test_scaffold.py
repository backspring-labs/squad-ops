"""Tests for the contract-first scaffold expander (SIP-Contract-First-Build-Scaffolding).

These assert the two load-bearing properties of the Phase-0.5 spike: the manifest
parses into the typed contract, and the expander materializes a *wired* skeleton
(App.jsx imports the views it routes to; routes.py defines every declared endpoint;
the generated Python is syntactically valid). The build+boot proof is a separate
CI/local gate; these guard the expander logic itself.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from squadops.capabilities.handlers.build_profiles import get_profile
from squadops.capabilities.scaffold import InterfaceManifest, expand

pytestmark = [pytest.mark.domain_capabilities]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"


def _group_run_manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _raw_manifest() -> dict:
    return yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_materialize_module():
    """Import scripts/dev/materialize_skeleton.py by path (scripts/ is not a package)."""
    path = _REPO_ROOT / "scripts" / "dev" / "materialize_skeleton.py"
    spec = importlib.util.spec_from_file_location("materialize_skeleton", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_expand_renders_pinned_error_contract():
    # The manifest pins {"error": {code, message}} incl. validation_error -> 422,
    # which FastAPI's default would render as {"detail": [...]} before any body
    # runs — so the renderer + RequestValidationError handler are scaffold-owned.
    files = _by_name(expand(_group_run_manifest()))

    errors = files["backend/errors.py"]
    assert '"run_not_found": 404,' in errors
    assert '"duplicate_participant": 409,' in errors
    assert '"validation_error": 422,' in errors
    assert '"participant_not_found": 404,' in errors
    assert 'return {"error": {"code": code, "message": message}}' in errors
    assert "class ApiError(Exception):" in errors
    assert "RequestValidationError" in errors  # the framework-level 422 is overridden

    main = files["backend/main.py"]
    assert "from .errors import register_error_handlers" in main
    assert "register_error_handlers(app)" in main

    # route stubs steer the fill dev at ApiError with the real codes, and the seam
    # import is wired into the frozen stub so import_present(ApiError) is valid interface
    routes = files["backend/routes.py"]
    assert "from .errors import ApiError" in routes
    assert "raise ApiError(code, message) from .errors" in routes


def test_expand_emits_api_client_prefixing_api():
    # vite.config strips /api before forwarding, so views MUST call /api/... to
    # reach the backend — the client encodes that so a fill dev never guesses.
    files = _by_name(expand(_group_run_manifest()))
    api = files["frontend/src/api.js"]
    assert "export async function apiFetch(path, options = {})" in api
    assert "fetch(`/api${path}`" in api
    assert "body.error" in api  # unwraps the pinned envelope
    assert "class ApiError extends Error" in api
    assert "apiFetch from '../api.js'" in files["frontend/src/views/RunsListView.jsx"]


# --------------------------------------------------------------------------- #
# 99.1 canonicalization: schema v1 freeze, content hash, profile seam
# --------------------------------------------------------------------------- #


def test_content_hash_is_sha256_hex():
    # SIP-0098's contract linter requires interface_manifest_hash to be a 64-char
    # sha256 hex digest; this proves the hash 99.1 produces satisfies that shape,
    # so the two phases interlock at 98.2's binding.
    h = _group_run_manifest().content_hash()
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_is_order_independent_for_mapping_keys():
    raw = _raw_manifest()
    reordered = {k: raw[k] for k in reversed(list(raw))}  # same content, keys reversed
    assert (
        InterfaceManifest.from_dict(reordered).content_hash()
        == InterfaceManifest.from_dict(raw).content_hash()
    )


def test_content_hash_ignores_provenance_but_tracks_interface():
    h = _group_run_manifest().content_hash()

    # provenance-only edits must NOT move the hash — else a re-pointed PRD would
    # spuriously invalidate the verification contract bound to it (SIP-0098 §10).
    prov = dict(_raw_manifest(), source_prd="totally/different.md", scope="rewritten")
    assert InterfaceManifest.from_dict(prov).content_hash() == h

    # an interface change DOES move it, so real drift is detectable, not masked.
    changed = _raw_manifest()
    changed["api"]["endpoints"].append({"method": "DELETE", "path": "/runs/{id}"})
    assert InterfaceManifest.from_dict(changed).content_hash() != h


def test_from_dict_rejects_unsupported_version():
    raw = dict(_raw_manifest(), version=2)
    with pytest.raises(ValueError, match="unsupported interface manifest version"):
        InterfaceManifest.from_dict(raw)


def test_from_dict_rejects_wrong_kind():
    raw = dict(_raw_manifest(), kind="pcr_manifest")
    with pytest.raises(ValueError, match="kind must be"):
        InterfaceManifest.from_dict(raw)


def test_build_profile_expand_delegates_to_scaffold():
    # The profile is the executor's seam (99.3); it must add no transformation of
    # its own — a byte-for-byte match with the pure expander.
    m = _group_run_manifest()
    via_profile = get_profile("fullstack_fastapi_react").expand(m)
    assert via_profile == expand(m)
    assert {f["name"] for f in via_profile} >= {"backend/main.py", "frontend/src/App.jsx"}


def test_build_profile_expand_surfaces_unknown_stack():
    bad = InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )
    with pytest.raises(ValueError, match="no scaffold expander"):
        get_profile("fullstack_fastapi_react").expand(bad)


def test_materialize_writes_every_expanded_file(tmp_path):
    mod = _load_materialize_module()
    count = mod.materialize(_MANIFEST_PATH, tmp_path)

    expected = {f["name"] for f in expand(_group_run_manifest())}
    written = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()}
    assert written == expected
    assert count == len(expected)
    # content lands verbatim (spot-check the wired entrypoint)
    assert "app.include_router(router)" in (tmp_path / "backend" / "main.py").read_text()


def test_materialize_refuses_path_traversal(tmp_path, monkeypatch):
    # Defense-in-depth: even if a future expander emitted an escaping name, the
    # materializer must refuse to write outside the target root.
    mod = _load_materialize_module()
    monkeypatch.setattr(mod, "expand", lambda _m: [{"name": "../escape.txt", "content": "x"}])
    with pytest.raises(ValueError, match="refusing to write outside"):
        mod.materialize(_MANIFEST_PATH, tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()


# --------------------------------------------------------------------------- #
# 99.2: InterfaceManifest.lint — the malformed/incomplete net for framing emissions
# --------------------------------------------------------------------------- #


def test_lint_accepts_the_group_run_manifest():
    assert _group_run_manifest().lint() == []


def test_lint_rejects_manifest_with_no_endpoints():
    raw = _raw_manifest()
    raw["api"]["endpoints"] = []
    assert any("at least one endpoint" in e for e in InterfaceManifest.from_dict(raw).lint())


def test_lint_rejects_endpoint_with_undeclared_request_shape():
    raw = _raw_manifest()
    raw["api"]["endpoints"][1]["request"] = "NopeShape"  # POST /runs
    errors = InterfaceManifest.from_dict(raw).lint()
    assert any("request 'NopeShape' is not a declared request_shape" in e for e in errors)


def test_lint_rejects_response_naming_an_undeclared_entity():
    raw = _raw_manifest()
    raw["api"]["endpoints"][1]["response"] = "RunEvnt"  # typo of RunEvent
    errors = InterfaceManifest.from_dict(raw).lint()
    assert any("response references undeclared entity 'RunEvnt'" in e for e in errors)


def test_lint_rejects_route_without_view():
    raw = _raw_manifest()
    raw["frontend"]["routes"][0]["view"] = ""
    assert any("view is required" in e for e in InterfaceManifest.from_dict(raw).lint())


def test_lint_rejects_unscaffoldable_stack_and_empty_manifest():
    # a bare manifest with an unknown stack: flagged for both the missing expander and
    # the absent endpoints (framing produced something unusable)
    m = InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )
    errors = m.lint()
    assert any("no scaffold expander" in e for e in errors)
    assert any("at least one endpoint" in e for e in errors)


# --------------------------------------------------------------------------- #
# Prototype proof (import-convention pieces 1-2): the scaffold seeds a consistent
# import root so a qa suite runs against the materialized skeleton with no import
# guessing — the pf-26 wall (files under backend/ but the test invented
# `from app.main import app`) removed AT THE SCAFFOLD.
# --------------------------------------------------------------------------- #


def test_scaffold_seeds_consistent_import_root_for_tests(tmp_path):
    """A qa-style suite authored against the scaffold's seeded ``client`` fixture
    COLLECTS AND RUNS against the freshly-materialized walking skeleton — no
    ModuleNotFoundError. The suite never imports the app itself; the frozen
    ``conftest.py`` owns the import root (sys.path anchor + ``client`` fixture)."""
    import subprocess
    import sys

    # Materialize the walking skeleton exactly as patch_verification would.
    for f in expand(_group_run_manifest()):
        p = tmp_path / f["name"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["content"])

    # A qa suite that uses the seeded `client` fixture and never authors an app import.
    test_dir = tmp_path / "backend" / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_smoke.py").write_text(
        "def test_health(client):\n"
        "    resp = client.get('/health')\n"
        "    assert resp.status_code == 200\n"
        "    assert resp.json() == {'status': 'ok'}\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/test_smoke.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    # Exit 0 = the app imported via the frozen conftest and the health probe answered.
    assert result.returncode == 0, (
        f"scaffold-materialized suite failed to run:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "1 passed" in result.stdout
    # Guard the regression directly: no import resolution failure at collection.
    assert "ModuleNotFoundError" not in result.stdout + result.stderr


def test_pf26_import_guess_fails_without_the_seeded_fixture(tmp_path):
    """Counterfactual: the exact pf-26 failure mode. Against the SAME skeleton, a
    suite that guesses its own import root (`from app.main import app` — no `app`
    package; files live under backend/) crashes pytest collection with a
    ModuleNotFoundError. This is the wall the seeded `client` fixture removes: the
    delta between converging and exhausting is purely the import convention."""
    import subprocess
    import sys

    for f in expand(_group_run_manifest()):
        p = tmp_path / f["name"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["content"])

    test_dir = tmp_path / "backend" / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    # The pf-26 mistake: the suite invents its own app import instead of using `client`.
    (test_dir / "test_bad.py").write_text(
        "from app.main import app\n"
        "from fastapi.testclient import TestClient\n"
        "client = TestClient(app)\n\n"
        "def test_health():\n"
        "    assert client.get('/health').status_code == 200\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/test_bad.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0  # collection crashes, exactly like pf-26
    assert "ModuleNotFoundError" in result.stdout + result.stderr
    assert "app" in result.stdout + result.stderr  # the unresolvable `app` root


# --------------------------------------------------------------------------- #
# SIP-0100 Task 0.2 — QA test namespace (D1: bounded-hybrid ownership)
# --------------------------------------------------------------------------- #


def test_qa_test_namespace_is_deterministic_and_bounds_qa_paths():
    """The QA test namespace is deterministic per stack (independent of manifest contents), and
    membership is the write-authority boundary: plan-declared concrete test files fall inside it;
    source files and undeclared top-level paths (the pf-26 shape) do not."""
    from squadops.capabilities.scaffold import is_qa_test_path, qa_test_namespace

    m = _group_run_manifest()
    assert qa_test_namespace(m) == ("backend/tests/", "frontend/src/tests/")
    assert qa_test_namespace(m) == qa_test_namespace(_group_run_manifest())  # deterministic

    assert is_qa_test_path("backend/tests/test_runs.py", m)
    assert is_qa_test_path("./frontend/src/tests/flows.test.jsx", m)  # normalized
    assert not is_qa_test_path("backend/main.py", m)  # frozen source, not QA-owned
    assert not is_qa_test_path("backend/routes.py", m)  # fill slot, not QA-owned
    assert not is_qa_test_path("tests/test_runs.py", m)  # undeclared top-level tests dir


def test_qa_test_namespace_rejects_unknown_stack():
    from squadops.capabilities.scaffold import InterfaceManifest, qa_test_namespace

    bad = InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )
    with pytest.raises(ValueError, match="no scaffold expander"):
        qa_test_namespace(bad)

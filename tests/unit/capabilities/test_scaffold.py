"""Tests for the contract-first scaffold expander (SIP-Contract-First-Build-Scaffolding).

These assert the two load-bearing properties of the Phase-0.5 spike: the manifest
parses into the typed contract, and the expander materializes a *wired* skeleton
(App.jsx imports the views it routes to; routes.py defines every declared endpoint;
the generated Python is syntactically valid). The build+boot proof is a separate
CI/local gate; these guard the expander logic itself.
"""

from __future__ import annotations

import dataclasses as dc
import importlib.util
from pathlib import Path

import pytest
import yaml

from squadops.capabilities import scaffold, stack_fastapi_react
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
        ("GET", "/runs/{run_id}"),
        ("POST", "/runs/{run_id}/join"),
        ("POST", "/runs/{run_id}/leave"),
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
    # /runs declares success_status: 201, so the decorator carries it (pf-39); join
    # declares none, so its decorator carries the DERIVED 200 — the value the contract
    # asserts for a child POST (#772: a bare decorator meant FastAPI's 200 met the
    # deriver's 201 on an undeclared collection POST, an unwinnable contract). The two
    # together pin that the status comes from the manifest or the deriver's one seam,
    # never from a framework default the contract does not know about.
    assert '@router.post("/runs", response_model=RunEvent, status_code=201)' in routes
    assert '@router.post("/runs/{run_id}/join", response_model=RunEvent, status_code=200)' in routes
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
    # materializer must refuse to write outside the target root. The guard lives on
    # the canonical helper, so every caller inherits it — the two copies of this loop
    # in scripts/dev/ (only one of which HAD the guard) now delegate here.
    monkeypatch.setattr(scaffold, "expand", lambda _m: [{"name": "../escape.txt", "content": "x"}])
    with pytest.raises(ValueError, match="refusing to write outside"):
        scaffold.materialize(_group_run_manifest(), tmp_path)
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


# --------------------------------------------------------------------------- #
# SIP-0100 Task 1.4 — runner-shape harness proof (through the production runner)
# --------------------------------------------------------------------------- #


async def test_scaffold_harness_resolves_under_the_production_test_runner():
    """The fixture-based smoke test reaches assertion execution through the PRODUCTION test-runner
    handler (`run_generated_tests`) — the same invocation shape (workspace, PYTHONPATH #454,
    collection) a bound cycle uses, not just a dev-shell `pytest`. Proves the scaffold harness
    (conftest sys.path anchor + `client` fixture) works under the real runner (SIP-0100 §9)."""
    from squadops.capabilities.handlers.test_runner import run_generated_tests

    # runner shape is {"path", "content"}; expand() emits {"name", "content"}.
    files = [{"path": f["name"], "content": f["content"]} for f in expand(_group_run_manifest())]
    source = [f for f in files if not f["path"].startswith("frontend/")]  # backend + root conftest
    tests = [
        {
            "path": "backend/tests/test_smoke.py",
            "content": (
                "def test_health(client):\n    assert client.get('/health').status_code == 200\n"
            ),
        }
    ]

    result = await run_generated_tests(source, tests)
    assert result.executed is True, getattr(result, "output", result)
    assert result.exit_code == 0, getattr(result, "output", result)
    assert result.tests_passed is True


class TestErrorSeamInstructions:
    """pf-34: the ApiError raise convention must survive the stub's death and
    reach correction prompts — dev repairs guessed ApiError(status_code=...,
    detail=...) on two consecutive rolls and 500'd every error path."""

    def test_lines_derive_from_manifest_error_contract(self):
        from squadops.capabilities.scaffold import error_seam_instructions

        lines = error_seam_instructions(_group_run_manifest())
        assert len(lines) == 2
        assert "ApiError(code, message)" in lines[0]
        assert "never `ApiError(status_code=..., detail=...)`" in lines[0]
        assert "HTTPException" in lines[0]
        assert "`run_not_found` → 404" in lines[1]
        assert "`duplicate_participant` → 409" in lines[1]
        assert "`validation_error` → 422" in lines[1]

    def test_empty_without_error_contract_or_manifest(self):
        from squadops.capabilities.scaffold import error_seam_instructions

        raw = _raw_manifest()
        raw["api"].pop("error_contract", None)
        assert error_seam_instructions(InterfaceManifest.from_dict(raw)) == []
        assert error_seam_instructions(None) == []


class TestDeclaredSuccessStatus:
    """pf-39: the success status is *interface*, so the scaffold must own it.

    Before this, ``Endpoint`` had no success-status field, ``_routes_source`` emitted a
    bare ``@router.post(path)`` (FastAPI default 200), and ``_probes`` hardcoded
    ``expect: status 201`` — a skeleton that contradicted its own contract. Green then
    depended on the dev agent *volunteering* ``status_code=201``: pf-38 did, pf-39 did
    not, and that single token was the entire difference between accepted and rejected.
    """

    def test_declared_status_lands_on_the_decorator(self):
        routes = next(
            f["content"] for f in expand(_group_run_manifest()) if f["name"] == "backend/routes.py"
        )
        post_runs = next(ln for ln in routes.splitlines() if ln.startswith('@router.post("/runs"'))
        assert "status_code=201" in post_runs

    def test_undeclared_status_emits_no_status_code(self):
        """A GET declares no success status, so the decorator must stay bare — the
        fix must not blanket every route with a status it did not ask for."""
        routes = next(
            f["content"] for f in expand(_group_run_manifest()) if f["name"] == "backend/routes.py"
        )
        get_runs = next(ln for ln in routes.splitlines() if ln.startswith('@router.get("/runs"'))
        assert "status_code" not in get_runs

    def test_probe_expectation_follows_the_manifest_not_a_constant(self):
        """The probe must *derive* its expectation from the same field the decorator
        reads. If it stayed hardcoded at 201, a manifest declaring anything else would
        emit a contract its own skeleton could never satisfy — the pf-39 defect with
        the numbers changed."""
        from squadops.capabilities.scaffold_contract import emit_contract_dict

        raw = _raw_manifest()
        for ep in raw["api"]["endpoints"]:
            if ep["method"] == "POST" and ep["path"] == "/runs":
                ep["success_status"] = 202
        manifest = InterfaceManifest.from_dict(raw)

        probe = next(
            p
            for p in emit_contract_dict(manifest)["behavioral"]["probes"]
            if p["id"] == "vc-probe-runs"
        )
        assert probe["expect"]["status"] == 202

        routes = next(f["content"] for f in expand(manifest) if f["name"] == "backend/routes.py")
        assert "status_code=202" in routes

    def test_manifest_without_success_status_keeps_the_historical_probe_default(self):
        """Backward compatibility: manifests predating the field still get 201."""
        from squadops.capabilities.scaffold_contract import emit_contract_dict

        raw = _raw_manifest()
        for ep in raw["api"]["endpoints"]:
            ep.pop("success_status", None)

        probe = next(
            p
            for p in emit_contract_dict(InterfaceManifest.from_dict(raw))["behavioral"]["probes"]
            if p["id"] == "vc-probe-runs"
        )
        assert probe["expect"]["status"] == 201


def test_success_status_moves_the_manifest_content_hash():
    """``_canonical`` claims to project every field the expander reads. ``success_status``
    lands on the emitted decorator, so a manifest that changes it produces a different
    skeleton — if the hash ignored it, a verification contract could stay bound to a
    manifest whose skeleton no longer matches, which is precisely the SIP-0098 §10 drift
    the hash exists to prevent."""
    raw = _raw_manifest()
    baseline = InterfaceManifest.from_dict(raw).content_hash()

    changed = _raw_manifest()
    for ep in changed["api"]["endpoints"]:
        if ep["method"] == "POST" and ep["path"] == "/runs":
            ep["success_status"] = 202

    assert InterfaceManifest.from_dict(changed).content_hash() != baseline


class TestModelSurfaceInstructions:
    """pf-41: repairs invent model names, and the guesses compound.

    The dev agent imported the correct names; three consecutive repairs then replaced
    them with `Run`/`CreateRun`, then `RunCreate`, then a five-name invention — turning
    working code into code that cannot import. The unresolved-import gate rejects such a
    patch but never says what the real names ARE, so the next attempt guesses again.
    """

    def test_lines_name_every_model_the_scaffold_emits(self):
        from squadops.capabilities.scaffold import model_surface_instructions

        manifest = _group_run_manifest()
        lines = model_surface_instructions(manifest)
        blob = " ".join(lines)

        # every class the frozen models.py actually defines must be named
        emitted = next(f["content"] for f in expand(manifest) if f["name"] == "backend/models.py")
        defined = [
            ln.split("class ", 1)[1].split("(", 1)[0]
            for ln in emitted.splitlines()
            if ln.startswith("class ")
        ]
        assert defined, "fixture sanity: models.py should define classes"
        for name in defined:
            # field-level since pf-45: names render as signatures, `RunEvent(id, ...)`
            assert f"`{name}(" in blob, (
                f"{name} is defined in models.py but not named to the repair"
            )

    def test_field_names_are_exact_and_field_level(self):
        """pf-45: class names alone did not carry the surface a fill body touches — the
        dev wrote `pace=data.pace` against a model declaring `pace_target`, and every
        POST /runs raised into a 500. The block must name the fields, not just the class."""
        from squadops.capabilities.scaffold import model_surface_instructions

        blob = " ".join(model_surface_instructions(_group_run_manifest()))

        assert "pace_target" in blob
        assert "`RunEvent(id, title, datetime, location, distance, pace_target" in blob
        assert "`RunEventCreate(title, datetime, location" in blob

    def test_the_frozen_store_is_named_with_its_actual_store_names(self):
        """pf-45's second defect: the dev re-declared local store dicts, shadowing
        backend/store.py — reset() then cleared the unused stores and test isolation
        silently broke. The block names the real stores so there is nothing to invent."""
        from squadops.capabilities.scaffold import model_surface_instructions

        blob = " ".join(model_surface_instructions(_group_run_manifest()))

        assert "`backend/store.py`" in blob
        assert "`run_event_store`" in blob
        assert "`participant_store`" in blob
        assert "reset()" in blob

    def test_non_memory_persistence_omits_the_store_line(self):
        from squadops.capabilities.scaffold import model_surface_instructions

        raw = _raw_manifest()
        raw["persistence"] = "external"
        lines = model_surface_instructions(InterfaceManifest.from_dict(raw))

        assert lines, "model lines still render"
        assert not any("store.py" in ln for ln in lines)

    def test_the_names_pf41_invented_are_not_presented_as_valid(self):
        """The five names pf-41's last repair imported do not exist. They may appear in
        the do-not-invent warning, but never in the authoritative list of what exists."""
        from squadops.capabilities.scaffold import model_surface_instructions

        available = next(
            ln for ln in model_surface_instructions(_group_run_manifest()) if "EXACTLY these" in ln
        )
        for invented in ("RunResponse", "RunJoin", "RunLeave", "RunDetailResponse", "CreateRun"):
            assert f"`{invented}`" not in available

    def test_states_the_module_is_frozen(self):
        """Without this a repair 'fixes' a missing name by editing models.py — which is
        restored by scaffold enforcement, so the repair silently accomplishes nothing."""
        from squadops.capabilities.scaffold import model_surface_instructions

        assert any("frozen" in ln for ln in model_surface_instructions(_group_run_manifest()))

    def test_absent_manifest_contributes_nothing(self):
        """Author mode and non-scaffold stacks inject nothing — additive, like every
        other entry on this transport."""
        from squadops.capabilities.scaffold import model_surface_instructions

        assert model_surface_instructions(None) == []

    def test_manifest_without_entities_or_shapes_contributes_nothing(self):
        from squadops.capabilities.scaffold import model_surface_instructions

        bare = InterfaceManifest.from_dict(
            {
                "version": 1,
                "kind": "interface_manifest",
                "project_id": "x",
                "stack": "fullstack_fastapi_react",
            }
        )
        assert model_surface_instructions(bare) == []


class TestScaffoldOwnedStore:
    """#603: the manifest declares in-memory persistence and the skeleton emitted nothing
    that held the data, so the planner invented a module every roll. An invented file is
    outside every safety net — nothing freezes it, no criterion names it, and its imports
    are guessed fresh. pf-40 died on exactly that: `from models import ...` without the
    leading dot, so the app never started and the behavioural probe could not run.
    """

    def test_the_skeleton_owns_the_state_the_manifest_declares(self):
        manifest = _group_run_manifest()
        assert manifest.persistence == "in_memory"  # fixture sanity

        names = {f["name"] for f in expand(manifest)}
        assert "backend/store.py" in names

    def test_store_imports_resolve_against_the_emitted_models(self):
        """The pf-40 killer, as a unit test: every name the store imports from `.models`
        must actually be defined there. This would have failed before that roll dispatched."""
        files = _by_name(expand(_group_run_manifest()))
        store, models = files["backend/store.py"], files["backend/models.py"]

        defined = {
            ln.split("class ", 1)[1].split("(", 1)[0]
            for ln in models.splitlines()
            if ln.startswith("class ")
        }
        imported = {
            name.strip()
            for ln in store.splitlines()
            if ln.startswith("from .models import ")
            for name in ln.split("import ", 1)[1].split(",")
        }
        assert imported, "store should import its entity types"
        assert imported <= defined, (
            f"store imports names models.py does not define: {imported - defined}"
        )

    def test_store_uses_a_relative_import(self):
        """pf-40's dev agent wrote `from models import ...` — absolute, so the package
        never loaded. The scaffold must not leave that to chance."""
        store = _by_name(expand(_group_run_manifest()))["backend/store.py"]
        assert "from .models import" in store
        assert "\nfrom models import" not in store

    def test_one_store_per_declared_entity(self):
        manifest = _group_run_manifest()
        store = _by_name(expand(manifest))["backend/store.py"]
        for entity in manifest.entities:
            assert f"_store: dict[str, {entity.name}]" in store

    def test_routes_stub_wires_the_store_so_the_fill_uses_it(self):
        """If the fill slot doesn't see the store it will invent one — which is the whole
        defect. Same rationale as pre-wiring the ApiError import."""
        routes = _by_name(expand(_group_run_manifest()))["backend/routes.py"]
        assert "from .store import" in routes

    def test_store_is_frozen_not_a_fill_slot(self):
        """Frozen means scaffold enforcement restores it if a producer rewrites it. If it
        were a fill slot the agent could reintroduce the broken import it was meant to fix."""
        from squadops.capabilities.scaffold import fill_slot_paths

        assert "backend/store.py" not in fill_slot_paths(_group_run_manifest())

    def test_store_is_valid_python_and_exposes_reset(self):
        store = _by_name(expand(_group_run_manifest()))["backend/store.py"]
        compile(store, "backend/store.py", "exec")
        # QA suites currently reach into a private dict to isolate cases; give them a seam
        assert "def reset()" in store

    def test_entityless_manifest_still_emits_a_valid_module(self):
        raw = _raw_manifest()
        raw.pop("entities", None)
        store = _by_name(expand(InterfaceManifest.from_dict(raw)))["backend/store.py"]

        compile(store, "backend/store.py", "exec")  # must not emit a bodyless reset()
        assert "from .models import" not in store  # nothing to import


class TestFrontendTestHarness:
    """#627 / pf-53: the frontend test harness is scaffold-owned — deps, runner
    script, jsdom config, setup file, and a frozen harness-proof test. Without
    it, qa either refused to test ("no runner available" — which matched the
    workspace) or invented harnesses that could not run (five repair attempts,
    all environment-killed)."""

    def test_package_json_declares_the_runner_and_harness_deps(self):
        import json

        pkg = json.loads(_by_name(expand(_group_run_manifest()))["frontend/package.json"])
        assert pkg["scripts"]["test"] == "vitest run"
        for dep in (
            "vitest",
            "jsdom",
            "@testing-library/react",
            "@testing-library/jest-dom",
            "@testing-library/dom",
        ):
            assert dep in pkg["devDependencies"], f"missing devDependency: {dep}"

    def test_vite_config_wires_jsdom_and_the_emitted_setup_file(self):
        files = _by_name(expand(_group_run_manifest()))
        config = files["frontend/vite.config.js"]
        assert "environment: 'jsdom'" in config
        # The setupFiles entry must point at a file the expansion actually emits —
        # a renamed setup file would break every suite at collection.
        assert "setupFiles: ['src/test-setup.js']" in config
        assert "frontend/src/test-setup.js" in files
        assert "@testing-library/jest-dom" in files["frontend/src/test-setup.js"]

    def test_harness_proof_imports_only_emitted_modules(self):
        files = _by_name(expand(_group_run_manifest()))
        harness = files["frontend/src/__tests__/harness.test.jsx"]
        # ../App.jsx from __tests__/ must resolve to the emitted App
        assert "from '../App.jsx'" in harness
        assert "frontend/src/App.jsx" in files
        assert "MemoryRouter" in harness

    def test_harness_files_are_frozen_not_fill_slots(self):
        from squadops.capabilities.scaffold import fill_slot_paths

        slots = fill_slot_paths(_group_run_manifest())
        assert "frontend/src/__tests__/harness.test.jsx" not in slots
        assert "frontend/src/test-setup.js" not in slots

    def test_setup_file_unmounts_between_tests(self):
        """#1127: under vitest's default ``globals:false`` Testing Library never
        auto-registers ``cleanup`` (it needs a global ``afterEach``), so a suite that
        renders in two ``it`` blocks fails "Found multiple elements" — 1.6.5
        FastAPI+React roll 1, three suites, the only green one had added the line
        itself. The frozen setup registers it; both imports must be real statements
        so the registration cannot survive as a comment."""
        setup = _by_name(expand(_group_run_manifest()))["frontend/src/test-setup.js"]
        statements = [ln.strip() for ln in setup.splitlines() if not ln.strip().startswith("//")]
        assert "import { afterEach } from 'vitest'" in statements
        assert "import { cleanup } from '@testing-library/react'" in statements
        assert "afterEach(cleanup)" in statements


class TestFrozenModelOptionalFields:
    """#1125: what the frozen pydantic model says about a field the manifest marks
    optional. Five of six 1.6.5 FastAPI+React rolls opened with a 500 on POST /runs
    because ``required: false, default: null`` froze as ``distance: str = None`` —
    pydantic v2 rejects an explicit None for a ``str`` field — while the request
    shape was correctly nullable and the route forwarded its None straight in."""

    @staticmethod
    def _run_field_line(field: dict) -> str:
        raw = _raw_manifest()
        run = next(e for e in raw["entities"] if e["name"] == "RunEvent")
        run["fields"] = [f for f in run["fields"] if f["name"] != "distance"] + [field]
        models = _by_name(expand(InterfaceManifest.from_dict(raw)))["backend/models.py"]
        compile(models, "backend/models.py", "exec")
        klass = models.split("class RunEvent(BaseModel):", 1)[1].split("\nclass ", 1)[0]
        return next(ln.strip() for ln in klass.splitlines() if ln.strip().startswith("distance:"))

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            # the 1.6.5 shape: a declared null default is nullable, not ``str = None``
            (
                {"name": "distance", "type": "string", "required": False, "default": None},
                "distance: str | None = None",
            ),
            # the shakeouts' shape: optional with no default key — same meaning, same line
            (
                {"name": "distance", "type": "string", "required": False},
                "distance: str | None = None",
            ),
            # a non-null default is never None after construction, so it stays non-nullable
            (
                {"name": "distance", "type": "string", "required": False, "default": "5k"},
                "distance: str = '5k'",
            ),
            # a required field without a default is a bare annotation
            (
                {"name": "distance", "type": "string", "required": True},
                "distance: str",
            ),
        ],
        ids=["default-null", "no-default", "non-null-default", "required"],
    )
    def test_optional_field_freezes_by_its_effective_default(self, field, expected):
        assert self._run_field_line(field) == expected

    def test_null_default_model_accepts_the_request_shapes_none(self):
        """The failure as the app saw it: the route builds the entity from an optional
        request field that is None. With the old emission this raised ValidationError."""
        import sys
        import types

        raw = _raw_manifest()
        run = next(e for e in raw["entities"] if e["name"] == "RunEvent")
        for f in run["fields"]:
            if f["name"] in ("distance", "pace_target", "route_notes"):
                f["default"] = None
        models = _by_name(expand(InterfaceManifest.from_dict(raw)))["backend/models.py"]
        # The emitted module uses ``from __future__ import annotations``; pydantic
        # resolves the entity references through ``sys.modules[cls.__module__]``.
        mod = types.ModuleType("frozen_models_1125")
        sys.modules[mod.__name__] = mod
        try:
            exec(compile(models, "backend/models.py", "exec"), mod.__dict__)
            run_event = mod.RunEvent(
                id="r1",
                title="t",
                datetime="2026-08-01T08:00:00",
                location="here",
                distance=None,
                pace_target=None,
                route_notes=None,
            )
        finally:
            del sys.modules[mod.__name__]
        assert (run_event.distance, run_event.pace_target, run_event.route_notes) == (None,) * 3


class TestNonBlankRequestFields:
    """#593: the emitted request models must actually enforce the constraint —
    a template typo (wrong alias, misplaced annotation) would compile fine and
    silently restore the blank-201 gap."""

    def _models_module(self):
        import sys
        import types

        src = _by_name(expand(_group_run_manifest()))["backend/models.py"]
        mod = types.ModuleType("scaffold_emitted_models")
        # Registered so pydantic can resolve the module's deferred annotations
        # (`from __future__ import annotations`) exactly as a real import does.
        sys.modules["scaffold_emitted_models"] = mod
        try:
            exec(compile(src, "backend/models.py", "exec"), mod.__dict__)
        except Exception:
            sys.modules.pop("scaffold_emitted_models", None)
            raise
        return mod

    def test_blank_and_whitespace_required_fields_are_rejected(self):
        import pydantic

        mod = self._models_module()
        for bad in ("", "   "):
            try:
                mod.RunEventCreate(title=bad, datetime="2026-08-01T08:00:00", location="Park")
            except pydantic.ValidationError:
                continue
            raise AssertionError(f"blank title {bad!r} was accepted")

    def test_valid_input_is_accepted_and_whitespace_stripped(self):
        mod = self._models_module()
        run = mod.RunEventCreate(
            title="  Morning 5K  ", datetime="2026-08-01T08:00:00", location="Park"
        )
        assert run.title == "Morning 5K"


# --------------------------------------------------------------------------- #
# #659: DOM anchor contract (route testids)
# --------------------------------------------------------------------------- #


class TestDomAnchorContract:
    """The manifest pins per-view data-testid inventories; the stub stamps the
    root anchor; the surface deriver feeds both prompt sides.

    Bug caught (fay-6/fay-12): with no shared DOM arbiter, qa suites assert
    invented render details, dev patches toward the last suite, and every
    correction round re-rolls the mismatch — five rounds on fay-12, all on
    the frontend suite, backend green throughout.
    """

    def test_manifest_parses_and_round_trips_route_testids(self):
        m = _group_run_manifest()
        runs_list = next(r for r in m.frontend.routes if r.view == "RunsListView")
        assert runs_list.testids[0] == "runs-list"  # root-anchor convention
        assert "empty-state" in runs_list.testids

        # testids participate in the canonical form, so content_hash() moves
        # with them — the re-seed driver for this contract change.
        emitted = next(
            r for r in m._canonical()["frontend"]["routes"] if r["view"] == "RunsListView"
        )
        assert emitted["testids"] == list(runs_list.testids)

    def test_view_stub_stamps_root_anchor_and_inventory(self):
        files = _by_name(expand(_group_run_manifest()))
        stub = files["frontend/src/views/RunsListView.jsx"]
        assert 'data-testid="runs-list"' in stub
        # the full inventory rides as a comment for the fill author
        assert "run-item" in stub
        assert "empty-state" in stub

    def test_route_without_testids_renders_the_plain_stub(self):
        stub = stack_fastapi_react._view_stub(scaffold.Route(path="/x", view="XView"))
        assert "data-testid" not in stub
        assert "DOM anchors" not in stub
        assert "export default function XView()" in stub

    def test_testid_surface_instructions_one_line_per_view(self):
        lines = scaffold.testid_surface_instructions(_group_run_manifest())
        assert len(lines) == 3
        assert lines[0].startswith("`RunsListView` (route `/`): root container `runs-list`")
        assert any("`join-name-input`" in line for line in lines)

    def test_testid_surface_instructions_empty_without_manifest_or_testids(self):
        assert scaffold.testid_surface_instructions(None) == []
        import dataclasses

        m = _group_run_manifest()
        bare_routes = tuple(dataclasses.replace(r, testids=()) for r in m.frontend.routes)
        bare = dataclasses.replace(m, frontend=dataclasses.replace(m.frontend, routes=bare_routes))
        assert scaffold.testid_surface_instructions(bare) == []


class TestErrorSeamIsPerStack:
    """#912 — one shared text asserted stack #1's Python facts for every stack."""

    def test_each_stack_names_its_own_module_import_and_parameter(self):
        """Bug caught: a nextjs_ts repair is told to edit `errors.py`.

        The file is `lib/errors.ts`. This is the #902 class in a second location — a
        shared prompt surface stating one stack's facts as universal — and it fires
        exactly when a repair is trying to fix an error-envelope defect, which is what
        window rolls 2 and 3 were both doing. The body field is `message` on BOTH
        stacks since #795's reconciliation (the nextjs generator's `detail` was the
        odd one out against stack #1 and the reference manifests); the per-stack seam
        stays because module and import genuinely differ."""
        from squadops.capabilities.scaffold import error_seam_for

        fastapi = error_seam_for("fullstack_fastapi_react")
        nextjs = error_seam_for("nextjs_ts")

        assert (fastapi.module, fastapi.body_field) == ("errors.py", "message")
        assert (nextjs.module, nextjs.body_field) == ("lib/errors.ts", "message")
        assert "@/lib/errors" in nextjs.import_form
        assert "ApiError(code, message)" == nextjs.raise_form

    def test_the_framework_exception_clause_is_named_only_where_one_exists(self):
        """Bug caught: generalizing the prohibition loses the name that made it work.

        `HTTPException` is what pf-33/pf-34 devs actually reached for on stack #1, so
        naming it is the point. Next.js has no equivalent attractor, and inventing one
        would teach a nonexistent fact — the clause is omitted instead.
        """
        from squadops.capabilities.scaffold import error_seam_for

        assert error_seam_for("fullstack_fastapi_react").framework_exception == "HTTPException"
        assert error_seam_for("nextjs_ts").framework_exception == ""


class TestErrorEnvelopeLines:
    """#911 — the envelope's body shape, stated instead of guessed."""

    def test_the_nested_path_is_stated_and_the_invented_one_named(self):
        """Bug caught: the author asserts `body.error_code` and reads undefined.

        It did exactly that on two consecutive window rolls. Naming the wrong form
        explicitly is deliberate — #902 established that showing the correct form alone
        is weaker than showing correct-and-wrong side by side, because the wrong form is
        what the model already believes.
        """
        from squadops.capabilities.scaffold import error_envelope_lines

        lines = error_envelope_lines("nextjs_ts")
        joined = " ".join(lines)

        assert '{"error": {"code": "validation_error", "message": "..."}}' in joined
        assert "body.error.code" in joined
        assert "error_code" in joined  # the invented form, named as wrong

    def test_each_stack_describes_the_envelope_its_generator_emits(self):
        """Bug caught: the brief describing a field the generator does not write.

        The description renders from each stack's OWN seam declaration, so it tracks
        the generator by construction. Since #795's reconciliation both stacks emit
        `message` (nextjs's `detail` was the odd one out against stack #1 and the
        reference manifests) — the per-stack seam machinery stays, because module and
        import genuinely differ and a future stack MAY differ on the field again."""
        from squadops.capabilities.scaffold import error_envelope_lines

        assert '"message"' in " ".join(error_envelope_lines("fullstack_fastapi_react"))
        assert '"message"' in " ".join(error_envelope_lines("nextjs_ts"))

    def test_an_unknown_stack_says_nothing_rather_than_guessing(self):
        """A stack with no declared seam must produce no lines. A guessed envelope is
        worse than silence: the author would assert against a shape nothing emits and
        the failure would look like an application defect."""
        from squadops.capabilities.scaffold import error_envelope_lines

        assert error_envelope_lines("") == []
        assert error_envelope_lines("some_future_stack") == []


class TestTypeScriptConstSurface:
    """#875 — a const's type and values are facts, not decoration."""

    def test_a_record_const_renders_its_type_and_values(self):
        """Bug caught: `exports ERROR_STATUS` tells an author the name and nothing else.

        Roll 13's qa suite called `.get()` on it — a runtime TypeError, since it is a
        Record and not a Map — and asserted a status the map does not contain. Both
        facts are in the frozen source the surface is derived from.
        """
        from squadops.capabilities.scaffold import _ecmascript_surface

        rendered = _ecmascript_surface(
            "export const ERROR_STATUS: Record<string, number> = {\n"
            "  validation_error: 400,\n"
            "  run_not_found: 404\n"
            "}\n"
        )

        assert "Record<string, number>" in rendered
        assert "validation_error: 400" in rendered
        assert "run_not_found: 404" in rendered

    def test_a_long_or_computed_const_degrades_to_name_and_type(self):
        """The surface index is a reminder of declarations, not a second copy of the
        file. A const built by a call has no literal to show, and an oversized literal
        would crowd out every other line — both degrade to name-and-type, which is still
        strictly more than the bare name."""
        from squadops.capabilities.scaffold import _ecmascript_surface

        computed = _ecmascript_surface("export const CONFIG: AppConfig = buildConfig()\n")
        assert "CONFIG: AppConfig" in computed
        assert "buildConfig" not in computed

        long_literal = _ecmascript_surface(
            "export const BIG: Record<string, string> = {\n"
            + "".join(f"  key_{i}: 'value_{i}',\n" for i in range(20))
            + "}\n"
        )
        assert "BIG: Record<string, string>" in long_literal
        assert "key_19" not in long_literal


class TestBriefCarriesSuccessStatus:
    """#1049: the second channel the framing omission gate reads.

    The gate blocks a framing only when NEITHER the skeleton nor the dev brief carries
    a declared success status. This predicate answers the second half, so a wrong
    answer here either re-arms a re-roll tax on a correct framing or — worse — silences
    the gate on a stack where prose really is the only channel.
    """

    def test_the_registered_stacks_report_their_actual_channels(self):
        from squadops.capabilities.scaffold import (
            brief_carries_success_status_for,
            skeleton_pins_success_status_for,
        )

        # nextjs pins nothing structurally (the TODO comment dies with the fill) but
        # does render the appendix — which is exactly why #1049 exists.
        assert skeleton_pins_success_status_for("nextjs_ts") is False
        assert brief_carries_success_status_for("nextjs_ts") is True
        assert skeleton_pins_success_status_for("fullstack_fastapi_react") is True

    @pytest.mark.parametrize("stack", ["", "no_such_stack", "NEXTJS_TS"])
    def test_an_unknown_stack_claims_no_channel(self, stack):
        """The conservative answer. Claiming a channel we cannot prove would silence
        the gate on precisely the stack that has no other carrier."""
        from squadops.capabilities.scaffold import brief_carries_success_status_for

        assert brief_carries_success_status_for(stack) is False

    def test_a_scaffoldable_stack_whose_capability_has_no_appendix_claims_no_channel(
        self, monkeypatch
    ):
        """The guard no registered stack reaches today, and the reason it is written
        rather than assumed: the dev brief carries the status only where the fill-only
        appendix renders. A capability with no template renders none, so prose is still
        the sole channel and the omission check must keep blocking.

        Mutating this to `return True` left the whole suite green — an unreachable
        guard is exactly the kind that silently stops working when a third stack lands.
        """
        from squadops.capabilities import scaffold as scaffold_module
        from squadops.capabilities.dev_capabilities import get_capability

        real = get_capability

        def _no_appendix(name: str):
            return dc.replace(real(name), fill_only_template="")

        monkeypatch.setattr("squadops.capabilities.dev_capabilities.get_capability", _no_appendix)
        assert scaffold_module.brief_carries_success_status_for("nextjs_ts") is False

"""The delivered-app capture reads the run's own interface (#1665).

What bug would these catch? The three v1.8.1 cut failures, each from a seed written for one
roll's app and replayed on another's: a 422 (``location`` authored where the seed said
``meeting_location``), a 404 (the join endpoint authored as ``/participants``, not ``/join``),
and a blank page written as a screenshot (``/`` photographed on an app routed at ``/runs``).
The two manifest fixtures are the shapes of window pair 5's squad and Solo runs.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "capture_delivered_app", REPO_ROOT / "scripts" / "dev" / "capture_delivered_app.py"
)
capture = importlib.util.module_from_spec(_spec)
sys.modules["capture_delivered_app"] = capture
_spec.loader.exec_module(capture)

SEED = json.loads((REPO_ROOT / "examples" / "03_group_run" / "screenshot_seed.json").read_text())


def _manifest(location: str, join: str, optional: list[str], testids: list[str]) -> dict:
    return {
        "api": {
            "base_path": "",
            "request_shapes": {
                "RunCreate": {"required": ["title", "datetime", location], "optional": optional},
                "JoinRequest": {"required": ["name"]},
            },
            "endpoints": [
                {"method": "POST", "path": "/runs", "request": "RunCreate"},
                {"method": "GET", "path": "/runs"},
                {"method": "GET", "path": "/runs/{run_id}"},
                {"method": "POST", "path": f"/runs/{{run_id}}/{join}", "request": "JoinRequest"},
            ],
        },
        "frontend": {
            "routes": [
                {"path": "/runs", "testids": testids},
                {"path": "/runs/new", "testids": ["create-view"]},
                {"path": "/runs/:run_id", "testids": ["detail-view"]},
            ]
        },
    }


SQUAD = _manifest(
    "location", "participants", ["distance", "pace_target", "route_notes"], ["runs-view"]
)
SOLO = _manifest(
    "meeting_location",
    "join",
    ["distance", "pace_target", "route_notes", "capacity"],
    ["run-list-view"],
)


@pytest.mark.parametrize(
    ("manifest", "field", "join_path", "capacity_kept"),
    [
        (SQUAD, "location", "/runs/{id}/participants", False),
        (SOLO, "meeting_location", "/runs/{id}/join", True),
    ],
)
def test_the_committed_seed_maps_onto_each_runs_authored_interface(
    manifest, field, join_path, capacity_kept
):
    """Bug this catches: the v1.8.1 squad capture's 422 and 404, from a seed replayed verbatim
    on an app that authored different names. The committed seed file is the input."""
    requests, notes = capture.plan_seed(manifest, SEED)

    creates = [r for r in requests if r["path"] == "/runs"]
    joins = [r for r in requests if r["path"] != "/runs"]
    assert len(creates) == 3 and len(joins) == 3
    assert creates[0]["body"][field] == "Riverside Park, east gate"
    assert ("capacity" in creates[0]["body"]) is capacity_kept
    assert {r["path"] for r in joins} == {join_path}
    assert joins[0]["body"] == {"name": "Priya"}
    assert any("capacity dropped" in n for n in notes) is not capacity_kept


def test_a_required_field_the_seed_cannot_fill_is_refused_by_name():
    manifest = _manifest("venue", "participants", [], ["runs-view"])
    with pytest.raises(SystemExit, match="requires 'venue'"):
        capture.plan_seed(manifest, SEED)


def test_an_interface_that_declares_none_of_the_seeds_endpoints_is_refused():
    manifest = _manifest("location", "attendees", [], ["runs-view"])
    with pytest.raises(SystemExit, match="member action endpoints"):
        capture.plan_seed(manifest, SEED)


def test_the_old_request_list_seed_is_refused():
    with pytest.raises(SystemExit, match="pre-#1665 request list"):
        capture.plan_seed(SQUAD, [{"method": "POST", "path": "/runs", "body": {}}])


def test_an_undeclared_route_is_refused_before_anything_boots(monkeypatch):
    """Wiring, entered at ``main``. Bug this catches: the v1.8.1 blank run-list shot at ``/``
    on an app routed at ``/runs``, found only after booting and photographing."""
    monkeypatch.setattr(capture, "load_manifest", lambda project, cycle, plan_refs=None: SQUAD)
    monkeypatch.setattr(capture, "cycle_row", lambda project, cycle: {})
    monkeypatch.setattr(capture, "reconstruct", lambda *a: pytest.fail("reconstructed"))
    monkeypatch.setattr(capture, "boot", lambda *a: pytest.fail("booted"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["capture", "--cycle", "c", "--run", "r", "--version", "1.8.2", "--route", "/:run-list"],
    )
    with pytest.raises(SystemExit, match=r"route\(s\) \['/'\] are not declared"):
        capture.main()


def test_a_detail_route_matches_its_declared_parameter_form():
    assert capture.declared_routes(SQUAD, [("/runs/{id}", "detail")]) == {
        "/runs/{id}": ["detail-view"]
    }


@pytest.mark.parametrize(
    ("rendered", "written"),
    [({"runs-view", "run-row"}, True), (set(), False), ({"app-error"}, False)],
)
def test_a_screenshot_is_written_only_when_its_view_rendered(
    tmp_path, monkeypatch, rendered, written
):
    """Bug this catches: a page that rendered nothing (or only an error boundary) written as a
    screenshot whose filename promises the run list."""
    monkeypatch.setattr(capture.Path, "home", lambda: tmp_path)

    def fake_chromium(cmd, **kwargs):
        target = next(a for a in cmd if a.startswith("--screenshot=")).split("=", 1)[1]
        Path(target).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(capture.subprocess, "run", fake_chromium)
    monkeypatch.setattr(capture, "rendered_testids", lambda browser, port, route: rendered)
    monkeypatch.setattr(capture, "REPO", tmp_path)
    assets = tmp_path / "assets"
    routes = [("/runs", "delivered-app-run-list")]

    if written:
        out = capture.shoot("chromium", 5199, routes, assets, 1180, {"/runs": ["runs-view"]})
        assert [p.name for p in out] == ["delivered-app-run-list.png"]
    else:
        with pytest.raises(SystemExit, match="rendered none of its view's test ids"):
            capture.shoot("chromium", 5199, routes, assets, 1180, {"/runs": ["runs-view"]})
        assert not (assets / "delivered-app-run-list.png").exists()


BEHIND_API = {**SQUAD, "api": {**SQUAD["api"], "base_path": "/api"}}


def test_the_committed_seed_maps_onto_an_interface_behind_a_base_path():
    """Bug this catches: the committed seed names ``POST /runs``; an interface declaring
    ``base_path: /api`` keys its endpoints ``POST /api/runs``, so the seed matched nothing and the
    1.8.2 cut's capture refused before it booted."""
    requests, _ = capture.plan_seed(BEHIND_API, SEED)
    paths = {r["path"] for r in requests}
    assert paths == {"/api/runs", "/api/runs/{id}/participants"}


def test_seed_requests_reach_the_ui_port_with_the_client_facing_path(monkeypatch, tmp_path):
    """Wiring, entered at ``main``. Bug this catches: seed requests went straight to the backend
    port with ``/api/runs``, which the backend does not serve — the dev proxy strips ``/api`` — so
    the 1.8.2 cut's capture failed with a 404 halfway through seeding."""
    seen: list[str] = []

    class _Resp:
        status = 201

        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=0):
        url = req if isinstance(req, str) else req.full_url
        seen.append(url)
        return _Resp(b'[{"id": "run-1"}]')

    monkeypatch.setattr(capture, "load_manifest", lambda project, cycle, plan_refs=None: BEHIND_API)
    monkeypatch.setattr(capture, "cycle_row", lambda project, cycle: {})
    monkeypatch.setattr(capture, "reconstruct", lambda *a: 0)
    monkeypatch.setattr(capture, "boot", lambda *a: None)
    monkeypatch.setattr(capture, "shoot", lambda *a, **k: [])
    monkeypatch.setattr(capture, "sh", lambda *a, **k: "")
    monkeypatch.setattr(capture.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(capture.Path, "home", lambda: tmp_path)
    seed_file = REPO_ROOT / "examples" / "03_group_run" / "screenshot_seed.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture",
            "--cycle",
            "c",
            "--run",
            "r",
            "--version",
            "1.8.2",
            "--seed-file",
            str(seed_file),
            "--id-from",
            "/api/runs",
            "--route",
            "/runs/{id}:detail",
            "--ui-port",
            "5199",
            "--api-port",
            "8099",
        ],
    )

    assert capture.main() == 0
    assert seen, "nothing was seeded"
    assert all(u.startswith("http://localhost:5199/api/runs") for u in seen), seen
    assert not any(":8099" in u for u in seen)


def _stored(vault: Path, cycle: str, run: str, art_id: str, name: str, body: str, **meta) -> None:
    d = vault / "group_run" / cycle / run / art_id
    (d / name).parent.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body)
    (d / "metadata.json").write_text(json.dumps({"artifact_id": art_id, "filename": name, **meta}))


def test_a_campaign_increment_is_rebuilt_from_its_accepted_tree_not_its_runs_stubs(
    tmp_path, monkeypatch
):
    """Bug caught (#2000, the 2.0.0 cut): increments 1 and 2 photographed as a page reading only
    "RunList". The increment's run holds the scaffold's stub for a view its change did not touch;
    the accepted tree names the real one, stored by an earlier cycle."""
    vault = tmp_path / "artifacts"
    monkeypatch.setattr(capture, "VAULT", vault)
    _stored(vault, "cyc_cal", "run_c", "art_real", "frontend/src/views/RunList.jsx", "REAL")
    _stored(vault, "cyc_inc", "run_i", "art_stub", "frontend/src/views/RunList.jsx", "STUB")
    tree = {"frontend/src/views/RunList.jsx": "art_real"}
    _stored(
        vault,
        "cyc_inc",
        "run_i",
        "art_tree",
        "accepted_tree.json",
        json.dumps(tree),
        artifact_type="accepted_tree",
    )

    out = tmp_path / "app"
    count = capture.reconstruct("group_run", "cyc_inc", "run_i", out)

    assert count == 1
    assert (out / "frontend/src/views/RunList.jsx").read_text() == "REAL"


def test_an_accepted_tree_naming_an_artifact_the_vault_lacks_is_refused_by_name(
    tmp_path, monkeypatch
):
    """Bug caught: a partial tree booted and photographed, with the missing file silently absent."""
    vault = tmp_path / "artifacts"
    monkeypatch.setattr(capture, "VAULT", vault)
    tree = {"backend/routes.py": "art_gone"}
    _stored(
        vault,
        "cyc_inc",
        "run_i",
        "art_tree",
        "accepted_tree.json",
        json.dumps(tree),
        artifact_type="accepted_tree",
    )

    with pytest.raises(SystemExit, match="backend/routes.py"):
        capture.reconstruct("group_run", "cyc_inc", "run_i", tmp_path / "app")


# --------------------------------------------------------------------------- #
# #2008: a reference increment stores no manifest, and its run holds stubs
# --------------------------------------------------------------------------- #


def _artifact(vault, cycle, run, art_id, filename, content, created, *, seeded=False):
    d = vault / "group_run" / cycle / run / art_id if run else vault / "group_run" / cycle / art_id
    (d / filename).parent.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)
    meta = {
        "artifact_id": art_id,
        "project_id": "group_run",
        "artifact_type": "interface_manifest" if filename.endswith(".yaml") else "source",
        "filename": filename,
        "content_hash": "h",
        "size_bytes": len(content),
        "media_type": "text/plain",
        "created_at": created,
        "cycle_id": cycle,
        "run_id": run,
        "metadata": {"scaffold_seeded": True} if seeded else {},
        "vault_uri": str((d / filename).relative_to(vault.parent.parent)),
    }
    for field in ("promotion_status", "system_prompt_bundle_hash", "request_template_id"):
        meta[field] = None
    for field in ("system_fragment_ids", "system_fragment_versions", "capability_supplement_ids"):
        meta[field] = []
    for field in ("request_template_version", "request_render_hash", "full_invocation_bundle_hash"):
        meta[field] = None
    meta["prompt_environment"] = None
    (d / "metadata.json").write_text(json.dumps(meta))


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "data" / "artifacts"
    monkeypatch.setattr(capture, "VAULT", root)
    monkeypatch.setattr(capture, "MAIN", tmp_path)
    return root


def test_a_reference_cycles_manifest_is_the_seeded_one_its_plan_refs_name(vault):
    """Bug caught: the v2.0.1 cut's "no interface_manifest.yaml stored" for the reference build
    half, whose candidate manifest was ingested before the cycle existed and stored unattached."""
    _artifact(vault, "_unattached", None, "art_cand", "interface_manifest.yaml", "api: {}\n", "t1")
    _artifact(vault, "cyc_ref", "run_impl", "art_src", "backend/main.py", "app\n", "t2")

    assert capture.load_manifest("group_run", "cyc_ref", ["art_cand", "art_cr"]) == {"api": {}}
    with pytest.raises(SystemExit, match="none named by its plan_artifact_refs"):
        capture.load_manifest("group_run", "cyc_ref", ["art_cr"])


def test_a_cycle_built_on_an_accepted_one_is_photographed_whole_never_its_stubs(vault, tmp_path):
    """#2008, #2000's shape on a reference increment: its run holds the view it changed and a
    scaffold stub for one it did not. Bug caught: the latest-per-filename tree photographing the
    stub page; the composed tree keeps the accepted view and takes the changed one."""
    _artifact(vault, "cyc_base", "run_b", "art_list", "src/List.jsx", "accepted list\n", "t1")
    _artifact(vault, "cyc_base", "run_b", "art_det", "src/Detail.jsx", "accepted detail\n", "t1")
    _artifact(
        vault, "cyc_ref", "run_r", "art_stub", "src/List.jsx", "FILL SLOT\n", "t2", seeded=True
    )
    _artifact(vault, "cyc_ref", "run_r", "art_new", "src/Detail.jsx", "capacity detail\n", "t3")
    out = tmp_path / "app"

    count = capture.reconstruct("group_run", "cyc_ref", "run_r", out, built_on="cyc_base")

    assert count == 2
    assert (out / "src/List.jsx").read_text() == "accepted list\n"
    assert (out / "src/Detail.jsx").read_text() == "capacity detail\n"

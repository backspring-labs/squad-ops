"""Interface-drift detector tests (correction-loop piece 1, set-report design).

Bug caught: an app that renames interface identifiers (field `location` ->
`meeting_location`, and simultaneously `pace_target` -> `pace` — the real pf-13
case) fails the probe with an opaque "status 404/422", the LLM analyzer
mislabels it, and the repair thrashes. The detector reports the offending set +
the interface targets so the agent renames by meaning; clean / class-drift /
unparseable cases yield NO finding and fall through to the existing loop.
"""

from __future__ import annotations

from types import SimpleNamespace

from squadops.cycles.interface_conformance import detect_interface_drift


def _manifest(fields: list[str], routes: list[tuple[str, str]]):
    entity = SimpleNamespace(name="RunEvent", fields=[SimpleNamespace(name=n) for n in fields])
    endpoints = [SimpleNamespace(method=m, path=p) for m, p in routes]
    return SimpleNamespace(entities=[entity], api=SimpleNamespace(endpoints=endpoints))


_FIELDS = ["id", "title", "datetime", "location", "pace_target", "participants"]
_ROUTES = [("GET", "/runs"), ("POST", "/runs"), ("GET", "/runs/{id}")]


def _model_src(field_names: list[str]) -> str:
    lines = "\n".join(f"    {n}: str" for n in field_names)
    return f"from pydantic import BaseModel\nclass RunEvent(BaseModel):\n{lines}\n"


def _routes_src(routes: list[tuple[str, str]]) -> str:
    body = "\n".join(
        f'@router.{m.lower()}("{p}")\ndef f{i}(): ...' for i, (m, p) in enumerate(routes)
    )
    return f"from fastapi import APIRouter\nrouter = APIRouter()\n{body}\n"


# --------------------------------------------------------------------------- #
# field drift — the multi-drift case is the whole point (single-mismatch would
# have missed pf-13, which drifted TWO fields at once)
# --------------------------------------------------------------------------- #


def test_two_field_drifts_are_both_reported():
    manifest = _manifest(_FIELDS, _ROUTES)
    app = ["id", "title", "datetime", "meeting_location", "pace", "participants"]
    contents = {"backend/models.py": _model_src(app), "backend/routes.py": _routes_src(_ROUTES)}
    findings = [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"]
    assert len(findings) == 1
    f = findings[0]
    assert f.extra == ("meeting_location", "pace")
    assert f.missing == ("location", "pace_target")
    assert "`meeting_location`" in f.instruction and "`pace`" in f.instruction
    assert "`location`" in f.instruction and "`pace_target`" in f.instruction
    assert "Change nothing else." in f.instruction


def test_single_field_drift_still_reported():
    manifest = _manifest(_FIELDS, _ROUTES)
    app = ["id", "title", "datetime", "meeting_location", "pace_target", "participants"]
    contents = {"backend/models.py": _model_src(app), "backend/routes.py": _routes_src(_ROUTES)}
    findings = [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"]
    assert len(findings) == 1
    assert findings[0].extra == ("meeting_location",)
    assert findings[0].missing == ("location",)


def test_clean_model_yields_no_field_finding():
    manifest = _manifest(_FIELDS, _ROUTES)
    contents = {"backend/models.py": _model_src(_FIELDS), "backend/routes.py": _routes_src(_ROUTES)}
    assert [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"] == []


def test_model_config_and_dunder_are_not_fields():
    manifest = _manifest(_FIELDS, _ROUTES)
    src = (
        "from pydantic import BaseModel, ConfigDict\n"
        "class RunEvent(BaseModel):\n"
        "    model_config: ConfigDict = ConfigDict()\n"
        + "\n".join(f"    {n}: str" for n in _FIELDS)
        + "\n"
    )
    contents = {"backend/models.py": src, "backend/routes.py": _routes_src(_ROUTES)}
    assert [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"] == []


def test_class_name_drift_is_skipped():
    manifest = _manifest(_FIELDS, _ROUTES)
    src = _model_src(["id", "title", "datetime", "meeting_location", "pace_target", "participants"])
    src = src.replace("RunEvent", "Event")  # class renamed -> no matching entity
    contents = {"backend/models.py": src, "backend/routes.py": _routes_src(_ROUTES)}
    assert [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"] == []


# --------------------------------------------------------------------------- #
# route drift
# --------------------------------------------------------------------------- #


def test_route_path_drift_is_reported():
    manifest = _manifest(_FIELDS, _ROUTES)
    drifted = [("GET", "/runs"), ("POST", "/run"), ("GET", "/runs/{id}")]  # POST /runs -> /run
    contents = {"backend/models.py": _model_src(_FIELDS), "backend/routes.py": _routes_src(drifted)}
    findings = [f for f in detect_interface_drift(manifest, contents) if f.kind == "route_drift"]
    assert len(findings) == 1
    assert findings[0].extra == ("POST /run",)
    assert findings[0].missing == ("POST /runs",)


def test_conforming_routes_yield_no_finding():
    # pf-15's real shape: routes match the manifest -> the 404 was NOT name drift
    manifest = _manifest(_FIELDS, _ROUTES)
    contents = {"backend/models.py": _model_src(_FIELDS), "backend/routes.py": _routes_src(_ROUTES)}
    assert [f for f in detect_interface_drift(manifest, contents) if f.kind == "route_drift"] == []


# --------------------------------------------------------------------------- #
# robustness
# --------------------------------------------------------------------------- #


def test_none_manifest_or_empty_contents_yields_no_finding():
    assert detect_interface_drift(None, {"x.py": "y"}) == []
    assert detect_interface_drift(_manifest(_FIELDS, _ROUTES), {}) == []
    assert detect_interface_drift(_manifest(_FIELDS, _ROUTES), None) == []


def test_unparseable_file_never_raises():
    manifest = _manifest(_FIELDS, _ROUTES)
    contents = {"backend/models.py": "def (( not python", "backend/routes.py": "@@@"}
    assert detect_interface_drift(manifest, contents) == []


def test_real_group_run_manifest_pf13_multi_drift():
    from pathlib import Path

    from squadops.capabilities.scaffold import InterfaceManifest

    manifest = InterfaceManifest.from_yaml(
        Path("examples/03_group_run/interface_manifest.yaml").read_text(encoding="utf-8")
    )
    # pf-13's exact real drift: location->meeting_location AND pace_target->pace
    app = [
        "id",
        "title",
        "datetime",
        "meeting_location",
        "distance",
        "pace",
        "route_notes",
        "participants",
    ]
    contents = {"backend/app/models.py": _model_src(app)}
    findings = [f for f in detect_interface_drift(manifest, contents) if f.kind == "field_drift"]
    assert len(findings) == 1
    assert findings[0].extra == ("meeting_location", "pace")
    assert findings[0].missing == ("location", "pace_target")

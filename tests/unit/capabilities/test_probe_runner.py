"""Behavioral probe runner (SIP-0098 phase 98.4).

The runner boots a contract subject, issues the declared HTTP requests, compares
status/shape, and emits standard evidence rows keyed by criterion id. Two layers of
test: fast request/compare logic against a stubbed httpx, and two real-boot integration
proofs — the reference fill answers probes (winnability) and the bare skeleton's 501
stubs do not (probes measure the fill, not the scaffold).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.handlers.probe_runner import (
    DEFAULT_PROFILE,
    ProbeOutcome,
    probe_check_rows,
    run_probes,
)
from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.cycles.verification_contract import Probe

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"
_REF_FILL = (
    _REPO / "tests" / "fixtures" / "reference_fills" / "fullstack_fastapi_react" / "group_run"
)


def _probe(**expect) -> Probe:
    return Probe(
        id="vc-probe-x",
        subject="backend",
        request={"method": "POST", "path": "/runs", "json": {"title": "x"}},
        expect=expect,
    )


# --------------------------------------------------------------------------- #
# Request / compare logic (stubbed httpx — no real boot)
# --------------------------------------------------------------------------- #


def _stub_response(monkeypatch, *, status: int, json_body=None):
    def _fake_request(method, url, **kwargs):
        return httpx.Response(status, json=json_body if json_body is not None else {})

    monkeypatch.setattr(pr.httpx, "request", _fake_request)


def test_status_match_passes(monkeypatch):
    _stub_response(monkeypatch, status=200)
    out = pr._run_one("http://x", _probe(status=200), DEFAULT_PROFILE)
    assert out == ProbeOutcome("vc-probe-x", "passed", None)


def test_status_mismatch_fails(monkeypatch):
    _stub_response(monkeypatch, status=501)
    out = pr._run_one("http://x", _probe(status=200), DEFAULT_PROFILE)
    assert out.status == "failed"
    assert "501" in out.reason and "200" in out.reason


def test_json_has_missing_key_fails(monkeypatch):
    _stub_response(monkeypatch, status=200, json_body={"id": "1"})
    out = pr._run_one(
        "http://x", _probe(status=200, json_has=["id", "participants"]), DEFAULT_PROFILE
    )
    assert out.status == "failed"
    assert "participants" in out.reason


def test_json_has_present_passes(monkeypatch):
    _stub_response(monkeypatch, status=200, json_body={"id": "1", "participants": []})
    out = pr._run_one(
        "http://x", _probe(status=200, json_has=["id", "participants"]), DEFAULT_PROFILE
    )
    assert out.status == "passed"


def test_error_code_match_passes(monkeypatch):
    _stub_response(monkeypatch, status=409, json_body={"error": {"code": "duplicate_participant"}})
    out = pr._run_one(
        "http://x", _probe(status=409, error_code="duplicate_participant"), DEFAULT_PROFILE
    )
    assert out.status == "passed"


def test_error_code_mismatch_fails(monkeypatch):
    _stub_response(monkeypatch, status=409, json_body={"error": {"code": "run_not_found"}})
    out = pr._run_one(
        "http://x", _probe(status=409, error_code="duplicate_participant"), DEFAULT_PROFILE
    )
    assert out.status == "failed"
    assert "run_not_found" in out.reason


def test_request_error_fails(monkeypatch):
    def _boom(method, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(pr.httpx, "request", _boom)
    out = pr._run_one("http://x", _probe(status=200), DEFAULT_PROFILE)
    assert out.status == "failed"
    assert "request error" in out.reason


# --------------------------------------------------------------------------- #
# run_probes dispatch + unbootable subjects + check-row shape
# --------------------------------------------------------------------------- #


def test_unbootable_subject_is_skipped_not_failed(tmp_path):
    # a probe whose subject the default profile can't boot is not-executed, never a pass
    frontend_probe = Probe(
        id="vc-probe-fe",
        subject="frontend",
        request={"method": "GET", "path": "/"},
        expect={"status": 200},
    )
    outcomes = run_probes(tmp_path, [frontend_probe])
    assert outcomes == [
        ProbeOutcome("vc-probe-fe", "skipped", "no execution profile boots subject 'frontend'")
    ]


def test_boot_failure_skips_backend_probes(tmp_path):
    # empty workspace -> uvicorn can't import backend.main -> never ready -> skipped (not failed)
    outcomes = run_probes(tmp_path, [_probe(status=200)], profile=_fast_fail_profile())
    assert outcomes[0].status == "skipped"
    assert "did not boot" in outcomes[0].reason


def test_probe_check_rows_carry_status_and_criterion_id():
    rows = probe_check_rows(
        [ProbeOutcome("vc-probe-x", "passed", None), ProbeOutcome("vc-probe-y", "failed", "bad")]
    )
    # status key is REQUIRED for criterion_id to survive normalize_task_checks; check==criterion_id
    # so two probes in one task never collapse on (check_id, subject)
    assert rows == [
        {"check": "vc-probe-x", "status": "passed", "reason": None, "criterion_id": "vc-probe-x"},
        {"check": "vc-probe-y", "status": "failed", "reason": "bad", "criterion_id": "vc-probe-y"},
    ]


def test_outcomes_preserve_contract_order(tmp_path):
    p1 = Probe(
        id="a", subject="backend", request={"method": "GET", "path": "/"}, expect={"status": 200}
    )
    p2 = Probe(
        id="b", subject="frontend", request={"method": "GET", "path": "/"}, expect={"status": 200}
    )
    p3 = Probe(
        id="c", subject="backend", request={"method": "GET", "path": "/"}, expect={"status": 200}
    )
    outcomes = run_probes(tmp_path, [p1, p2, p3], profile=_fast_fail_profile())
    assert [o.id for o in outcomes] == ["a", "b", "c"]


def test_missing_boot_command_skips(tmp_path):
    # a boot command not on PATH -> OSError -> skipped (not-executed), never a crash
    bad = pr.ExecutionProfile(boot_argv=("definitely-not-a-real-binary", "--port", "{port}"))
    outcomes = run_probes(tmp_path, [_probe(status=200)], profile=bad)
    assert outcomes[0].status == "skipped"
    assert "could not launch" in outcomes[0].reason


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #


def test_has_key_on_object_and_list():
    assert pr._has_key({"id": 1, "participants": []}, "id")
    assert not pr._has_key({"id": 1}, "participants")
    # list response: key must be present in every element
    assert pr._has_key([{"id": 1}, {"id": 2}], "id")
    assert not pr._has_key([{"id": 1}, {"x": 2}], "id")
    assert not pr._has_key("not-json", "id")


def test_error_code_of_reads_pinned_envelope():
    assert pr._error_code_of({"error": {"code": "run_not_found"}}) == "run_not_found"
    assert pr._error_code_of({"error_code": "flat"}) == "flat"
    assert pr._error_code_of({"nope": 1}) is None
    assert pr._error_code_of(["x"]) is None


def _fast_fail_profile() -> pr.ExecutionProfile:
    # a short startup timeout so boot-failure tests don't wait the full 25s
    return pr.ExecutionProfile(boot_argv=DEFAULT_PROFILE.boot_argv, startup_timeout_s=1.5)


# --------------------------------------------------------------------------- #
# Real-boot integration: the winnability + measures-the-fill proof
# --------------------------------------------------------------------------- #


def _materialize(dest: Path, *, overlay_fill: bool) -> None:
    manifest = InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8"))
    for f in expand(manifest):
        out = dest / f["name"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f["content"], encoding="utf-8")
    if overlay_fill:
        for src in _REF_FILL.rglob("*"):
            if src.is_file():
                out = dest / src.relative_to(_REF_FILL)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)


def _group_run_probe() -> Probe:
    return Probe(
        id="vc-probe-runs",
        subject="backend",
        request={
            "method": "POST",
            "path": "/runs",
            "json": {"title": "T", "datetime": "D", "location": "L"},
        },
        # creates return 201 (PR #523: the contract contradicted the PRD at 200)
        expect={"status": 201},
    )


@pytest.mark.slow
def test_reference_fill_answers_the_probe():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        _materialize(ws, overlay_fill=True)
        outcomes = run_probes(ws, [_group_run_probe()])
    assert outcomes == [ProbeOutcome("vc-probe-runs", "passed", None)]


@pytest.mark.slow
def test_bare_skeleton_fails_the_probe():
    # the skeleton's routes raise 501 — a probe expecting 200 must FAIL (measures the fill)
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        _materialize(ws, overlay_fill=False)
        outcomes = run_probes(ws, [_group_run_probe()])
    assert outcomes[0].status == "failed"
    assert "501" in outcomes[0].reason


# --------------------------------------------------------------------------- #
# boot-failure stderr disclosure (#512) — bug caught: both night measurement
# rolls reported only "subject did not boot"; the uvicorn stderr (the actual
# diagnosis) went to DEVNULL and diagnosis required manually rebuilding the
# workspace and booting by hand.
# --------------------------------------------------------------------------- #


def test_boot_failure_reason_carries_stderr_tail(tmp_path):
    # A subject that crashes on start with a distinctive stderr message: the
    # disclosed reason must carry the exit state AND the message tail.
    crash = pr.ExecutionProfile(
        boot_argv=(
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('BOOM: no module backend'); sys.exit(3)",
        ),
        startup_timeout_s=2.0,
        poll_interval_s=0.05,
    )
    outcomes = run_probes(tmp_path, [_probe(status=200)], profile=crash)
    assert outcomes[0].status == "skipped"
    assert "subject did not boot (exited 3)" in outcomes[0].reason
    assert "BOOM: no module backend" in outcomes[0].reason


def test_boot_hang_reason_discloses_timeout_not_exit(tmp_path):
    # A subject that never becomes ready but stays alive: reason says so.
    hang = pr.ExecutionProfile(
        boot_argv=(sys.executable, "-c", "import time; time.sleep(30)"),
        startup_timeout_s=0.5,
        poll_interval_s=0.05,
    )
    outcomes = run_probes(tmp_path, [_probe(status=200)], profile=hang)
    assert outcomes[0].status == "skipped"
    assert "no ready response within 0.5s" in outcomes[0].reason


def test_stderr_tail_is_bounded(tmp_path):
    # A subject spewing >4KB of stderr must not blow up the reason string.
    spew = pr.ExecutionProfile(
        boot_argv=(sys.executable, "-c", "import sys; sys.stderr.write('x' * 100000); sys.exit(1)"),
        startup_timeout_s=2.0,
        poll_interval_s=0.05,
    )
    outcomes = run_probes(tmp_path, [_probe(status=200)], profile=spew)
    assert len(outcomes[0].reason) < 600

"""The boot audit keeps the response it judged (#1324).

1.7.2 counted roll 1 was rejected on `probe vc-probe-runs-leave: response missing key(s):
[...]` and could not be root-caused: the manifest, the delivered models and routes all said
the probe was winnable, and what the app actually returned was gone with the container.
The failure line now carries the status and a bounded excerpt of the judged body, and the
driver keeps every FAIL line rather than the last line alone.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from squadops.cycles.verification_contract import Probe

_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("audit_delivered_app_keeps_response", "scripts/dev/audit_delivered_app.py")
driver = _load("verification_set_driver_keeps_response", "scripts/dev/verification_set_driver.py")


def _contract(*probes: Probe):
    return SimpleNamespace(behavioral=SimpleNamespace(probes=tuple(probes)))


# Captured before any test patches ``audit.httpx.AsyncClient`` — the audit module and this
# test share the one httpx module, so the factory must not reach for the patched name.
_RealAsyncClient = httpx.AsyncClient


def _client_factory(handler):
    def factory(**kwargs):
        return _RealAsyncClient(transport=httpx.MockTransport(handler), base_url=kwargs["base_url"])

    return factory


async def test_a_failed_probe_names_the_status_and_the_body_it_judged(monkeypatch):
    """The 1.7.2 roll-1 shape: the app returned *some* of the shape — which part is the
    whole question, and it used to be dropped at the moment it was in hand."""
    probe = Probe(
        id="vc-probe-runs-leave",
        subject="backend",
        request={"method": "POST", "path": "/api/runs/1/leave", "json": {"name": "ada"}},
        expect={"status": 200, "json_has": ["id", "title", "participants"]},
    )
    monkeypatch.setattr(
        audit.httpx,
        "AsyncClient",
        _client_factory(lambda req: httpx.Response(200, json={"participants": [], "ok": True})),
    )
    failures = await audit._run_probes(_contract(probe), "http://app")
    assert len(failures) == 1
    line = failures[0]
    assert line.startswith("probe vc-probe-runs-leave: ")
    assert "— response 200: " in line
    assert line.endswith('{"ok":true,"participants":[]}')


async def test_a_non_json_body_is_kept_as_text_and_a_long_one_is_bounded(monkeypatch):
    probe = Probe(
        id="p", subject="backend", request={"method": "GET", "path": "/x"}, expect={"status": 200}
    )
    monkeypatch.setattr(
        audit.httpx,
        "AsyncClient",
        _client_factory(lambda req: httpx.Response(500, text="<html>boom</html>")),
    )
    (line,) = await audit._run_probes(_contract(probe), "http://app")
    assert "response 500: (non-JSON) '<html>boom</html>'" in line
    long = audit.response_excerpt("", {"k": "v" * 2000})
    assert len(long) < 2000 and long.endswith("chars)") and "…" in long


async def test_a_passing_probe_and_a_transport_error_keep_their_old_shape(monkeypatch):
    ok = Probe(
        id="ok", subject="backend", request={"method": "GET", "path": "/ok"}, expect={"status": 200}
    )
    monkeypatch.setattr(
        audit.httpx, "AsyncClient", _client_factory(lambda req: httpx.Response(200, json={"a": 1}))
    )
    assert await audit._run_probes(_contract(ok), "http://app") == []

    def boom(req):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(audit.httpx, "AsyncClient", _client_factory(boom))
    (line,) = await audit._run_probes(_contract(ok), "http://app")
    assert line.startswith("probe ok: transport error ")


def test_the_driver_keeps_every_fail_line_not_the_last_line_alone():
    output = (
        "assembled 12 files for stack fullstack_fastapi_react\n"
        'FAIL probe vc-probe-runs-create: status 500 (expected 201) — response 500: {"detail":"x"}\n'
        "FAIL probe vc-probe-runs-leave: response missing key(s): ['id'] — response 200: {\"ok\":true}\n"
        "FAIL 2 probe(s)\n"
    )
    out = driver.audit_outcome(1, output, "run_f")
    assert out["passed"] is False and out["detail"] == "FAIL 2 probe(s)"
    assert [f.split(":")[0] for f in out["failures"]] == [
        "FAIL probe vc-probe-runs-create",
        "FAIL probe vc-probe-runs-leave",
        "FAIL 2 probe(s)",
    ]
    assert driver.audit_outcome(0, "audit PASS: 5/5 probes\n", "run_f")["failures"] == []


@pytest.mark.parametrize("payload", [None, {"a": 1}])
def test_the_excerpt_is_deterministic_for_one_response(payload):
    assert audit.response_excerpt("t", payload) == audit.response_excerpt("t", payload)

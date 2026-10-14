"""A list order declared on its endpoint is checked (#2202).

Campaign 3's calibration manifest (``cmp_d4181c169653``) declared datetime sorting as a
``decisions[]`` entry, its delivered ``GET /runs`` returned insertion order, and the cycle was
accepted: no gate reads a decision. An order is now structure on the endpoint, the contract
derives a probe that creates elements out of order and judges the list it reads back, and the
authoring gate refuses an order that probe could not check.
"""

from __future__ import annotations

import copy
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from squadops.campaigns.change_request import (
    DeltaOp,
    DeltaTarget,
    ManifestOperation,
    apply_manifest_delta,
)
from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.handlers.probe_runner import (
    DEFAULT_PROFILE,
    evaluate_expectations,
    run_probes,
)
from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.capabilities.stack_nextjs_ts_tests import _shell_source, derive_scaffold_behaviors
from squadops.cycles.manifest_gates import PROOF_LINT, PROOF_PARSES, assess_winnability
from squadops.cycles.verification_contract import Probe, VerificationContract
from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack, manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"
_REF_FILL = (
    _REPO / "tests" / "fixtures" / "reference_fills" / "fullstack_fastapi_react" / "group_run"
)
ASC = {"field": "datetime", "direction": "asc"}


def _raw() -> dict:
    return yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))


def _with_order(order, *, method: str = "GET", path: str = "/runs", raw: dict | None = None):
    raw = copy.deepcopy(raw) if raw is not None else _raw()
    for ep in raw["api"]["endpoints"]:
        if ep["method"] == method and ep["path"] == path:
            ep["order"] = order
    return raw


def _ordered_probe(raw: dict) -> dict:
    probes = emit_contract_dict(InterfaceManifest.from_dict(raw))["behavioral"]["probes"]
    (probe,) = [p for p in probes if p.get("seed")]
    return probe


# --------------------------------------------------------------------------- the manifest


def test_an_order_moves_the_hash_and_each_direction_is_its_own_contract():
    """The projection must carry the order: two manifests deriving different probes must not
    share the hash a stored contract binds to. The reference manifests' own pinned hashes
    (``test_verification_scaffold_reference``) prove an undeclared order moves nothing."""
    plain = InterfaceManifest.from_dict(_raw()).content_hash()
    asc = InterfaceManifest.from_dict(_with_order(ASC)).content_hash()
    desc = InterfaceManifest.from_dict(_with_order({**ASC, "direction": "desc"})).content_hash()
    assert len({plain, asc, desc}) == 3


@pytest.mark.parametrize(
    ("raw", "refusal"),
    [
        (_with_order(ASC, method="POST"), "only on a GET collection endpoint"),
        (_with_order(ASC, path="/runs/{run_id}"), "only on a GET collection endpoint"),
        (_with_order({**ASC, "direction": "newest"}), "order.direction 'newest' must be one of"),
        (_with_order({**ASC, "field": "starts_at"}), "'starts_at' is not a field of 'RunEvent'"),
        (_with_order({**ASC, "field": "distance"}), "must be a required string or number field"),
        (
            _with_order({**ASC, "field": "participants"}),
            "must be a required string or number field",
        ),
    ],
)
def test_the_authoring_gate_refuses_an_order_nothing_could_check(raw, refusal):
    """Entered at ``assess_winnability``, the gate ``author_manifest`` and a change request's
    candidate manifest both pass through: a declared order nothing tests is the defect."""
    findings = assess_winnability(yaml.safe_dump(raw))
    assert [f.proof for f in findings if refusal in f.detail] == [PROOF_LINT]


def test_an_order_with_no_create_to_seed_from_is_refused():
    raw = _with_order(ASC)
    raw["api"]["endpoints"] = [
        ep for ep in raw["api"]["endpoints"] if (ep["method"], ep["path"]) != ("POST", "/runs")
    ]
    errors = InterfaceManifest.from_dict(raw).lint()
    assert "endpoint GET /runs: order needs a POST /runs to create the elements" in "\n".join(
        errors
    )


def test_a_checkable_order_passes_and_a_bare_word_does_not_parse():
    assert not [
        f for f in assess_winnability(yaml.safe_dump(_with_order(ASC))) if "order" in f.detail
    ]
    (finding,) = assess_winnability(yaml.safe_dump(_with_order("datetime")))
    assert finding.proof == PROOF_PARSES
    assert "order must be a mapping {field, direction}" in finding.detail


# --------------------------------------------------------------------------- the contract


def test_the_contract_seeds_the_list_out_of_order_and_judges_it_last():
    raw = _with_order(ASC)
    probes = emit_contract_dict(InterfaceManifest.from_dict(raw))["behavioral"]["probes"]
    probe = probes[-1]
    assert probe["id"] == "vc-probe-runs-ordered"
    assert probe["request"] == {"method": "GET", "path": "/runs"}
    assert probe["expect"]["status"] == 200
    assert probe["expect"]["ordered_by"] == ASC
    # Falls, then rises: insertion order is neither ascending nor descending.
    assert [s["json"]["datetime"] for s in probe["seed"]] == [
        "2026-08-03T08:00:00",
        "2026-08-01T09:00:00",
        "2026-08-02T08:00:00",
    ]
    # Numbered, so a create that refuses a duplicate title does not refuse the seeds.
    assert [s["json"]["title"] for s in probe["seed"]] == ["sample 1", "sample 2", "sample 3"]
    assert not [p for p in probes[:-1] if p.get("seed")]
    assert not [
        p
        for p in emit_contract_dict(InterfaceManifest.from_dict(_raw()))["behavioral"]["probes"]
        if p.get("seed")
    ]


def test_a_generated_order_field_is_never_sent_by_the_seeds():
    """A create body that carried the generated ``id`` would be refused by a correct app."""
    probe = _ordered_probe(_with_order({"field": "id", "direction": "desc"}))
    assert all("id" not in s["json"] for s in probe["seed"])
    assert probe["expect"]["ordered_by"] == {"field": "id", "direction": "desc"}


def test_a_proposal_that_declares_an_order_gets_its_criterion():
    """SIP-0109's path: a change request modifies the endpoint, and the contract its candidate
    manifest derives carries the probe."""
    baseline = _MANIFEST.read_text(encoding="utf-8")
    definition = {
        "method": "GET",
        "path": "/runs",
        "summary": "list runs",
        "response": "list[RunEvent]",
        "order": ASC,
    }
    candidate = apply_manifest_delta(
        baseline,
        (ManifestOperation(DeltaOp.MODIFY, DeltaTarget.ENDPOINT, "GET /runs", definition),),
    )
    assert _ordered_probe(yaml.safe_load(candidate))["expect"]["ordered_by"] == ASC


def test_a_seed_is_round_tripped_and_a_placeholder_seed_is_a_contract_defect():
    probe = _ordered_probe(_with_order(ASC))
    assert Probe.from_dict(probe).to_dict() == probe
    assert "seed" not in Probe.from_dict({**probe, "seed": []}).to_dict()

    contract = emit_contract_dict(InterfaceManifest.from_dict(_with_order(ASC)))
    contract["behavioral"]["probes"][-1]["seed"][0]["path"] = "/runs/{run_id}"
    errors = VerificationContract.from_dict(contract).lint()
    assert errors == [
        "probe[vc-probe-runs-ordered]: seed[0] must declare 'method' and a 'path' with no "
        "placeholder"
    ]


# --------------------------------------------------------------------------- the judgment


@pytest.mark.parametrize(
    ("payload", "direction", "failure"),
    [
        ([{"d": "a"}, {"d": "b"}], "asc", None),
        ([{"d": "b"}, {"d": "a"}], "asc", "ordered_by 'd' asc: 'b' comes before 'a'"),
        ([{"d": "b"}, {"d": "a"}], "desc", None),
        ([{"d": "a"}, {"d": "b"}], "desc", "ordered_by 'd' desc: 'a' comes before 'b'"),
        ([{"d": "a"}, {"d": "a"}], "asc", None),
        ([{"d": 2}, {"d": 10}], "asc", None),  # numbers numerically, not as text
        ([], "asc", None),
        ({"d": "a"}, "asc", "the response body is not a list"),
        ([{"d": "a"}, {}], "asc", "not every element carries the field"),
        ([{"d": "a"}, {"d": 1}], "asc", "values are not all strings or all numbers"),
        ([{"d": True}, {"d": False}], "asc", "values are not all strings or all numbers"),
    ],
)
def test_ordered_by_is_judged_once_for_every_caller(payload, direction, failure):
    expect = {"status": 200, "ordered_by": {"field": "d", "direction": direction}}
    verdict = evaluate_expectations(expect, 200, payload)
    assert (verdict is None) if failure is None else (failure in verdict)


def test_a_refused_seed_fails_the_probe_before_the_list_is_read(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return httpx.Response(422 if len(calls) == 2 else 201, json={})

    monkeypatch.setattr(pr.httpx, "request", fake_request)
    probe = Probe.from_dict(_ordered_probe(_with_order(ASC)))
    outcome = pr._run_one("http://app", probe, DEFAULT_PROFILE, {})
    assert outcome.status == "failed"
    assert outcome.reason.startswith("seed[1] POST /runs answered 422")
    assert calls == [("POST", "http://app/runs"), ("POST", "http://app/runs")]


def _load_audit():
    spec = importlib.util.spec_from_file_location(
        "audit_delivered_app_list_order", _REPO / "scripts/dev/audit_delivered_app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_delivered_app_list_order"] = mod
    spec.loader.exec_module(mod)
    return mod


async def test_the_boot_audit_issues_the_seeds_and_reaches_the_same_verdict(monkeypatch):
    """The audit is the independent oracle (#1079): an insertion-ordered app must fail it too."""
    audit = _load_audit()
    store: list[dict] = []
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            store.append(yaml.safe_load(request.content))
            return httpx.Response(201, json=store[-1])
        return httpx.Response(200, json=store)

    monkeypatch.setattr(
        audit.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), base_url=kw["base_url"]),
    )
    probe = Probe.from_dict(_ordered_probe(_with_order(ASC)))
    probe = Probe(**{**probe.__dict__, "expect": {"status": 200, "ordered_by": ASC}})
    contract = SimpleNamespace(behavioral=SimpleNamespace(probes=(probe,)))
    (failure,) = await audit._run_probes(contract, "http://app")
    assert failure.startswith(
        "probe vc-probe-runs-ordered: ordered_by 'datetime' asc: '2026-08-03T08:00:00' comes "
        "before '2026-08-01T09:00:00'"
    )
    assert len(store) == 3


# --------------------------------------------------------------------------- Next.js


def test_the_nextjs_shell_requires_each_seed_and_asserts_the_declared_order():
    data = manifest_dict_for_stack("nextjs_ts")
    data = _with_order({"field": "datetime", "direction": "desc"}, path="/api/runs", raw=data)
    behaviors, _ = derive_scaffold_behaviors(InterfaceManifest.from_dict(data))
    (ordered,) = [b for b in behaviors if b.expect_order]
    assert ordered.expect_order == ("datetime", "desc")
    assert [s.method for s in ordered.prerequisites] == ["POST", "POST", "POST"]
    source = _shell_source(ordered, store_symbols=("reset",))
    for index in range(3):
        assert f"expect(seed{index}Res.ok).toBe(true)" in source
    assert "const ordered = (body as any[]).map((element) => element['datetime'])" in source
    assert "[...ordered].sort((a, b) => (a < b ? 1 : a > b ? -1 : 0))" in source


# --------------------------------------------------------------------------- the build side


@pytest.mark.parametrize(
    ("stack", "path"), [("fullstack_fastapi_react", "/runs"), ("nextjs_ts", "/api/runs")]
)
def test_the_route_stub_tells_the_developer_the_declared_order(stack, path):
    data = _with_order(ASC, path=path, raw=manifest_dict_for_stack(stack))
    stubs = "\n".join(f["content"] for f in expand(InterfaceManifest.from_dict(data)))
    assert "Return the list ordered by datetime, ascending: the contract checks it." in stubs
    plain = "\n".join(f["content"] for f in expand(manifest_for_stack(stack)))
    assert "the contract checks it" not in plain


# --------------------------------------------------------------------------- the wiring


def _materialize(dest: Path, manifest: InterfaceManifest, *, sort: bool) -> None:
    for f in expand(manifest):
        out = dest / f["name"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f["content"], encoding="utf-8")
    for src in _REF_FILL.rglob("*"):
        if src.is_file():
            out = dest / src.relative_to(_REF_FILL)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
    if sort:
        routes = dest / "backend" / "routes.py"
        text = routes.read_text(encoding="utf-8")
        assert "    return list(_RUNS.values())" in text
        routes.write_text(
            text.replace(
                "    return list(_RUNS.values())",
                "    return sorted(_RUNS.values(), key=lambda run: run.datetime)",
            ),
            encoding="utf-8",
        )


@pytest.mark.slow
@pytest.mark.parametrize(("sort", "verdict"), [(False, "failed"), (True, "passed")])
def test_a_booted_app_is_held_to_the_order_its_manifest_declares(sort, verdict):
    """The wiring: ``emit_contract_dict`` derives the contract the cycle binds, and
    ``run_probes`` judges a booted application with it. The reference fill returns insertion
    order, as campaign 3's delivered ``GET /runs`` did, and fails; sorted, it passes."""
    manifest = InterfaceManifest.from_dict(_with_order(ASC))
    contract = VerificationContract.from_dict(emit_contract_dict(manifest))
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        _materialize(ws, manifest, sort=sort)
        outcomes = {o.id: o for o in run_probes(ws, list(contract.behavioral.probes))}
    assert outcomes["vc-probe-runs"].status == "passed"
    assert outcomes["vc-probe-runs-ordered"].status == verdict

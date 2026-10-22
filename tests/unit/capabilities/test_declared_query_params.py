"""An endpoint's query parameters are declared on it, and every reader takes them from there (#2378).

Roll 1 of the 2.3 cut set (``cyc_281f3978c9bd``) declared ``DELETE /runs/{run_id}/participants``
with the participant's name "as a query param" in its summary and a decision. No field held it, so
the scaffold seeded ``(run_id)``, the signature check refused the conventional ``name`` argument,
and the accepted repair read the name through a context variable to get past the check. A query
parameter is now structure on the endpoint: the scaffold seeds it, the signature check pins it,
and QA's contract lines and the Next.js route stub name it.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from squadops.cycles.fill_slot_integrity import declared_route_signatures, signature_divergences
from squadops.cycles.verification_contract import VerificationContract
from squadops.stacks.scaffold import InterfaceManifest, expand
from squadops.stacks.scaffold_contract import emit_contract_dict
from squadops.stacks.stack_nextjs_ts import _contract_lines

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"
_LEAVE = "/runs/{run_id}/participants"


def _raw(query=None, *, path: str = _LEAVE, request: str | None = None) -> dict:
    """The reference manifest with #2378's leave endpoint added: a DELETE taking its name from
    the query string when ``query`` is given."""
    raw = copy.deepcopy(yaml.safe_load(_MANIFEST.read_text(encoding="utf-8")))
    endpoint = {"method": "DELETE", "path": path, "summary": "leave a run", "response": "RunEvent"}
    if query is not None:
        endpoint["query"] = query
    if request is not None:
        endpoint["request"] = request
    raw["api"]["endpoints"].append(endpoint)
    return raw


def _routes(raw: dict) -> str:
    return next(
        f["content"]
        for f in expand(InterfaceManifest.from_dict(raw))
        if f["name"].endswith("routes.py")
    )


# --------------------------------------------------------------------------- the manifest


def test_a_query_moves_the_hash_and_none_leaves_it_where_it_was():
    """The projection must carry the query: it changes the seeded signature, so two manifests that
    seed different signatures must not share the hash a stored contract binds to. The reference
    manifests' pinned hashes (``test_verification_scaffold_reference``) show an undeclared query
    moves nothing."""
    without = InterfaceManifest.from_dict(_raw()).content_hash()
    required = InterfaceManifest.from_dict(_raw({"name": "string"})).content_hash()
    optional = InterfaceManifest.from_dict(
        _raw({"name": {"type": "string", "required": False}})
    ).content_hash()
    assert len({without, required, optional}) == 3


def test_both_forms_parse_in_declaration_order_and_a_bare_type_is_required():
    manifest = InterfaceManifest.from_dict(
        _raw({"name": "string", "page": {"type": "integer", "required": False}})
    )
    (leave,) = [ep for ep in manifest.api.endpoints if ep.path == _LEAVE]
    assert [(q.name, q.type, q.required) for q in leave.query] == [
        ("name", "string", True),
        ("page", "integer", False),
    ]
    assert leave.query_suffix() == "?name=<string>&page=<integer, optional>"


def test_a_query_that_is_not_a_mapping_is_refused_when_read():
    with pytest.raises(ValueError, match="must map each name to its type"):
        InterfaceManifest.from_dict(_raw(["name"]))


@pytest.mark.parametrize(
    "query, path, request_shape, refusal",
    [
        ({"run_id": "string"}, _LEAVE, None, "'run_id' is also a path parameter"),
        ({"name": "string"}, _LEAVE, "ParticipantName", "'name' is also a request body field"),
        ({"first-name": "string"}, _LEAVE, None, "'first-name' is not an identifier"),
        ({"name": "list[string]"}, _LEAVE, None, "type 'list[string]' must be one of"),
    ],
    ids=["a-path-parameter", "a-body-field", "not-an-identifier", "a-type-no-stack-reads"],
)
def test_the_authoring_gate_refuses_a_query_no_handler_could_take(
    query, path, request_shape, refusal
):
    """Bug caught: a declared query the scaffold would seed as an argument the handler already has
    under that name, or couldn't parse, expanding into a module that doesn't load."""
    errors = InterfaceManifest.from_dict(_raw(query, path=path, request=request_shape)).lint()
    assert any(refusal in e for e in errors), errors


def test_a_well_formed_query_lints_clean():
    assert InterfaceManifest.from_dict(_raw({"name": "string"})).lint() == []


# --------------------------------------------------------------------------- the readers


def test_the_fastapi_stub_seeds_each_query_parameter_and_imports_query_only_when_one_is_declared():
    routes = _routes(
        _raw({"name": "string", "limit": "integer", "page": {"type": "integer", "required": False}})
    )
    assert "from fastapi import APIRouter, HTTPException, Query" in routes
    assert (
        "def delete_runs_run_id_participants(run_id: str, name: str = Query(...), "
        "limit: int = Query(...), page: int | None = Query(None)):" in routes
    )
    assert "from fastapi import APIRouter, HTTPException\n" in _routes(_raw())


def test_the_signature_check_pins_a_declared_query_parameter():
    """Bug caught (#2378): the scaffold seeded ``(run_id)`` and refused the handler that took the
    name the manifest's prose chose. Seeded from the declaration, the name is scaffold-owned: a fill
    that keeps it passes, and the accepted repair's workaround, dropping it for a context variable,
    is refused."""
    seed = _routes(_raw({"name": "string"}))
    declared = declared_route_signatures(seed)
    (leave,) = [s for s in declared if s["route"] == f"DELETE {_LEAVE}"]
    assert leave["params"] == ["run_id", "name"]

    kept = seed.replace(
        '    raise HTTPException(status_code=501, detail="not implemented")\n',
        "    return {}\n",
        1,
    )
    workaround = seed.replace("(run_id: str, name: str = Query(...))", "(run_id: str)")
    assert signature_divergences(declared, kept) == []
    assert any("name" in d for d in signature_divergences(declared, workaround))


def test_qa_and_the_nextjs_route_stub_are_told_the_query():
    """The two other readers: QA's contract lines, which the plan's qa tasks render
    (``behavior_expectation_lines``), and the Next.js handler's contract comments (#2522)."""
    manifest = InterfaceManifest.from_dict(_raw({"name": "string"}))
    lines = VerificationContract.from_dict(
        emit_contract_dict(manifest)
    ).behavior_expectation_lines()
    (happy,) = [line for line in lines if line.startswith("happy path for each endpoint:")]
    assert f"DELETE {_LEAVE}?name=<string>" in happy

    (leave,) = [ep for ep in manifest.api.endpoints if ep.path == _LEAVE]
    shapes = {s.name: s for s in manifest.api.request_shapes}
    entities = {e.name: e for e in manifest.entities}
    assert "    // query: name=<string>" in _contract_lines(leave, shapes, entities=entities)

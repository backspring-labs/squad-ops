"""An error's message declared in the manifest's error contract (#2205 gap 3, the owner's ruling
(a), 2026-10-14): the frozen error module renders it word for word, and the derived probes assert it.

What bugs would these catch? The frozen module ignoring a declared message, so the build's own
wording reaches the user; a probe that never asserts it, so a later increment rewords it unseen; a
judge that passes a wrong message; and a manifest whose declared message is lost on its round trip.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from squadops.capabilities.handlers.probe_runner import evaluate_expectations
from squadops.capabilities.scaffold import InterfaceManifest, error_seam_instructions
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.capabilities.stack_fastapi_react import _errors_source as fastapi_errors
from squadops.capabilities.stack_nextjs_ts import _errors_source as nextjs_errors

_BASELINE = (
    Path(__file__).parents[2]
    / "fixtures"
    / "campaigns"
    / "baseline-cmp_ff3ddfdfbc70-interface_manifest.yaml"
).read_text()
DUPLICATE = "A participant with this name has already joined this run."
INVALID = "Every field needs a value."


class JoinBody(BaseModel):
    name: str


def _manifest(**messages: str) -> InterfaceManifest:
    raw = yaml.safe_load(_BASELINE)
    for code, text in messages.items():
        raw["api"]["error_contract"]["codes"][code]["message"] = text
    return InterfaceManifest.from_dict(raw)


def _fastapi_app(source: str, tmp_path: Path):
    """The generated module, imported as the delivered app imports it, behind a real app."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    path = tmp_path / "errors_under_test.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("errors_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["errors_under_test"] = module
    spec.loader.exec_module(module)

    app = FastAPI()
    module.register_error_handlers(app)

    @app.post("/join/{code}")
    def join(code: str, body: JoinBody):
        raise module.ApiError(code, "the build's own wording")

    return TestClient(app)


def test_the_fastapi_module_renders_a_declared_message_whatever_the_raise_passes(tmp_path):
    client = _fastapi_app(
        fastapi_errors(_manifest(duplicate_participant=DUPLICATE, validation_error=INVALID)),
        tmp_path,
    )

    declared = client.post("/join/duplicate_participant", json={"name": "a"})
    undeclared = client.post("/join/run_not_found", json={"name": "a"})
    invalid = client.post("/join/duplicate_participant", json={})

    assert (declared.status_code, declared.json()) == (
        409,
        {"error": {"code": "duplicate_participant", "message": DUPLICATE}},
    )
    assert undeclared.json()["error"]["message"] == "the build's own wording"
    assert (invalid.status_code, invalid.json()["error"]["message"]) == (422, INVALID)


def test_the_fastapi_module_keeps_the_raises_message_when_the_contract_declares_none(tmp_path):
    client = _fastapi_app(fastapi_errors(_manifest()), tmp_path)

    declared = client.post("/join/duplicate_participant", json={"name": "a"})

    assert declared.json()["error"]["message"] == "the build's own wording"
    assert "_ERROR_MESSAGE" not in fastapi_errors(_manifest())


def test_the_nextjs_module_renders_a_declared_message_before_the_throws():
    source = nextjs_errors(_manifest(duplicate_participant='Already "joined".'))

    assert 'duplicate_participant: "Already \\"joined\\"."' in source
    assert (
        "const message = ERROR_MESSAGE[code] ?? (err instanceof ApiError ? err.message : '')"
        in source
    )
    assert "ERROR_MESSAGE" not in nextjs_errors(_manifest())


def test_the_derived_rejection_probes_assert_a_declared_message():
    """Entered at ``emit_contract_dict``, which seeds every cycle's contract."""
    probes = {
        p["id"]: p["expect"]
        for p in emit_contract_dict(_manifest(duplicate_participant=DUPLICATE))["behavioral"][
            "probes"
        ]
    }
    plain = {p["id"]: p["expect"] for p in emit_contract_dict(_manifest())["behavioral"]["probes"]}

    assert probes["vc-probe-runs-join-duplicate"] == {
        "status": 409,
        "error_code": "duplicate_participant",
        "error_message": DUPLICATE,
    }
    assert "error_message" not in probes["vc-probe-runs-rejects-blank"]
    assert all("error_message" not in expect for expect in plain.values())


@pytest.mark.parametrize(
    ("payload", "failure"),
    [
        ({"error": {"code": "duplicate_participant", "message": DUPLICATE}}, None),
        (
            {"error": {"code": "duplicate_participant", "message": "Already joined."}},
            f"error message 'Already joined.' != expected {DUPLICATE!r}",
        ),
        (
            {"error": {"code": "duplicate_participant"}},
            f"error message None != expected {DUPLICATE!r}",
        ),
        ({"detail": DUPLICATE}, "error_code None != expected 'duplicate_participant'"),
    ],
    ids=["the declared wording", "other wording", "no message", "not the envelope"],
)
def test_the_judge_holds_a_response_to_the_declared_message(payload, failure):
    expect = {"status": 409, "error_code": "duplicate_participant", "error_message": DUPLICATE}

    assert evaluate_expectations(expect, 409, payload) == failure


def test_a_declared_message_moves_the_manifests_hash_and_reaches_a_repair():
    """The hash binds a contract to its manifest: a message it ignored would keep a contract
    derived without the message's probe."""
    manifest = _manifest(duplicate_participant=DUPLICATE)

    assert manifest.content_hash() != _manifest().content_hash()
    assert manifest.content_hash() != _manifest(duplicate_participant="Joined.").content_hash()
    assert repr(DUPLICATE) in error_seam_instructions(manifest)[-1]
    assert "declared error messages" not in " ".join(error_seam_instructions(_manifest()))

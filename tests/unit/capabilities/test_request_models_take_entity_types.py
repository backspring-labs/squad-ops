"""The scaffold's request models take the types their entities declare (#1876).

Request shapes are projections of entity fields. The models typed every field ``str``, so the
reference increment's ``RunCreate`` refused the integer ``capacity`` its criterion sends — an
error no repair could reach, because the model is scaffold-frozen.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    validate_proposal,
)
from squadops.capabilities.scaffold import InterfaceManifest, expand

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()


def _candidate_models() -> dict:
    """The reference increment's candidate ``models.py``, executed."""
    request = validate_proposal(
        yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            BASELINE,
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
    candidate = InterfaceManifest.from_yaml(apply_manifest_delta(BASELINE, request.manifest_delta))
    source = {f["name"]: f["content"] for f in expand(candidate)}["backend/models.py"]
    # A real module: the source defers its annotations, and pydantic resolves them there.
    module = types.ModuleType("candidate_models")
    sys.modules[module.__name__] = module
    try:
        exec(compile(source, "backend/models.py", "exec"), module.__dict__)  # noqa: S102
    finally:
        sys.modules.pop(module.__name__, None)
    return module.__dict__


def test_an_integer_field_is_accepted_as_an_integer_and_nothing_else():
    """Bugs caught: the integer refused (typed ``str``, pydantic v2 does not coerce), or
    anything accepted in its place."""
    run_create = _candidate_models()["RunCreate"]
    body = {"title": "Morning", "datetime": "2026-10-03T07:00", "location": "Park"}

    assert run_create(**body, capacity=2).capacity == 2
    assert run_create(**body).capacity is None
    with pytest.raises(ValidationError):
        run_create(**body, capacity="two")


def test_a_required_string_still_refuses_blank_input():
    """#593 kept: typing by entity must not lose the blank-input 422 on required strings."""
    run_create = _candidate_models()["RunCreate"]

    with pytest.raises(ValidationError):
        run_create(title="  ", datetime="2026-10-03T07:00", location="Park")

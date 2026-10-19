"""SIP-0113's evaluator image (A2, #2416), whose tag is each quality measure's version."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from squadops.sandbox import environment
from squadops.sandbox.environment import EVALUATOR_IMAGE, get_environment_contract

_EVALUATOR = Path(__file__).resolve().parents[3] / "infra" / "evaluator"
_SOURCES = ("Dockerfile", "driver.mjs", "package.json", "package-lock.json")
#: The digest of the sources each tag was cut from. A change to them is a new measure: cut a new
#: tag here and in ``EVALUATOR_IMAGE``, and the window's record names it.
_CUT = {"squadops-evaluator:lighthouse13.5-axe4.14-1": "2011ffd3c1fa431a"}


def _digest() -> str:
    joined = b"".join((_EVALUATOR / name).read_bytes() for name in _SOURCES)
    return hashlib.sha256(joined).hexdigest()[:16]


def test_the_evaluator_tag_moves_whenever_its_sources_do():
    """The 2.4 plan's §1.3: the window records each quality measure's version, and a change to
    it ends the series. Bug caught: the driver or a pinned package changed under the same tag,
    so two different measures are compared as one."""
    assert _CUT.get(EVALUATOR_IMAGE) == _digest(), (
        f"infra/evaluator's sources changed (digest {_digest()}): cut a new EVALUATOR_IMAGE tag "
        "and record it in _CUT"
    )


@pytest.mark.parametrize("stack", sorted(environment._CONTRACTS))
def test_each_stacks_pages_are_served_by_the_app_or_by_its_ui_serve(stack):
    """Bug caught: a stack whose UI port nothing serves, so every evaluation waits out its
    readiness and records ``ui_not_ready``; or a second server on the app's own port, so the
    start fails on a port already in use."""
    contract = get_environment_contract(stack)

    assert (contract.ui_port == contract.app_port) != bool(contract.ui_serve)

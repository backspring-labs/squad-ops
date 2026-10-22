"""SIP-0113's evaluator image (A2, #2416), whose tag is each quality measure's version."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from squadops.sandbox import environment
from squadops.sandbox.environment import EVALUATOR_IMAGE, get_environment_contract

_REPO = Path(__file__).resolve().parents[3]
_EVALUATOR = _REPO / "infra" / "evaluator"
#: The image's sources, and what each lint request carries: #1937's ESLint runner (its config) and
#: ruff's command (its rules). A change to any of them is a new measure.
_SOURCES = (
    _EVALUATOR / "Dockerfile",
    _EVALUATOR / "driver.mjs",
    _EVALUATOR / "browser.mjs",
    _EVALUATOR / "puppeteer_page.mjs",
    _EVALUATOR / "package.json",
    _EVALUATOR / "package-lock.json",
    _REPO / "src" / "squadops" / "capabilities" / "delivered_lint_eslint.cjs",
)
#: The digest of the sources each tag was cut from: cut a new tag here and in ``EVALUATOR_IMAGE``
#: when they change, and the window's record names it.
_CUT = {
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-2": "ed170cddc62fe9f3",
    # SIP-0113 §10p ruling 6: the browser runner's driver. The quality and lint series end here.
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-3": "3c87fc625505fd42",
}


def _digest() -> str:
    from squadops.capabilities.delivered_lint import RUFF_ARGS

    joined = b"".join(path.read_bytes() for path in _SOURCES) + " ".join(RUFF_ARGS).encode()
    return hashlib.sha256(joined).hexdigest()[:16]


def test_the_evaluator_tag_moves_whenever_its_sources_do():
    """The 2.4 plan's §1.3: the window records each quality measure's version, and a change to
    it ends the series. Bug caught: the driver or a pinned package changed under the same tag,
    so two different measures are compared as one."""
    assert _CUT.get(EVALUATOR_IMAGE) == _digest(), (
        f"infra/evaluator's sources changed (digest {_digest()}): cut a new EVALUATOR_IMAGE tag "
        "and record it in _CUT"
    )


def _qa_pins() -> dict[str, str]:
    lines = (_REPO / "agents" / "instances" / "qa" / "npm-global-packages.txt").read_text()
    pins = (line.rsplit("@", 1) for line in lines.splitlines() if line and not line.startswith("#"))
    return dict(pins)


def test_the_evaluators_lint_tools_are_the_qa_images_so_the_two_readings_are_one_measure():
    """#1937's reading is taken in the qa image and, since #2416, in the evaluator's. Bug caught:
    one image's ESLint, a config package or TypeScript moved and the other's not, or a different
    ruff, so an increment's lint delta is a tool change read as a code change."""
    import json
    import re

    evaluator = json.loads((_EVALUATOR / "package.json").read_text())["dependencies"]
    qa = _qa_pins()
    shared = ("eslint", "@eslint/js", "typescript-eslint", "globals", "typescript")
    locked = re.search(r"^ruff==(\S+)$", (_REPO / "requirements" / "agent.lock").read_text(), re.M)
    image = re.search(r"ghcr\.io/astral-sh/ruff:(\S+)@", (_EVALUATOR / "Dockerfile").read_text())

    assert {p: evaluator.get(p) for p in shared} == {p: qa.get(p) for p in shared}
    assert image is not None and locked is not None and image.group(1) == locked.group(1)


@pytest.mark.parametrize("stack", sorted(environment._CONTRACTS))
def test_each_stacks_pages_are_served_by_the_app_or_by_its_ui_serve(stack):
    """Bug caught: a stack whose UI port nothing serves, so every evaluation waits out its
    readiness and records ``ui_not_ready``; or a second server on the app's own port, so the
    start fails on a port already in use."""
    contract = get_environment_contract(stack)

    assert (contract.ui_port == contract.app_port) != bool(contract.ui_serve)

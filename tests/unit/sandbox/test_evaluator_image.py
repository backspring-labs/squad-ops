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
    _EVALUATOR / "page_reading.mjs",
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
    # §10p ruling 1: the driver's error text kept to the evidence. Nothing was measured on -3.
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-4": "fe21f8ea911a4e61",
    # #2583: the base and Debian's archive pinned (its 260 packages are -4's), and §10p ruling 5's
    # measured bound of 5 s (§10r).
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-5": "2fa34a2d556173c6",
    # 2.5's re-cut: a control's name matched with a trailing colon dropped (#2706), the `if_enabled`
    # click (#2659), and the lock's advisories fixed, the peer puppeteer pinned to 25.14.0 and fast-uri
    # 3.1.9 (#2712, #2469). Every baseline is re-read on it (the 2.5 plan's §2.2).
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-6": "cecd430f253e0567",
    # §10y's finer reading (#2637): the driver reads axe by node, the failing audits by id and the
    # environment's apart (page_reading.mjs). browser.mjs, the Chromium pin and the lock are -6's,
    # byte for byte. Every quality series on -6 or earlier stays its own.
    "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-7": "8006d83c1f37dc28",
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


def test_one_tag_is_one_image_every_input_the_dockerfile_fetches_is_pinned():
    """#2583. Bug caught: an unpinned base, archive or package, so two builds of one tag carry
    different Chromium or libraries, and Lighthouse's scores move under a tag that says nothing
    changed."""
    dockerfile = (_EVALUATOR / "Dockerfile").read_text()
    stages = [line.split()[1] for line in dockerfile.splitlines() if line.startswith("FROM ")]
    assert stages and all("@sha256:" in image for image in stages), stages
    assert "snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}" in dockerfile
    assert "snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}" in dockerfile
    install = dockerfile.split("apt-get install", 1)[1].split("&&", 1)[0]
    packages = [w for w in install.replace("\\", " ").split() if not w.startswith("-")]
    assert packages and all("=" in p for p in packages), packages


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


def test_the_browser_a_products_pages_are_read_with_is_the_one_the_image_installs():
    """SIP-0109 §24co: the runner runs the image's Chromium by its path. Bug caught: the path
    drifting from the image's, so every product's route reads unread with "the browser exited
    127", and the increment blocks with a reason that names the image, not the product."""
    from squadops.sandbox.environment import EVALUATOR_BROWSER

    dockerfile = (_EVALUATOR / "Dockerfile").read_text()
    assert f"CHROME_PATH={EVALUATOR_BROWSER}" in dockerfile
    assert f"PUPPETEER_EXECUTABLE_PATH={EVALUATOR_BROWSER}" in dockerfile

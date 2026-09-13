"""The framework smoke, run against a real cycle (#176).

Recipe 1 of #176 — the **invariant smoke**. Point it at a cycle the box has already run
and it answers one question: *did the pipeline behave, whatever the run's verdict?*

    SQUADOPS_SMOKE_PROJECT=play_game SQUADOPS_SMOKE_CYCLE=cyc_02682aa4efa2 \
        pytest tests/integration/cycles/test_framework_smoke.py -m smoke -v

Deliberately **not** keyed on terminal status. Small models exercise the plumbing
reliably and cannot clear content-quality gates, so a status-keyed harness reports "the
framework is broken" on exactly the squads cheap enough to gate merges with. The
reference case is `cyc_02682aa4efa2`: ended FAILED because a 7b builder emitted 194
completion tokens and the output validator correctly rejected it, and every framework
invariant held.

The invariants themselves are `scripts/dev/framework_smoke.py`, unit-tested against that
cycle's committed artifact references in `tests/unit/cycles/`. This file is the thin part:
it supplies a live cycle and asserts. Reading the vault rather than the registry is what
lets it run wherever the artifacts are, without database credentials.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.smoke]

_REPO = Path(__file__).resolve().parents[3]


def _harness():
    spec = importlib.util.spec_from_file_location(
        "framework_smoke", _REPO / "scripts/dev/framework_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cycle_refs():
    project = os.getenv("SQUADOPS_SMOKE_PROJECT")
    cycle_id = os.getenv("SQUADOPS_SMOKE_CYCLE")
    if not (project and cycle_id):
        pytest.skip(
            "set SQUADOPS_SMOKE_PROJECT and SQUADOPS_SMOKE_CYCLE to the cycle to smoke, "
            "e.g. SQUADOPS_SMOKE_PROJECT=play_game SQUADOPS_SMOKE_CYCLE=cyc_02682aa4efa2"
        )
    vault = Path(os.getenv("SQUADOPS_SMOKE_VAULT", _REPO / "data/artifacts"))
    return _harness().load_refs_from_vault(vault, project, cycle_id), cycle_id


def test_the_pipeline_invariants_held(cycle_refs):
    """Bug caught: the pipeline stopped doing something and the run still looked ordinary.

    Each invariant is one thing that must be true of any run, green or red — every
    framing stage authored its artifact, the dev stage delivered source, a correction
    that fired banked its reasoning, and every task-produced artifact names its producer.
    A failure names what it saw, so nobody has to go and read the run.
    """
    refs, cycle_id = cycle_refs
    results = _harness().check_all(refs)

    broken = [str(r) for r in results if not r.held]
    assert broken == [], f"framework invariants broken on {cycle_id}:\n  " + "\n  ".join(broken)


def test_the_cycle_actually_produced_something(cycle_refs):
    """Bug caught: an empty or wrong cycle id passes every invariant vacuously.

    `multi_role_framing` on an empty ref list reports 0 of 5 and fails, but a cycle that
    stored nothing at all is a different fault from one whose framing broke — and a smoke
    harness pointed at a typo must say so rather than blame the pipeline.
    """
    refs, cycle_id = cycle_refs
    assert refs, f"no artifacts stored for {cycle_id} — check the project and cycle id"

"""Composition roots — the guard docs/architecture/composition-roots.md §6.6 specifies.

This module carries **assertion 1, import purity (R3)**. Assertions 2–4 — factory-only
construction, expected bindings present, selectors required — become true with #301 and land
with it; a guard asserting them before the queue/A2A/filesystem factories exist would be
red on main for the whole of §3.3, which is a guard nobody reads.

The root list is ``test_forbidden_imports.COMPOSITION_ROOTS`` — imported, not duplicated,
so a root added there is asserted here the same day (the ``_COUNTING_SETS`` lesson). Each
root maps to the module a process actually imports to start it.

Bug class guarded: a composition root that does work at import. #286 is the instance —
``squadops.api.runtime.main`` called ``load_config()`` at module scope, so a bare import
resolved secrets, validated the deployment profile and failed with
``ConfigValidationError: secret:// references found`` in any environment but the deployed
one. Every consumer that only needed a symbol (the CLI integration tests) grew a
``sys.modules``-and-env workaround, and #637's lock-and-import job could not exist.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.unit.architecture.test_forbidden_imports import COMPOSITION_ROOTS

pytestmark = [pytest.mark.unit]

#: The module a process imports to start each root. A root in COMPOSITION_ROOTS with no
#: entry here fails the completeness test below rather than silently going unasserted.
_ENTRY_MODULE = {
    "squadops.api.runtime": "squadops.api.runtime.main",
    "squadops.agents.entrypoint": "squadops.agents.entrypoint",
    "squadops.sandbox.main": "squadops.sandbox.main",
    "squadops.bootstrap": "squadops.bootstrap",
}


def test_every_root_has_an_entry_module():
    assert set(_ENTRY_MODULE) == set(COMPOSITION_ROOTS), (
        "COMPOSITION_ROOTS and _ENTRY_MODULE disagree — a root was added to one and not the other"
    )


@pytest.mark.parametrize("module", sorted(_ENTRY_MODULE.values()))
def test_a_bare_import_reads_no_environment(module):
    """A subprocess with an EMPTY environment — no ``SQUADOPS__*``, no ``.env`` — must import
    the root and exit 0. Same interpreter, so site-packages resolve; nothing else."""
    proc = subprocess.run(  # noqa: S603 — fixed argv, our own interpreter
        [sys.executable, "-c", f"import {module}"],
        env={},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, (
        f"`import {module}` with an empty environment failed — the root does work at import:\n"
        f"{proc.stderr[-1500:]}"
    )

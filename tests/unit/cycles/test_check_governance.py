"""#730 (1.5 A5) — the curated check menu's governance guards.

The #686 pattern applied to the governance axis: the registry is the source,
the doc table is generated FROM it, and these tests are what keep the two —
plus the registry's own structural laws — from drifting apart silently.

Regenerate the doc: UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from squadops.cycles.acceptance_check_spec import (
    CHECK_SPECS,
    DECLARED_UNBUILT_CHECKS,
    CheckSpec,
    render_check_governance_menu,
)

pytestmark = [pytest.mark.domain_contracts]

_MENU_PATH = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "typed-check-menu.md"


def test_menu_doc_is_generated_from_the_registry():
    """The design doc's rule mechanized: prose documentation is generated from
    the registry, never hand-maintained beside it. Bug caught: a registry
    change without a doc regen (the menu lies about the vocabulary), or a
    hand-edit to the doc (drift the other way — #686's own defect class)."""
    rendered = render_check_governance_menu()
    if os.environ.get("UPDATE_CHECK_MENU"):
        _MENU_PATH.write_text(rendered)
        return
    assert _MENU_PATH.exists(), (
        "docs/architecture/typed-check-menu.md missing — run "
        "UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py"
    )
    assert _MENU_PATH.read_text() == rendered, (
        "typed-check-menu.md drifted from the registry — regenerate with "
        "UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py "
        "(if you edited the doc by hand: don't — edit the registry)"
    )


def test_non_replayable_checks_stay_out_of_the_failure_signature():
    """Registry law (recorded in CheckSpec's docstring): a failure that does
    not reproduce deterministically must not key chain-termination identity.
    Bug caught: flipping command_exit_zero/frontend_compiles into signature
    participation — A4 would terminate correction chains as plan_defect on
    environment noise (a missing tool 'repeating' across rounds)."""
    violators = sorted(
        name
        for name, spec in CHECK_SPECS.items()
        if not spec.replayable and spec.signature_participation
    )
    assert not violators, (
        f"non-replayable check(s) {violators} participate in the correction "
        "failure-signature — environment-variant failures must not key chain "
        "termination (change requires a ruled design amendment, not an edit)"
    )


def test_declared_unbuilt_entries_never_shadow_real_checks():
    """Bug caught: a declared-unbuilt check gets built (added to CHECK_SPECS)
    but its unbuilt row remains — the menu would state the check both exists
    and cannot exist. The build PR must remove the unbuilt record."""
    collisions = {e.name for e in DECLARED_UNBUILT_CHECKS} & set(CHECK_SPECS)
    assert not collisions, (
        f"{sorted(collisions)} present in BOTH CHECK_SPECS and "
        "DECLARED_UNBUILT_CHECKS — remove the unbuilt record in the PR that "
        "builds the check"
    )
    for entry in DECLARED_UNBUILT_CHECKS:
        assert entry.reason and entry.trigger, (
            f"declared-unbuilt {entry.name!r} must state why it cannot exist "
            "yet AND the named trigger that unlocks it — visibility without "
            "either is just a dangling name"
        )


def test_every_entry_must_declare_its_governance_explicitly():
    """Pins the forcing mechanism: the six governance fields are required
    keyword-only. Bug caught: a refactor giving them defaults — after which a
    new check silently ships with unexamined governance and every consumer
    (repair targeting, A1 accounting, A4 signatures, replay) inherits a guess."""
    with pytest.raises(TypeError):
        CheckSpec(name="x", required_params=frozenset({"file"}))  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="failure_ownership"):
        CheckSpec(
            name="x",
            required_params=frozenset(),
            failure_ownership="vibes",
            qa_available=True,
            signature_participation=True,
            outcome_contribution=True,
            replayable=True,
            blocking_default="error",
        )

    with pytest.raises(ValueError, match="blocking_default"):
        CheckSpec(
            name="x",
            required_params=frozenset(),
            failure_ownership="product",
            qa_available=True,
            signature_participation=True,
            outcome_contribution=True,
            replayable=True,
            blocking_default="fatal",
        )

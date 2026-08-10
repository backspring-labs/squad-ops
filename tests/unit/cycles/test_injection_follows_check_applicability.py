"""Injection asks the check whether it can parse the artifact (#833).

Three sites in `task_plan` filtered on `art.endswith(".py")` before injecting a framework
check. The literal was **correct** — every check being injected declares
`applicable_extensions={".py"}` — but it stated the boundary a second time, in a place that
cannot notice when the first one moves.

Recorded because #833 was filed on the opposite premise, that these were stack #1 layout
hardwiring undoing a stack-aware seam. They are not: `is_qa_test_path_for_stack` answers
"is this a QA test path for this stack" and the suffix answered "can the check parse it".
Both are needed. What was wrong was restating the second one by hand.

Bug classes guarded:

- **the injection filter drifting from the check's declared applicability** — the whole point.
  If a check gains a `.ts` implementation, injection must follow without anyone remembering
  this file exists;
- injecting a check that cannot run, which `manifest_gates` `PROOF_CHECKS_LIVE` would then
  reject as unwinnable — the manifest gate and this filter must agree, and now they read the
  same source;
- **stack #1's plan changing.** These checks are the enforcement surface the release's banked
  evidence was measured through; the swap must be behavior-identical for `.py`.
"""

from __future__ import annotations

import pytest

from squadops.cycles.acceptance_check_spec import (
    CHECK_CONTRACT_ASSERTIONS,
    CHECK_FILL_SLOT_SIGNATURE,
    CHECK_HARNESS_BOUNDARY,
    CHECK_SPECS,
    is_check_applicable,
)

pytestmark = [pytest.mark.domain_contracts]

_INJECTED = (CHECK_CONTRACT_ASSERTIONS, CHECK_FILL_SLOT_SIGNATURE, CHECK_HARNESS_BOUNDARY)


@pytest.mark.parametrize("check", _INJECTED)
def test_todays_boundary_is_unchanged_for_python(check):
    """Behavior-identical for stack #1: every injected check still accepts `.py` and still
    refuses the suffixes a Python parser cannot read."""
    assert is_check_applicable(check, "backend/tests/test_runs.py")
    assert not is_check_applicable(check, "app/api/runs/route.ts")
    assert not is_check_applicable(check, "frontend/src/views/V.jsx")


@pytest.mark.parametrize("check", _INJECTED)
def test_injection_follows_the_check_when_its_applicability_moves(check, monkeypatch):
    """The reason for the change. A hand-written `.py` cannot notice that the check learned
    to parse something else; this reads the declaration, so a future TypeScript implementation
    is picked up by the injection sites without touching them."""
    import dataclasses

    spec = CHECK_SPECS[check]
    monkeypatch.setitem(
        CHECK_SPECS,
        check,
        dataclasses.replace(spec, applicable_extensions=frozenset({".py", ".ts"})),
    )

    assert is_check_applicable(check, "app/api/runs/route.ts")


def test_every_injected_check_is_named_by_a_constant():
    """A literal in an injection filter silently injects nothing after a rename — the reason
    the constant block gives for the four names that preceded these."""
    assert {CHECK_CONTRACT_ASSERTIONS, CHECK_FILL_SLOT_SIGNATURE, CHECK_HARNESS_BOUNDARY} <= set(
        CHECK_SPECS
    )


def test_the_injection_sites_no_longer_restate_the_suffix():
    """The drift this closes is textual: a second statement of the boundary in a file that
    cannot see the first. Asserted against the source so a reintroduction is caught."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] / "src" / "squadops" / "cycles" / "task_plan.py"
    ).read_text(encoding="utf-8")

    assert 'endswith(".py") and is_qa_test_path_for_stack' not in source
    assert 'endswith(".py") and _normalize(art) in fill' not in source

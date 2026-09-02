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
    CHECK_DECLARED_IMPORTS,
    CHECK_SPECS,
    CHECK_UNDEFINED_NAMES,
    DECLARED_COVERAGE_GAPS,
    DECLARED_UNBUILT_CHECKS,
    EMISSION_LANGUAGES,
    CheckSpec,
    framework_file_scoped_checks,
    render_check_governance_menu,
    uncovered_languages,
)

pytestmark = [pytest.mark.domain_contracts]


class TestCoverageGapsAreDeclared:
    """#1216: a check that does not cover a stack was silently skipped.

    `is_check_applicable` returns False for a non-matching extension and the injection
    loop `continue`s, so a `.ts` emission received less checking than an identical
    `.py` one and the green looked the same. Two neighbouring layers already refuse
    loudly in this situation — the verification-set driver's #818 rule ("a stack with
    no registered P0 check is refused loudly, never silently passed") and scaffold
    emission's #838 registry-disagreement rule. This layer stayed quiet, and #939 sat
    open five weeks before a shakeout paid for it.
    """

    def test_every_coverage_gap_is_declared(self):
        """Bug caught: a stack-specific check added without saying what it leaves
        uncovered — which is how #939 became invisible. Fails at CI rather than at a
        roll three weeks later."""
        undeclared = {}
        for name, extensions in framework_file_scoped_checks().items():
            gaps = EMISSION_LANGUAGES - extensions
            missing = sorted(gaps - set(DECLARED_COVERAGE_GAPS.get(name, {})))
            if missing:
                undeclared[name] = missing
        assert not undeclared, (
            "These checks do not cover a language and do not say so:\n"
            + "\n".join(f"  {n}: {', '.join(e)}" for n, e in sorted(undeclared.items()))
            + "\n\nAdd them to DECLARED_COVERAGE_GAPS with the reason, or widen the "
            "check.\nAn undeclared gap means an emission in that language is checked "
            "less than\nan identical one elsewhere, and nothing says so."
        )

    def test_no_declared_gap_outlives_the_gap(self):
        """Bug caught: a stale entry claiming a gap that has been closed. An
        accumulating list is how a declared gap becomes an undeclared one — nobody
        re-reads a reason that has been there a year."""
        stale = {}
        for name, gaps in DECLARED_COVERAGE_GAPS.items():
            spec = CHECK_SPECS.get(name)
            assert spec is not None, f"DECLARED_COVERAGE_GAPS names unknown check {name}"
            covered = sorted(set(gaps) & spec.applicable_extensions)
            if covered:
                stale[name] = covered
        assert not stale, (
            "These gaps are declared but the check now covers them — remove the "
            "entries:\n" + "\n".join(f"  {n}: {', '.join(e)}" for n, e in sorted(stale.items()))
        )

    def test_every_declared_gap_carries_a_reason(self):
        """Bug caught: the list degrading into the anonymous skip it replaced. A bare
        extension with no reason is not a declaration, it is unfinished work."""
        unreasoned = [
            f"{name}:{ext}"
            for name, gaps in DECLARED_COVERAGE_GAPS.items()
            for ext, reason in gaps.items()
            if len(reason.strip()) < 40
        ]
        assert not unreasoned, "These declared gaps have no usable reason:\n  " + "\n  ".join(
            unreasoned
        )

    def test_the_disclosure_names_what_went_unchecked(self):
        """The point of the declaration: evidence can state the gap. `declared_imports`
        covers the four JS/TS extensions only, so a reader asking what it did not check
        gets `.py` and why — rather than a green that implies full coverage. And the
        gap this mechanism was built for is closed: `undefined_names` reads every
        emission language since #939, so it declares nothing (the two-sided guard
        above would fail if it still did)."""
        gaps = uncovered_languages(CHECK_DECLARED_IMPORTS)
        assert sorted(gaps) == [".py"]
        assert all("requirements" in reason for reason in gaps.values())
        assert uncovered_languages(CHECK_UNDEFINED_NAMES) == {}
        assert uncovered_languages("nonexistent_check") == {}


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


class TestInjectionScopeIsDeclared:
    """#598: where a framework-injected ``file`` check is applied is the spec's own
    declaration. The first cut inferred "recipe" from an empty ``applicable_extensions``,
    which would have turned any file-scoped check that declared none into a recipe check
    silently — and a file-scoped injection that read the #1216 predicate dropped every
    check without extensions from emission."""

    def test_the_two_scopes_partition_the_injected_file_checks(self):
        from squadops.cycles.acceptance_check_spec import (
            CHECK_ADDITIVE_CONTAINMENT,
            CHECK_CONTAINER_PACKAGING,
            CHECK_SPECS,
            CHECK_UNDEFINED_NAMES,
            INJECTION_SCOPE_FILE,
            INJECTION_SCOPE_RECIPE,
            INJECTION_SCOPE_SUITE,
            framework_injected_checks,
        )

        file_scoped = framework_injected_checks(INJECTION_SCOPE_FILE)
        recipe_scoped = framework_injected_checks(INJECTION_SCOPE_RECIPE)
        suite_scoped = framework_injected_checks(INJECTION_SCOPE_SUITE)
        assert CHECK_UNDEFINED_NAMES in file_scoped
        assert recipe_scoped == (CHECK_CONTAINER_PACKAGING,)
        assert suite_scoped == (CHECK_ADDITIVE_CONTAINMENT,)
        scoped = [set(file_scoped), set(recipe_scoped), set(suite_scoped)]
        assert sum(len(x) for x in scoped) == len(set().union(*scoped))
        every_injected_file_check = {
            name
            for name, spec in CHECK_SPECS.items()
            if spec.framework_injected and spec.required_params == frozenset({"file"})
        }
        assert set().union(*scoped) == every_injected_file_check
        assert framework_injected_checks("not-a-scope") == ()

    def test_the_seam_applies_each_scope_to_its_own_artifacts(self):
        from squadops.cycles.acceptance_check_spec import (
            CHECK_ADDITIVE_CONTAINMENT,
            CHECK_CONTAINER_PACKAGING,
            CHECK_UNDEFINED_NAMES,
        )

        """#1022: a suite-scoped check lands on the suite file only — never on the source
        beside it, whose extension it also parses — and carries the scaffold stack as its
        own param; the recipe check lands on the Dockerfile; the file checks on both
        parseable files. A .py suite gets no JS containment row."""
        from squadops.capabilities.handlers.cycle.base import _framework_injected_criteria

        artifacts = [
            {"name": "app/page.tsx", "content": ""},
            {"name": "__tests__/runs.test.ts", "content": ""},
            {"name": "backend/tests/test_runs.py", "content": ""},
            {"name": "Dockerfile", "content": ""},
        ]
        rows = _framework_injected_criteria(artifacts, (), scaffold_stack="nextjs_ts")
        by_check: dict[str, list[dict]] = {}
        for row in rows:
            by_check.setdefault(row.check, []).append(row.params)
        assert by_check[CHECK_ADDITIVE_CONTAINMENT] == [
            {"file": "__tests__/runs.test.ts", "stack": "nextjs_ts"}
        ]
        assert by_check[CHECK_CONTAINER_PACKAGING] == [{"file": "Dockerfile"}]
        assert {p["file"] for p in by_check[CHECK_UNDEFINED_NAMES]} == {
            "app/page.tsx",
            "__tests__/runs.test.ts",
            "backend/tests/test_runs.py",
        }
        # An unknown scaffold stack injects the check without a stack param: the
        # evaluator then skips as unknown_stack rather than judging by a guess.
        bare = _framework_injected_criteria(artifacts[1:2], (), scaffold_stack="")
        assert [r.params for r in bare if r.check == CHECK_ADDITIVE_CONTAINMENT] == [
            {"file": "__tests__/runs.test.ts"}
        ]

    def test_an_unknown_scope_is_rejected_at_declaration(self):
        import dataclasses

        import pytest

        from squadops.cycles.acceptance_check_spec import CHECK_SPECS, CHECK_UNDEFINED_NAMES

        with pytest.raises(ValueError, match="injection_scope"):
            dataclasses.replace(CHECK_SPECS[CHECK_UNDEFINED_NAMES], injection_scope="suite-ish")

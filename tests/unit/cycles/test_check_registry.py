"""Canonical framework-check registry (SIP-0096 §6.3).

The registry is the single source of truth for which check-ids a profile may
mark ``required_checks``. Its whole reason to exist is to make an unknown id
(a typo) detectable instead of silently inert, so these tests pin exactly that
boundary plus the tooling axis the later preflight/doctor parity reads.
"""

from __future__ import annotations

import pytest

from squadops.cycles.check_registry import (
    CHECK_FRONTEND_BUILD,
    CHECK_NO_SELF_MOCKING_TESTS,
    CHECK_NO_STUB_FALLBACK_TESTS,
    CHECK_REQUIRED_FILES,
    CHECK_TESTS_PASS,
    TOOL_NODE,
    framework_check_ids,
    get_framework_check,
    is_framework_check,
)

pytestmark = [pytest.mark.domain_orchestration]

_ALL_IDS = {
    CHECK_TESTS_PASS,
    CHECK_NO_STUB_FALLBACK_TESTS,
    CHECK_NO_SELF_MOCKING_TESTS,
    CHECK_REQUIRED_FILES,
    CHECK_FRONTEND_BUILD,
}


def test_registry_holds_exactly_the_framework_checks():
    """The vocabulary is closed. If a per-cycle id (e.g. ``acceptance:*``) or a
    pulse suite_id ever leaks in here it would become falsely required-addressable
    — §6.3 keeps those OUT of the fixed framework set."""
    assert framework_check_ids() == frozenset(_ALL_IDS)


def test_known_ids_are_recognized():
    assert all(is_framework_check(cid) for cid in _ALL_IDS)


@pytest.mark.parametrize("typo", ["test_pass", "tests_passed", "no_stub", "acceptance:foo", ""])
def test_unknown_or_typoed_id_is_not_a_framework_check(typo):
    """The exact bug the registry exists for: a mistyped required id must be
    detectable (False), not silently accepted then matched to nothing at run end."""
    assert is_framework_check(typo) is False
    assert get_framework_check(typo) is None


def test_get_framework_check_returns_the_registered_entry():
    check = get_framework_check(CHECK_FRONTEND_BUILD)
    assert check is not None
    assert check.check_id == CHECK_FRONTEND_BUILD


def test_only_tooling_backed_checks_can_be_knowably_absent():
    """The frontend build needs Node (provisioned in the qa image, #306) — it is
    the one check the coming preflight/doctor parity can flag as knowably absent.
    The test-spine/pure checks declare no external tooling, so they can never be
    'missing tooling'. Dropping Node here would silently disarm that guard."""
    assert get_framework_check(CHECK_FRONTEND_BUILD).required_tooling == (TOOL_NODE,)
    for cid in (CHECK_TESTS_PASS, CHECK_NO_STUB_FALLBACK_TESTS, CHECK_REQUIRED_FILES):
        assert get_framework_check(cid).required_tooling == ()


class TestChecksARunCanSubject:
    """#1428: a run owes only the required checks its PLANNED task types can produce a
    subject for. The bug each case catches is named in its id."""

    FRAMING = (
        "development.author_manifest",
        "qa.define_test_strategy",
        "governance.prepare_plan_authoring_brief",
        "governance.merge_plan",
        "governance.review_plan",
    )

    @pytest.mark.parametrize(
        ("task_types", "expected"),
        [
            pytest.param(FRAMING, frozenset(), id="framing-run-owes-nothing"),
            pytest.param(
                ("development.develop",),
                frozenset({"frontend_build"}),
                id="source-author-subjects-the-frontend-build",
            ),
            pytest.param(
                ("qa.test",),
                frozenset({"tests_pass", "no_stub_fallback_tests", "no_self_mocking_tests"}),
                id="suite-author-subjects-the-test-spine",
            ),
            pytest.param(
                ("builder.assemble",),
                frozenset({"required_files"}),
                id="builder-subjects-required-files",
            ),
            pytest.param(
                ("development.develop", "qa.test", "builder.assemble"),
                frozenset(
                    {
                        "frontend_build",
                        "tests_pass",
                        "no_stub_fallback_tests",
                        "no_self_mocking_tests",
                        "required_files",
                    }
                ),
                id="implementation-run-subjects-all-five",
            ),
            pytest.param(("not.a.task_type",), frozenset(), id="unknown-type-subjects-nothing"),
            pytest.param((), frozenset(), id="empty-plan-subjects-nothing"),
        ],
    )
    def test_the_subject_set_follows_the_planned_task_types(self, task_types, expected):
        from squadops.cycles.check_registry import checks_a_run_can_subject

        assert checks_a_run_can_subject(task_types) == expected

    def test_every_registered_check_has_exactly_one_subject_provider(self):
        """Bug caught: a new framework check registered without a subject provider —
        it would be owed by no run and vanish from every required set silently, the
        #291 shape (declared, enforced nowhere) one table over."""
        from squadops.cycles.check_registry import (
            _CHECK_SUBJECT_PROVIDER,
            framework_check_ids,
        )

        providers = [check for check, _ in _CHECK_SUBJECT_PROVIDER]
        assert set(providers) == set(framework_check_ids())
        assert len(providers) == len(set(providers))


class TestTheOwedRowsAreComposedFromTheContract:
    """#1374: the composition half of ``framework_rows_owed``, moved here beside the
    owed/producer half by #1152 step 2.

    Two void counted rolls on two lines were one mechanism patched twice: the
    accepted-patch seam composed a corrected result from the failed attempt's rows plus
    whatever the verifier produced, so a framework row survived only if some earlier
    stage happened to write one. What a task owes is its contract's statement; its
    attempt's history is not evidence about it.
    """

    def _compose(self, task_type, **kw):
        from squadops.cycles.check_registry import compose_owed_framework_rows

        return compose_owed_framework_rows(
            task_type,
            produced=kw.get("produced", set()),
            expected_artifacts=kw.get("expected_artifacts", []),
            patched_names=kw.get("patched_names", []),
        )

    def test_a_contentless_attempt_still_owes_its_required_files_row(self):
        """Bug caught: #1364's shape — a builder attempt that emitted nothing carries no
        rows at all, so a rule keyed on "only when the attempt carried one" (#1318) leaves
        the required check with no executed row anywhere. The accepted patch supplied the
        files, the app booted, and the roll-up read ``subject_missing`` →
        ``blocked_unverified`` (1.7.3 roll 1).
        """
        from squadops.cycles.check_registry import OWED_DERIVED
        from squadops.tasks.task_types import TaskType

        owed = self._compose(
            TaskType.BUILDER_ASSEMBLE,
            produced=set(),
            expected_artifacts=["docker/Dockerfile", "docker/compose.yaml"],
            patched_names=["Dockerfile", "compose.yaml"],
        )

        assert [(o.check_id, o.disposition) for o in owed] == [(CHECK_REQUIRED_FILES, OWED_DERIVED)]
        assert owed[0].row == {
            "check": CHECK_REQUIRED_FILES,
            "passed": True,
            "missing": [],
            "required": ["Dockerfile", "compose.yaml"],
        }

    def test_the_row_is_derived_from_the_patched_set_and_fails_on_a_real_miss(self):
        """The derivation must be able to say no. A rule that only ever produced a
        passing row would credit every accepted patch with deliverables it never wrote —
        worse than the gap it replaces, because it reads as evidence."""
        from squadops.tasks.task_types import TaskType

        owed = self._compose(
            TaskType.BUILDER_ASSEMBLE,
            expected_artifacts=["Dockerfile", "compose.yaml"],
            patched_names=["Dockerfile"],
        )

        assert owed[0].row["passed"] is False
        assert owed[0].row["missing"] == ["compose.yaml"]
        assert owed[0].row["required"] == ["Dockerfile", "compose.yaml"]

    def test_nothing_declared_is_undeclared_not_a_passing_row(self):
        """Bug caught: an empty required set read as "all present".

        There is no set to check the patched tree against, so inventing a passing row
        would credit a deliverable nobody named. The pre-patch state decides and the
        disposition says so (#1318), rather than the seam manufacturing a green.
        """
        from squadops.cycles.check_registry import OWED_UNDECLARED
        from squadops.tasks.task_types import TaskType

        owed = self._compose(TaskType.BUILDER_ASSEMBLE, expected_artifacts=[])

        assert [(o.check_id, o.disposition, o.row) for o in owed] == [
            (CHECK_REQUIRED_FILES, OWED_UNDECLARED, None)
        ]

    def test_tests_pass_is_satisfied_by_the_evidence_the_rollup_reads(self):
        """Bug caught: every retested qa patch refused.

        ``tests_pass`` is the one owed row that is never a check ROW on a passing result —
        ``verification_normalize`` skips the failure-only row and synthesises the check
        from the richer ``test_result``. A caller keyed on the row alone sees it missing
        on exactly the green runs, so the caller adds it to ``produced``, and this asserts
        the composition honours that rather than re-deriving it.
        """
        from squadops.cycles.check_registry import OWED_NOT_DERIVABLE, OWED_PRODUCED
        from squadops.tasks.task_types import TaskType

        owed = self._compose(TaskType.QA_TEST, produced={CHECK_TESTS_PASS})

        by_id = {o.check_id: o.disposition for o in owed}
        assert by_id[CHECK_TESTS_PASS] == OWED_PRODUCED
        # The other two the qa suite owes have no derivation at this seam — reported so a
        # record can count them, never refused (the promotion is a deliberate separate
        # call with evidence behind it).
        assert by_id[CHECK_NO_STUB_FALLBACK_TESTS] == OWED_NOT_DERIVABLE
        assert by_id[CHECK_NO_SELF_MOCKING_TESTS] == OWED_NOT_DERIVABLE

    def test_a_task_type_owing_nothing_composes_nothing(self):
        """A framing task emits no source, no suite and no required files. Owing it a row
        would manufacture a gap on every framing run — the #1428 shape, one table over."""
        from squadops.tasks.task_types import TaskType

        assert self._compose(TaskType.GOVERNANCE_REVIEW_PLAN) == []

    def test_every_owed_row_names_the_stage_that_should_have_produced_it(self):
        """The log line and the record both read ``producer``; an empty one turns "owed
        and absent" into a fact nobody can act on."""
        from squadops.tasks.task_types import TaskType

        for task_type in (TaskType.BUILDER_ASSEMBLE, TaskType.QA_TEST):
            for owed in self._compose(task_type):
                assert owed.producer and owed.producer != "unknown"

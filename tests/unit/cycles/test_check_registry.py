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

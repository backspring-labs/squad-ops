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

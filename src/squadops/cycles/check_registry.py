"""Canonical registry of framework verification checks (SIP-0096 §6.3).

The set of checks a cycle-request profile may name in ``required_checks``. §6.3:
requiredness is resolved **only** from explicit profile declarations against
*stable framework identities* — never inferred from names, types, or history.

Before this module those identities were scattered — constants in
``verification_normalize``, raw strings in the qa handler, ``required_files``
only in ``build_completeness``, and the frontend build check had no id at all —
and ``_validate_required_checks`` accepted *any* string. So a profile declaring
``required_checks: [test_pass]`` (a typo) validated fine and then silently
matched nothing at aggregation, reverting the profile to inert: the
"looks-enforced-but-isn't" failure this SIP exists to kill. This module is the
single source of truth those surfaces validate against.

Out of scope by design (§6.3):
- **Plan-authored typed checks** (SIP-0092, ``acceptance:<name>``) have per-cycle
  identity and are disclosed but **not** required-addressable — not registered here.
- **Pulse suites** are addressable by ``suite_id``, which is profile-defined and
  validated against the profile's own pulse config — a separate axis, not this
  fixed framework vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# External tooling identifiers a deployment must provision for a check to
# execute. This is the cross-process axis the later SIP-0095 preflight parity
# and doctor verification category consume: the frontend build runs in the qa
# agent image (Node via #306), not in runtime-api where preflight runs, so
# availability can't be probed locally — it is declared here and resolved per
# deployment.
TOOL_NODE = "node"


@dataclass(frozen=True)
class FrameworkCheck:
    """A stable, ``required_checks``-addressable framework check (§6.3)."""

    check_id: str
    description: str
    # Tooling the deployment must provision for this check to execute. Empty ⇒
    # runs on the framework's always-present runtime (pytest, pure-Python diffs),
    # so it can never be "knowably absent".
    required_tooling: tuple[str, ...] = ()


# Stable framework check-ids. Existing strings are REUSED verbatim (this
# centralizes them; it does not coin new names — taxonomy naming coordinates
# with #316). ``frontend_build`` is net-new so the fullstack frontend check is
# declarable; wiring its CheckResult emission is a later slice (4b).
CHECK_TESTS_PASS = "tests_pass"
CHECK_NO_STUB_FALLBACK_TESTS = "no_stub_fallback_tests"
CHECK_NO_SELF_MOCKING_TESTS = "no_self_mocking_tests"
CHECK_REQUIRED_FILES = "required_files"
CHECK_FRONTEND_BUILD = "frontend_build"


def required_files_row(required: Iterable[str], emitted: Iterable[str]) -> dict[str, Any]:
    """The framework's ``required_files`` evidence row — one rule, both seams that emit it.

    The builder handler emits it from its own emission (#399). The accepted-patch path
    must re-emit it from the **patched** set, or the failed attempt's row is the only one
    bearing the ``(required_files, task)`` identity the ledger supersedes on, and the run
    is rejected for a deliverable the accepted patch supplied — #1318, seen on 1.7.2
    FastAPI+React roll 1 (`cyc_e33939eda950`), where the patch wrote ``qa_handoff.md``,
    ``patch_verification`` passed, and the verdict was still ``rejected``.

    Basenames, matching the #107 rule the handler has always applied.
    """
    from pathlib import PurePosixPath

    have = {PurePosixPath(str(name)).name for name in emitted if name}
    required_names = [str(item) for item in required]
    missing = [item for item in required_names if item not in have]
    # `required` rides the row so the evidence says what was asked for, not only what was
    # absent. H1 (1.7.4) is "no counted roll is rejected on the handoff", and a readout
    # built from `missing` alone cannot tell that bar from its own blind spot: a NEW
    # required file the profile derives fails identically under a different name, and a
    # record listing only misses would read as the bar holding.
    return {
        "check": CHECK_REQUIRED_FILES,
        "passed": not missing,
        "missing": missing,
        "required": required_names,
    }


FRAMEWORK_CHECKS: dict[str, FrameworkCheck] = {
    CHECK_TESTS_PASS: FrameworkCheck(
        CHECK_TESTS_PASS,
        "Generated test suite executed and passed (framework test spine).",
    ),
    CHECK_NO_STUB_FALLBACK_TESTS: FrameworkCheck(
        CHECK_NO_STUB_FALLBACK_TESTS,
        "The passing tests are not stub/placeholder fallbacks (§6.6.1).",
    ),
    CHECK_NO_SELF_MOCKING_TESTS: FrameworkCheck(
        CHECK_NO_SELF_MOCKING_TESTS,
        "The passing tests invoke the application rather than their own mock (#915).",
    ),
    CHECK_REQUIRED_FILES: FrameworkCheck(
        CHECK_REQUIRED_FILES,
        "The build profile's required_files were all emitted (#291).",
    ),
    CHECK_FRONTEND_BUILD: FrameworkCheck(
        CHECK_FRONTEND_BUILD,
        "The fullstack frontend build/test executed (SIP-0070 D13).",
        required_tooling=(TOOL_NODE,),
    ),
}


#: Which framework spine rows a task type owes BY CONTRACT, and which stage's rule
#: produces each. #1374: the accepted-patch path composed a corrected result from the
#: failed attempt's rows plus whatever the verifier produced, so a framework row was
#: present only if some earlier stage happened to write one — and each miss was patched
#: with a narrower gate. #1318 (1.7.2 roll 1) re-derived `required_files` only when the
#: failed attempt had CARRIED it; #1364 (1.7.3 roll 1) found the next shape, a contentless
#: attempt that carried no rows at all, and both void counted rolls were booting apps.
#:
#: A table, so the next shape is a row here rather than a third gate: what a task owes is
#: its contract's statement, never its attempt's history.
#:
#: `frontend_build` is deliberately absent. It is stack-conditional — the criteria pack
#: emits `vc-frontend-builds` only where a frontend exists — so declaring it owed would
#: manufacture a gap on every backend-only cycle, which is the same false-negative class
#: in the other direction.
_FRAMEWORK_ROWS_OWED: tuple[tuple[str, str, str], ...] = (
    (CHECK_REQUIRED_FILES, "emits_required_files", "derived from the patched set"),
    (CHECK_TESTS_PASS, "authors_qa_suite", "the retest"),
    (CHECK_NO_STUB_FALLBACK_TESTS, "authors_qa_suite", "the retest"),
    (CHECK_NO_SELF_MOCKING_TESTS, "authors_qa_suite", "the retest"),
)


def framework_rows_owed(task_type: object) -> tuple[str, ...]:
    """The framework spine rows this task type owes, by contract (#1374).

    Read at the accepted-patch seam: every owed row must be present in the corrected
    result — derived there when the rule can derive it, taken from the retest when the
    retest is the producing stage — or the patch is not accepted. "Absent" is the state
    SIP-0096 reads as `subject_missing`, and it blocked two counted rolls whose apps
    booted.
    """
    from squadops.tasks import task_types as _tt

    return tuple(
        check
        for check, predicate, _stage in _FRAMEWORK_ROWS_OWED
        if getattr(_tt, predicate)(task_type)
    )


def framework_row_producer(check_id: str) -> str:
    """Which stage's rule writes ``check_id`` — for the log line and the seam table."""
    for check, _predicate, stage in _FRAMEWORK_ROWS_OWED:
        if check == check_id:
            return stage
    return "unknown"


def is_framework_check(check_id: str) -> bool:
    """True iff ``check_id`` is a stable, required-addressable framework check."""
    return check_id in FRAMEWORK_CHECKS


def get_framework_check(check_id: str) -> FrameworkCheck | None:
    """Return the registered check, or ``None`` if unregistered."""
    return FRAMEWORK_CHECKS.get(check_id)


def framework_check_ids() -> frozenset[str]:
    """The set of valid ``required_checks`` ids (for load-time validation)."""
    return frozenset(FRAMEWORK_CHECKS)

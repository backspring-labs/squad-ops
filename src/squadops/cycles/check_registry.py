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

from dataclasses import dataclass

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
CHECK_REQUIRED_FILES = "required_files"
CHECK_FRONTEND_BUILD = "frontend_build"

FRAMEWORK_CHECKS: dict[str, FrameworkCheck] = {
    CHECK_TESTS_PASS: FrameworkCheck(
        CHECK_TESTS_PASS,
        "Generated test suite executed and passed (framework test spine).",
    ),
    CHECK_NO_STUB_FALLBACK_TESTS: FrameworkCheck(
        CHECK_NO_STUB_FALLBACK_TESTS,
        "The passing tests are not stub/placeholder fallbacks (§6.6.1).",
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


def is_framework_check(check_id: str) -> bool:
    """True iff ``check_id`` is a stable, required-addressable framework check."""
    return check_id in FRAMEWORK_CHECKS


def get_framework_check(check_id: str) -> FrameworkCheck | None:
    """Return the registered check, or ``None`` if unregistered."""
    return FRAMEWORK_CHECKS.get(check_id)


def framework_check_ids() -> frozenset[str]:
    """The set of valid ``required_checks`` ids (for load-time validation)."""
    return frozenset(FRAMEWORK_CHECKS)

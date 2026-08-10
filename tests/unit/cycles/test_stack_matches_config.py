"""The manifest must be for the stack the cycle is building (#838).

Found by VS (#822 Stage 1e), `cyc_afa934886acd`: configured `build_profile=nextjs_ts`, the
authored manifest declared `fullstack_fastapi_react`, and **every component behaved correctly
while building the wrong application for 75 minutes**. `lint()` accepts any *registered*
stack — is it known, never is it the one asked for — so nothing downstream had a reason to
object, and the rejection that eventually fired was incidental (a frozen-file claim) rather
than the real problem.

The author *is* told the target, but it lost to a technical design that named the other stack
eight times, produced by a stage that is never told the stack at all. That plumbing is a
separate fix in the same chain. This proof is the deterministic backstop that holds regardless
of what any model writes.

Bug classes guarded:

- **a manifest for another stack passing every gate**, which is the defect;
- **the check firing where there is no cycle config to compare against** — seeded cycles and
  the gate's own adversarial fixtures — which would reject correct manifests and is the #762
  lesson that a net false-positiving on a working configuration is worse than the gap it
  closes;
- **accumulating findings across a stack mismatch.** The other proofs run happily against the
  wrong application, so an author would be told to fix a testid in a design about to be
  replaced wholesale;
- a rejection that names the problem without naming either value or the fix;
- **the proof escaping M6's taxonomy**, which would put a rejection in the baseline with no
  class — data lost at exactly the moment B1 is collecting it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.cycles.authoring_failure import AUTHORING_DEFECT, assess_authoring_outcome
from squadops.cycles.manifest_gates import (
    PROOF_STACK_MATCHES_CONFIG,
    PROOF_TESTID_COVERAGE,
    assess_winnability,
)

pytestmark = [pytest.mark.domain_contracts]

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str = "fullstack_fastapi_react") -> str:
    return _REFERENCE.replace("fullstack_fastapi_react", stack)


# --------------------------------------------------------------------------- #
# The defect
# --------------------------------------------------------------------------- #


def test_the_vs_case_is_rejected():
    """`cyc_afa934886acd` exactly: a FastAPI manifest on a Next.js cycle."""
    findings = assess_winnability(_manifest("fullstack_fastapi_react"), "nextjs_ts")

    assert [f.proof for f in findings] == [PROOF_STACK_MATCHES_CONFIG]


def test_the_rejection_names_both_stacks_and_the_fix():
    """A rejection reading only "stack mismatch" sends the author to guess which of two
    values is wrong — and the author cannot see the cycle's config at all."""
    detail = assess_winnability(_manifest(), "nextjs_ts")[0].detail

    assert "fullstack_fastapi_react" in detail
    assert "nextjs_ts" in detail
    assert "stack: nextjs_ts" in detail, "the corrective action must be literal"


@pytest.mark.parametrize("stack", ["fullstack_fastapi_react", "nextjs_ts"])
def test_a_matching_stack_raises_no_stack_finding(stack):
    """The check must be silent on every correct cycle, on both real stacks."""
    findings = assess_winnability(_manifest(stack), stack)

    assert PROOF_STACK_MATCHES_CONFIG not in [f.proof for f in findings]


# --------------------------------------------------------------------------- #
# It must not fire where there is nothing to compare
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("expected", ["", None])
def test_no_configured_stack_means_no_comparison(expected):
    """Seeded cycles and the gate's own adversarial fixtures have no cycle config. Inventing
    a mismatch for them would reject manifests that are correct (#762's lesson)."""
    findings = assess_winnability(_manifest(), expected or "")

    assert PROOF_STACK_MATCHES_CONFIG not in [f.proof for f in findings]


def test_the_reference_manifest_still_passes_every_gate_unconfigured():
    """The pair the release's evidence is bound to must be unaffected."""
    assert assess_winnability(_REFERENCE) == ()


# --------------------------------------------------------------------------- #
# It returns alone
# --------------------------------------------------------------------------- #


def test_a_stack_mismatch_suppresses_the_other_findings():
    """The other proofs run happily against the wrong application. Reporting them would tell
    an author to fix a testid in a design that is about to be replaced wholesale — the same
    reason a parse failure returns alone."""
    broken = _manifest("nextjs_ts").replace("testids:", "removed_testids:")

    # the mutation alone is a real testid failure...
    assert PROOF_TESTID_COVERAGE in [f.proof for f in assess_winnability(broken, "nextjs_ts")]
    # ...but a wrong stack hides it, deliberately
    findings = assess_winnability(broken, "fullstack_fastapi_react")
    assert [f.proof for f in findings] == [PROOF_STACK_MATCHES_CONFIG]


def test_an_unparseable_manifest_still_reports_the_parse_failure_first():
    """Adding a proof ahead of lint must not displace the parse exception — a document that
    did not parse has no `stack` to compare."""
    findings = assess_winnability("not: [valid", "nextjs_ts")

    assert [f.proof for f in findings] == ["parses"]


# --------------------------------------------------------------------------- #
# M6 classifies it
# --------------------------------------------------------------------------- #


def test_the_rejection_is_classified_rather_than_uncounted():
    """A rejection with no class is data lost at the moment B1 is collecting it — and the
    taxonomy's drift guard requires every `PROOF_*` to have one."""
    outcome = assess_authoring_outcome(_manifest(), "nextjs_ts")

    assert outcome.rejected
    classes = {f.failure_class for f in outcome.findings}
    assert classes == {AUTHORING_DEFECT}


def test_the_outcome_assessor_defaults_to_no_comparison():
    """Its other callers — B1's replay over stored manifests, the gate's own tests — pass no
    cycle config and must keep working unchanged."""
    assert not assess_authoring_outcome(_REFERENCE).rejected

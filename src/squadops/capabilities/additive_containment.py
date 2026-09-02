"""Containment rules for author-written additive test suites — #1022, the gate.

SIP-0104 contains the qa author inside deterministic scaffold slots, and
``verification_scaffold_gate`` validates that surface with named findings. **Additive
suites — the extra files a qa author writes beyond the scaffold, and on a stack with no
scaffold every file the author writes — had no equivalent.** They are unconstrained
authorship landing in the same tree, and they are where arm A's V7 rolls died: every
counted red was additive-suite-side while all nine delivered applications of the arc
passed independent boot audits. The apps were fine; the tests were not.

Three rules, all reading the EMITTED BYTES rather than any declaration — the same posture
as the scaffold gate, and for the same reason: a defect is precisely a gap between what
the author meant and what it wrote. Two of them are the stack's own definition of
"invokes the application" (:class:`~squadops.capabilities.app_invocation.AppInvocation`,
#1126) applied at emission, which is where the self-mocking detector's rule was only
ever applied after the suite had already run.

- **Live-server fetch.** The suite runs in-process under vitest; there is no server
  listening. A suite that fetches an absolute URL can only hang or throw.
- **No application invocation.** A suite that imports nothing the stack counts as the
  application is testing nothing it did not itself define — C3's and C4's stored suites
  (``cyc_6495d9870587``, ``cyc_2913ae7abd67``) both reached the app only through its
  browser client, ``@/lib/api``, one with ``fetch`` stubbed (asserting on its own stub)
  and one without (a network call under vitest). Neither imported a route handler.
- **Subject mocked.** ``vi.mock`` of the module under test; there is no reading under
  which replacing the subject and asserting on the replacement verifies the subject.

**Enforced as the typed check** ``additive_containment`` (``cycles.acceptance_check_spec``),
framework-injected per emitted suite file with the scaffold stack as a self-contained
param, so it runs where every other emission-time check runs: the producing agent's
container, on the primary emission, on every self-eval re-emission, and on a repair's
patch (#1229, rule B). #1052 shipped these findings reporting-only, banked under
``additive_containment`` in the fill-merge evidence, so the gate's shape could be argued
from what it would have flagged across real rolls; the 1.7.1 plan (§2.3) promoted it on
that evidence, with the V7 slot-2/3 greens and the accepted 1.6.6 and 1.7.0 rolls'
suites as the over-rejection controls (``tests/fixtures/roll_replays``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from squadops.capabilities.app_invocation import AppInvocation

#: Rule identifiers — constants at the core; the strings are what the evidence carries.
RULE_LIVE_SERVER_FETCH = "live_server_fetch"
RULE_NO_APPLICATION_INVOCATION = "no_application_invocation"
RULE_SUBJECT_MOCKED = "subject_mocked"

#: An absolute http(s) URL passed to a network client. Deliberately not "any URL in the
#: file": a comment or a fixture string mentioning a URL is not an execution-model
#: violation, and over-matching prose is how a finding loses its meaning.
#:
#: Case-SENSITIVE, and `request` is not in the alternation — both learned from the
#: control test in the first draft. `new Request('http://test/api/runs')` is the CORRECT
#: in-process form the scaffold shells themselves emit, and an ignore-case `request`
#: alternative flags every legitimate suite. A check that fires on the right answer is
#: worse than no check.
_LIVE_FETCH_RE = re.compile(r"""\b(?:fetch|axios(?:\.\w+)?|got|superagent)\s*\(\s*[`'"]https?://""")

#: `supertest`-style listeners: the package exists only to bind a server.
_SERVER_HARNESS_RE = re.compile(r"""\bfrom\s+['"](supertest|node-fetch|undici)['"]""")


@dataclass(frozen=True)
class ContainmentFinding:
    """One rule one suite file broke, with the detail the author is handed back."""

    path: str
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}: {self.detail}"


def _live_server_detail(match: str) -> str:
    return (
        f"fetches a live server (`{match.strip()}…`). The suite runs in-process with "
        f"nothing listening, so the call can only hang or throw."
    )


def _no_invocation_detail(invocation: AppInvocation) -> str:
    what = invocation.invocation_description or "an import of the application"
    return (
        f"invokes nothing of the application — this stack counts {what}. A suite that "
        f"reaches the app only through its network client, or not at all, asserts against "
        f"its own stubs."
    )


def containment_findings(
    path: str, content: str, invocation: AppInvocation
) -> list[ContainmentFinding]:
    """The rules one suite file breaks, in rule order (empty = contained).

    Pure over the bytes and the stack's declaration; the typed-check evaluator and the
    fill-merge evidence both call this so the record and the verdict cannot disagree.
    """
    findings: list[ContainmentFinding] = []
    live = _LIVE_FETCH_RE.search(content) or _SERVER_HARNESS_RE.search(content)
    if live:
        findings.append(
            ContainmentFinding(path, RULE_LIVE_SERVER_FETCH, _live_server_detail(live.group(0)))
        )
    if invocation.mocks_subject(content):
        findings.append(
            ContainmentFinding(
                path,
                RULE_SUBJECT_MOCKED,
                "mocks the module under test and asserts on the mock; replacing the subject "
                "verifies nothing about it.",
            )
        )
    if not invocation.invokes(content):
        findings.append(
            ContainmentFinding(
                path, RULE_NO_APPLICATION_INVOCATION, _no_invocation_detail(invocation)
            )
        )
    return findings


def assess_additive_suite(
    files: list[dict], invocation: AppInvocation | None
) -> list[ContainmentFinding]:
    """Containment findings for every suite file in an emission (empty = clean).

    ``files`` is the emission's artifact shape (``{"name", "content"}``). Which files are
    suites is the stack's declaration (``invocation.is_suite``); with no declaration — an
    unregistered stack — nothing is judged, and the caller records that as not-inspected
    rather than as clean (#986). Sorted by path so two runs' findings compare.
    """
    if invocation is None:
        return []
    findings: list[ContainmentFinding] = []
    for f in sorted(files, key=lambda a: str(a.get("name", ""))):
        path = str(f.get("name") or "")
        content = f.get("content")
        if not path or not invocation.is_suite(path) or not isinstance(content, str):
            continue
        findings.extend(containment_findings(path, content, invocation))
    return findings

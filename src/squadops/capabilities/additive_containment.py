"""Containment findings for additive test suites — #1022, reporting-only.

SIP-0104 contains the qa author inside deterministic scaffold slots, and
``verification_scaffold_gate`` validates that surface with named findings. **Additive
suites — the extra files a qa author writes beyond the scaffold — have no equivalent.**
They are unconstrained authorship landing in the same tree, and they are where arm A's
V7 rolls died: every counted red was additive-suite-side while all nine delivered
applications of the arc passed independent boot audits. The apps were fine; the tests
were not.

Two checks, both reading the EMITTED BYTES rather than any declaration — the same
posture as the scaffold gate, and for the same reason: a defect is precisely a gap
between what the author meant and what it wrote.

- **Execution model.** The suite runs in-process under vitest; there is no server
  listening. A suite that fetches an absolute URL can only hang or throw.
  `cyc_6495d9870587` (corpus C3) did exactly this and burned three qa repairs without
  converging — *after* #877's prompt guidance shipped, which is the evidence that
  guidance alone does not contain this.
- **Subject import.** A test that imports no application module is testing nothing it
  did not itself define. It is the precondition for the self-mocking class: a file that
  stubs `global.fetch` and imports no route can only assert against its own stub.

**Reporting-only, deliberately, and this is the whole disposition of this module.**
Nothing here rejects. The findings are computed and banked so the shape of a real gate
can be argued from what it *would* have flagged across actual rolls, rather than from
what seems reasonable now — #1022 itself defers the gate's shape to design review, and
tonight's #1049 is a live demonstration of the cost of deploying a rejection whose
premise was never checked against real traffic. Promotion to a blocking gate is a
separate, deliberate call with the banked evidence in hand.
"""

from __future__ import annotations

import re

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

#: An import of application code — the alias form the stack's tsconfig defines, a
#: relative climb out of `__tests__/`, or the store/harness seam the shells use.
_SUBJECT_IMPORT_RE = re.compile(
    r"""(?:import|require)\s*(?:[^'"]*from\s*)?['"](@/[^'"]+|\.\.?/[^'"]+)['"]"""
)

#: Files this pass judges. A non-test file in the emission is somebody else's concern.
_TEST_SUFFIXES = (".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js")

#: Scaffold-owned shells are NOT additive: they are generated, gated, and their spine is
#: frozen. Judging them here would report the generator's own output as an authoring
#: defect.
_SCAFFOLD_MARKER = ".scaffold.test."


def is_additive_test(path: str) -> bool:
    """Whether *path* is an author-written test this pass judges."""
    return path.endswith(_TEST_SUFFIXES) and _SCAFFOLD_MARKER not in path


def assess_additive_suite(files: list[dict]) -> list[str]:
    """Containment findings for the additive files in an emission (empty = clean).

    ``files`` is the emission's artifact shape (``{"name", "content"}``). Pure, so the
    same function serves the banked evidence today and a gate later without either
    reimplementing the rule.
    """
    findings: list[str] = []
    for f in sorted(files, key=lambda a: str(a.get("name", ""))):
        path = str(f.get("name") or "")
        content = f.get("content")
        if not is_additive_test(path) or not isinstance(content, str):
            continue
        if _LIVE_FETCH_RE.search(content) or _SERVER_HARNESS_RE.search(content):
            findings.append(
                f"{path}: fetches a live server. The suite runs in-process under vitest "
                f"with nothing listening, so this can only hang or throw — call the route "
                f"handler directly, as the scaffold shells do (#877/C3)."
            )
        if not _SUBJECT_IMPORT_RE.search(content):
            findings.append(
                f"{path}: imports no application module. A test that imports nothing it "
                f"did not define asserts only against its own stubs — the precondition "
                f"for the self-mocking class (#915)."
            )
    return findings

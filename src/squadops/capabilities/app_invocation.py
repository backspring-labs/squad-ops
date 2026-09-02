"""How a suite on one stack reaches the application — the stack's fact (#1126).

A leaf module, like ``success_status``: the stack modules declare an
:class:`AppInvocation` and the qa-side detector applies it, and neither may import the
other's package to do so (``handlers/__init__`` pulls in the handler tree, and the
stack registry is imported by handlers).

The self-mocking rule is stack-neutral: *a suite that replaces the seam it would reach the
app through, and never invokes the app, verifies nothing.* What "invokes the app" looks
like is not. Under Next.js's in-process model (#877) it is an import of an ``app/api/``
route module; on a React SPA it is rendering a real component or ``App``, and a global
``fetch`` stub is the *correct* way to isolate the network under it. The first definition
was written into the shared detector as if it were universal, and on 2026-08-27 it failed
a green FastAPI+React suite that rendered the real ``App`` with ``fetch`` stubbed — while
passing the suite that ``vi.mock``ed the app's own API module. Each stack now declares its
own three patterns on its ``ScaffoldStack``; the detector only applies them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Replacing the network seam — the stack-neutral half. Stubbing ``fetch`` is the same act
#: in every JS stack; what it MEANS is the stack's declaration below.
NETWORK_SEAM_FETCH_STUB = r"""(?x)
      global(?:This)?\s*\.\s*fetch\s*=                          # global.fetch = ...
    | (?:vi|jest)\s*\.\s*stubGlobal\s*\(\s*['"`]fetch['"`]      # vi.stubGlobal('fetch', ...)
    | (?:vi|jest)\s*\.\s*spyOn\s*\(\s*global(?:This)?\s*,\s*['"`]fetch['"`]
"""

#: The test-file suffixes a vitest harness collects — vitest's default include
#: (``**/*.{test,spec}.[jt]s?(x)``). These are the files the invocation rule judges and
#: the files the runner reports as uncollected. Both stacks run vitest, so both declare
#: this set; a stack whose harness collects a different shape declares its own on its
#: ``AppInvocation``. Until #1131 this list lived in the shared detector as a JS-only
#: vocabulary no stack had declared, and the runner kept a narrower copy (``.ts`` only)
#: that could not name an uncollected ``.test.jsx`` on the React stack.
JS_SUITE_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
)


@dataclass(frozen=True)
class AppInvocation:
    """The three patterns one stack needs to judge a self-mocking suite.

    All three are regex *sources*, applied with ``re.MULTILINE`` so an import can be
    required as a statement (``^\\s*import …``) rather than as any occurrence of a path —
    a ``vi.mock('…/app/api/…')`` string must never satisfy the invocation test.
    """

    #: A real import of the application — the evidence that the suite invokes it.
    invocation_import: str
    #: A mock of the subject itself. Unconditional: there is no reading under which
    #: replacing the module under test and asserting on it verifies that module.
    subject_mock: str
    #: Replacing the seam the suite would otherwise reach the app through. Flagged only
    #: when nothing invokes the app — mocking is not the defect, mocking INSTEAD of
    #: invoking is.
    network_seam_mock: str = NETWORK_SEAM_FETCH_STUB
    #: The test files this rule judges, by basename suffix — the harness's collection
    #: vocabulary. A file outside it (a helper beside the suites) is never a suite.
    suite_suffixes: tuple[str, ...] = JS_SUITE_SUFFIXES
    #: What ``invocation_import`` means, in words, for the finding a rejected suite is
    #: handed back with (#1022): the author is told what this stack counts as invoking
    #: the application, not shown a regex. Empty renders nothing.
    invocation_description: str = ""

    def is_suite(self, path: str) -> bool:
        """True for a test file this stack's harness collects (by its basename suffix)."""
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        return name.endswith(self.suite_suffixes)

    def invokes(self, content: str) -> bool:
        return re.search(self.invocation_import, content, re.MULTILINE) is not None

    def mocks_subject(self, content: str) -> bool:
        return re.search(self.subject_mock, content, re.MULTILINE) is not None

    def mocks_network(self, content: str) -> bool:
        return re.search(self.network_seam_mock, content, re.MULTILINE) is not None

"""Tests for the shared closing-reference parser (#1135).

What bug would these catch? A release package that credits a PR with closing
issues it merely quoted — permanently, since the package is a committed snapshot
the site never re-derives. The v1.6.5 capture claimed PR #1114 closed #1096,
#1106 and #999999: one already-closed issue, one PR number, and an issue that
does not exist, all four lifted out of that PR's own test log. It was corrected
by hand in #1134, which only worked because someone happened to read the preview.

The mirror bug is under-crediting: the package's old regex accepted three
present-tense verbs and mandatory whitespace, so `Closed #N` and `Fixes: #N` —
both of which GitHub honours and auto-closes on — were silently dropped from the
record while the issue really did close.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "closing_refs", REPO_ROOT / "scripts" / "dev" / "closing_refs.py"
)
closing_refs_mod = importlib.util.module_from_spec(_spec)
sys.modules["closing_refs"] = closing_refs_mod
_spec.loader.exec_module(closing_refs_mod)

closing_refs = closing_refs_mod.closing_refs
quoted_refs = closing_refs_mod.quoted_refs

pytestmark = [pytest.mark.domain_contracts]

#: PR #1114's shape: a guard's own test log, quoted three ways, plus one real closure.
PR_1114_SHAPE = """\
The guard rejects these, and its test log is the evidence:

`Closes #1096` → FAIL (already closed); `Closes #1106` → FAIL (is a PR)

```
Fixes #999999 → FAIL (no such issue)
```

<!-- template note: put Closes #4242 below -->

Closes #1113
"""


class TestQuotedTextIsNotAClosure:
    def test_the_v1_6_5_regression_credits_only_the_real_closure(self):
        """The exact capture that shipped wrong. The old regex over the raw body
        returned [1096, 1106, 1113, 999999]."""
        assert closing_refs(PR_1114_SHAPE) == [1113]

    def test_the_dropped_numbers_are_named_rather_than_silently_lost(self):
        """An empty Closes cell has two causes — nothing closed, or only quoted. The
        preview prints these so the difference is legible while it can still be acted on."""
        # 4242 is the template's own example, in the HTML comment — dropped for a
        # different reason than the other three, and reported the same way.
        assert quoted_refs(PR_1114_SHAPE) == [1096, 1106, 4242, 999999]

    def test_the_html_comment_the_pr_template_ships_is_not_a_closure(self):
        """`.github/PULL_REQUEST_TEMPLATE.md` puts its instructions in an HTML comment.
        Crediting those would give every PR the template's example number."""
        assert closing_refs("<!-- Closes #4242 -->\n\nNo issue: chore.") == []

    def test_a_fence_containing_backticks_does_not_leak_its_contents(self):
        body = "```\nrun `x` then Closes #55\n```\n\nCloses #66\n"
        assert closing_refs(body) == [66]

    def test_a_single_stray_backtick_does_not_blank_the_rest_of_the_body(self):
        """Inline spans do not cross lines in Markdown. Matching greedily across the
        newline would swallow a real closing line that follows an unpaired backtick."""
        assert closing_refs("A stray ` tick\n\nCloses #77\n") == [77]


class TestEveryFormGitHubHonoursIsCredited:
    @pytest.mark.parametrize(
        "line,expected",
        [
            ("Closes #1", 1),
            ("closes #2", 2),
            ("Closed #3", 3),
            ("Close #4", 4),
            ("Fixes: #5", 5),
            ("fixed #6", 6),
            ("Resolves #7", 7),
            ("resolved   #8", 8),
        ],
        ids="closes closes-lower closed close fixes-colon fixed resolves resolved".split(),
    )
    def test_tense_and_colon_variants_are_all_closures(self, line, expected):
        """GitHub auto-closes on all of these. The package's old regex took only
        `closes|fixes|resolves` with mandatory whitespace, so the record under-credited
        real closures — a quieter wrong than over-crediting, and harder to notice."""
        assert closing_refs(f"Body text.\n\n{line}\n") == [expected]

    def test_a_bare_reference_is_not_a_closure(self):
        """`Refs #N` and a bare `#N` do not auto-close — crediting them would put
        issues in the record that are still open (#1113, the original defect)."""
        assert closing_refs("Refs #9 — remaining: the rest. See also #10.") == []

    def test_numbers_are_deduplicated_and_ordered(self):
        assert closing_refs("Closes #30\nFixes #12\nResolves #30\n") == [12, 30]


class TestDegenerateInput:
    @pytest.mark.parametrize("body", ["", None], ids=["empty", "none"])
    def test_an_absent_body_yields_no_references(self, body):
        """`gh pr view --json body` returns None for a PR with no description; the
        capture runs over every merged PR in a tag range and must not raise on one."""
        assert closing_refs(body) == []
        assert quoted_refs(body) == []

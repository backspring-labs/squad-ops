#!/usr/bin/env python3
"""What counts as a closing reference — one home for it (#1135).

GitHub auto-closes an issue when a merged PR's body says ``Closes #N`` (or fix/resolve,
any tense). Two places in this repo need to know that: the pre-merge guard
(``check_pr_closure.sh``) and the release-package capture
(``maintainer/build_release_package.py``). They each grew their own regex and the two
disagreed, in both directions:

* **Quoting.** The guard strips fenced blocks, inline code spans and HTML comments
  before matching — it learned that on its own first live run, which failed on a PR
  whose Evidence section quoted ``Closes #1096`` as a test case. The package script
  matched the raw body, so it credited quoted text as closure. The v1.6.5 capture
  rendered PR #1114's *Closes* cell as **#1096 #1106 #1113 #999999**: one real
  closure, one already-closed issue, one PR number, and an issue that does not exist —
  all four lifted out of that PR's own test log. Corrected by hand in #1134.
* **Keywords.** The guard accepted every tense and an optional colon
  (``Closed #N``, ``Fixes: #N``); the package script accepted only three present-tense
  forms with mandatory whitespace, so it *under*-credited real closures GitHub honours.

The package is committed as a snapshot the site never re-derives, so a wrong cell is
permanent unless caught at preview. That asymmetry — a guard that merely nags versus a
record that outlives the release — is why this is worth one shared module rather than
two regexes kept in step by review.

Used as a library from Python and over stdin from shell::

    closing_refs(body) -> [1096, 1113]
    cat body.md | closing_refs.py --refs     # one number per line
    cat body.md | closing_refs.py --strip    # the body with quoted regions removed
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: Fenced blocks, HTML comments, then inline spans — in that order, because a fence may
#: contain backticks that would otherwise be paired across its boundary. Non-greedy so
#: two fences in one body do not swallow the prose between them.
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
#: Inline code spans do not span lines in Markdown, so the newline exclusion is what
#: stops a single stray backtick from blanking the rest of the document.
_INLINE = re.compile(r"`[^`\n]*`")

#: Every form GitHub itself honours: the three verbs, each in three tenses, with an
#: optional colon and flexible spacing. Anything narrower silently under-credits a real
#: closure; anything wider credits prose.
_CLOSING = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)",
    re.IGNORECASE,
)


def strip_quoted(body: str) -> str:
    """The body with fenced blocks, HTML comments and inline code spans removed.

    Quoting the syntax is not using it: the PR template's own instructions live in an
    HTML comment, and PRs routinely quote ``Closes #N`` when describing this very rule.
    """
    return _INLINE.sub("", _HTML_COMMENT.sub("", _FENCE.sub("", body or "")))


def closing_refs(body: str) -> list[int]:
    """Issue numbers this body actually closes, ascending and de-duplicated."""
    return sorted({int(n) for n in _CLOSING.findall(strip_quoted(body))})


def quoted_refs(body: str) -> list[int]:
    """Numbers that look like closures but sit in quoted regions, so are NOT credited.

    Reported at preview time so an empty *Closes* cell is legible as "quoted, not
    claimed" rather than as a parser that lost something.
    """
    everywhere = {int(n) for n in _CLOSING.findall(body or "")}
    return sorted(everywhere - set(closing_refs(body)))


def raw_closing_refs(text: str) -> list[int]:
    """Closing references in text GitHub reads unrendered: a commit message or a PR title.

    Nothing is stripped. Markdown quoting protects a body, which is rendered; a commit message
    and the title become the squash merge commit's text, and GitHub closes on that.
    """
    return sorted({int(n) for n in _CLOSING.findall(text or "")})


def merge_contradictions(body: str, title: str, commits: str) -> list[str]:
    """Why a squash merge of this PR would close an issue its body does not close.

    GitHub's squash merge makes the title the commit's subject and the PR's commit messages its
    body, and a closing keyword in either closes the issue whatever the PR body says. #1620's
    body said ``Refs #1619 — remaining: …`` and passed the guard; a ``Closes #1619`` trailer
    left in a revision commit closed #1619 on merge (#1621). A closed issue stops being read,
    so an issue closed too early is the more dangerous direction.

    The title may never carry a closing keyword, however negated ("does not close #N" closes
    #N): a title has no room for ``remaining:`` (1.8.2 plan §3.8). A commit may close only
    what the body closes; a commit that agrees with the body is fine.
    """
    problems = [
        f"the PR title closes #{n}: the squash merge's subject is the title, so #{n} closes "
        "whatever the body says; take the number out of the title (1.8.2 plan §3.8)"
        for n in raw_closing_refs(title)
    ]
    body_closes = set(closing_refs(body))
    problems += [
        f"a commit message closes #{n} but the PR body does not: the squash merge carries the "
        f"commit messages and closes #{n} anyway (#1621); reword the commit, or close #{n} in "
        "the body"
        for n in raw_closing_refs(commits)
        if n not in body_closes
    ]
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--refs", action="store_true", help="print closing numbers, one per line")
    mode.add_argument("--strip", action="store_true", help="print the body without quoted regions")
    mode.add_argument(
        "--contradictions",
        action="store_true",
        help="print what a squash merge would close that the body does not, one per line",
    )
    ap.add_argument("--title", default="", help="with --contradictions: the PR title")
    ap.add_argument(
        "--commits-file", help="with --contradictions: the PR's commit messages, concatenated"
    )
    args = ap.parse_args()
    body = sys.stdin.read()
    if args.strip:
        sys.stdout.write(strip_quoted(body))
    elif args.contradictions:
        commits = Path(args.commits_file).read_text() if args.commits_file else ""
        for problem in merge_contradictions(body, args.title, commits):
            print(problem)
    else:
        print("\n".join(str(n) for n in closing_refs(body)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

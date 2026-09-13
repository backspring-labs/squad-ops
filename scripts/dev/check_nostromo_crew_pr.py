#!/usr/bin/env python3
"""Enforce the Nostromo crew contract on a pull request: path boundaries and commit attribution.

A crew branch is `nostromo/<role>/...`. Each role may only touch the paths its role owns,
declared in .github/nostromo-path-boundaries.yml. Anything that is not a crew branch is
none of this check's business and passes immediately.

This exists because GitHub refuses push rules on public source repositories, so the branch
rulesets that guarantee *who* may write to a namespace cannot also constrain *what* they
write. See Nostromo DEV-006.

Two assertions, both only on crew branches:

  paths        the changed files stay inside the role's declared boundary
  attribution  every commit is authored by that role's bot

Attribution matters because the branch ruleset guarantees only one App may *push* to a
namespace, while the commit *author* is a separate field any git config can set. A launcher
that fails to export the author variables produces commits under whatever identity the host
happens to hold, and nothing announces it.

Usage:
  check_nostromo_crew_pr.py --branch <ref> --files-from <path|-> [--authors a@b ...]
                            [--expected-author <email>]

Exit 0 = allowed. Exit 1 = a boundary was crossed, attribution is wrong, or the branch names
a role with no rules.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

DEFAULT_RULES = Path(".github/nostromo-path-boundaries.yml")
CREW_PREFIX = "nostromo/"


def matches(path: str, pattern: str) -> bool:
    """`dir/**` means at or below dir/. Everything else is fnmatch. Nothing else.

    Deliberately narrow: fnmatch's `*` crosses `/`, which makes `src/*` mean more than a
    reader expects. Keeping the vocabulary tiny is worth more here than expressiveness.
    """
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def role_of(branch: str) -> str | None:
    """`nostromo/parker/fix-thing` -> `parker`. Anything else -> None."""
    if not branch.startswith(CREW_PREFIX):
        return None
    rest = branch[len(CREW_PREFIX):]
    role, sep, _ = rest.partition("/")
    return role if sep and role else None


def violations(files: list[str], role: str, rules: dict) -> list[str]:
    out: list[str] = []
    for pattern in rules.get("universal_forbidden", []):
        for f in files:
            if matches(f, pattern):
                out.append(f"{f} — no crew role may change this (it is part of the boundary itself)")

    spec = rules["roles"][role]
    if "allowed" in spec:
        allowed = spec["allowed"]
        for f in files:
            if not any(matches(f, p) for p in allowed):
                out.append(f"{f} — {role} may only touch: {', '.join(allowed)}")
    else:
        for pattern in spec.get("forbidden", []):
            for f in files:
                if matches(f, pattern):
                    out.append(f"{f} — {role} may not touch {pattern}")
    # Preserve order, drop duplicates: one line per file is what a reader wants.
    seen, uniq = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--branch", required=True, help="pull request head ref")
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--authors", nargs="*", default=None,
                    help="commit author emails on this pull request")
    ap.add_argument("--expected-author", default=None,
                    help="the bot email this role's commits must carry; derived by the workflow")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--files-from", help="file of newline-separated paths, or - for stdin")
    src.add_argument("--files", nargs="*", help="paths directly")
    args = ap.parse_args(argv)

    if args.files is not None:
        files = [f.strip() for f in args.files if f.strip()]
    elif args.files_from == "-":
        files = [ln.strip() for ln in sys.stdin if ln.strip()]
    else:
        files = [ln.strip() for ln in Path(args.files_from).read_text().splitlines() if ln.strip()]

    role = role_of(args.branch)
    if role is None:
        print(f"not a Nostromo crew branch ({args.branch or '<empty>'}) — no boundary applies")
        return 0

    # Imported here, not at module scope: the overwhelmingly common case is a pull request
    # that is not the crew's, and that path should need nothing installed.
    import yaml

    rules = yaml.safe_load(args.rules.read_text())

    if role not in rules.get("roles", {}):
        # Fail closed. A namespace with no declared boundary is an unreviewed boundary.
        print(f"FAIL: branch {args.branch} names crew role '{role}', which has no rules in {args.rules}")
        print("      Add its boundary before using the namespace, or rename the branch.")
        return 1

    failed = False

    found = violations(files, role, rules)
    if found:
        failed = True
        print(f"FAIL: {len(found)} path boundary violation(s) on branch {args.branch}\n")
        for v in found:
            print(f"  {v}")
        print(f"\n{role}'s boundary is declared in {args.rules}.")
        print("If the work genuinely belongs outside it, it belongs to a different role — hand it off")
        print("rather than widening the boundary. Widening is an owner decision.\n")
    else:
        print(f"ok: {len(files)} changed file(s) are inside {role}'s boundary")

    if args.expected_author and args.authors is not None:
        wrong = sorted({a for a in args.authors if a and a != args.expected_author})
        if wrong:
            failed = True
            print(f"FAIL: {len(wrong)} commit author(s) are not {role}'s identity\n")
            for a in wrong:
                print(f"  {a}")
            print(f"\n  expected: {args.expected_author}")
            print("\nThe ruleset controls who may push to this namespace; the commit author is a separate")
            print("field. A mismatch means the launcher did not export the author variables, so the commit")
            print("is attributed to whatever identity the host holds. Fix the launcher, not the history.")
        else:
            print(f"ok: all commits authored by {args.expected_author}")
    elif args.authors is not None:
        print("note: attribution not checked — no expected author supplied")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

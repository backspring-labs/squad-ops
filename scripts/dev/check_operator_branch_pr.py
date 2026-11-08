#!/usr/bin/env python3
"""Hold an outside operator's pull request to its branch's path boundary and commit identity
(#2975; the 2.7 plan's R7, the owner's ruling of 2026-11-08).

An operator's branch is ``<prefix><role>/...``. A branch ruleset guarantees which identity may push
to that namespace, but GitHub refuses push rules on public repositories, so it can't constrain which
*paths* that identity touches, and a commit's author is a field any git config can set. This check
is the substitute. A branch outside the operator's prefix passes at once.

**The policy is not in the repository** (SquadOps names no operator). It is the repository variable
``OPERATOR_BRANCH_POLICY``, which only an administrator can change, so a guarded pull request can't
change the policy that judges it. The workflow runs on ``pull_request_target``, from the default
branch, and never checks out or runs the pull request's code. The policy is JSON:

    {"branch_prefix": "<prefix>/",
     "bot_login": "<login with {role}, e.g. name-{role}[bot]>",
     "universal_forbidden": ["<pattern>", ...],
     "roles": {"<role>": {"allowed": [...]} | {"forbidden": [...]}, ...}}

A pattern ``dir/**`` matches anything at or below ``dir/``; anything else is an ``fnmatch`` pattern
over the repository-relative path. A role declares ``allowed`` (nothing else may be touched) or
``forbidden`` (anything else may), never both.

**It fails closed.** These fail every pull request; none of them disables the check:
- a missing or malformed policy;
- a role the policy doesn't declare;
- an operator's commit identity that couldn't be resolved;
- a commit by any other author.

The check's own files are always out of bounds to an operator's branch, whatever the policy says.

    check_operator_branch_pr.py --branch REF --files-from PATH|- [--authors EMAIL ...]
                                [--expected-author EMAIL] [--policy-json TEXT]

The policy is read from ``--policy-json``, or else from ``OPERATOR_BRANCH_POLICY`` in the
environment. Exit 0 = allowed; 1 = refused, with every reason printed.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any

POLICY_VARIABLE = "OPERATOR_BRANCH_POLICY"
#: The guard's own files: no operator branch may change what judges it.
GUARD_FILES = (
    ".github/workflows/operator-branch-checks.yml",
    "scripts/dev/check_operator_branch_pr.py",
)


class PolicyError(ValueError):
    """The policy is missing or doesn't say what the check needs."""


def load_policy(text: str | None) -> dict[str, Any]:
    """The policy, checked for the fields the check reads, or ``PolicyError`` saying what's wrong."""
    if not text or not text.strip():
        raise PolicyError(f"no policy: the repository variable {POLICY_VARIABLE} is unset or empty")
    try:
        policy = json.loads(text)
    except ValueError as e:
        raise PolicyError(f"{POLICY_VARIABLE} isn't JSON ({e})") from None
    if not isinstance(policy, dict):
        raise PolicyError(f"{POLICY_VARIABLE} isn't a JSON object")
    prefix = policy.get("branch_prefix")
    if not isinstance(prefix, str) or not prefix.endswith("/") or len(prefix) < 2:
        raise PolicyError("branch_prefix must be a non-empty prefix ending in '/'")
    login = policy.get("bot_login")
    if not isinstance(login, str) or "{role}" not in login:
        raise PolicyError("bot_login must be a login naming {role}")
    roles = policy.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise PolicyError("roles must declare at least one role")
    for role, spec in roles.items():
        if not isinstance(spec, dict) or ("allowed" in spec) == ("forbidden" in spec):
            raise PolicyError(f"role {role!r} declares exactly one of allowed or forbidden")
        patterns = spec.get("allowed", spec.get("forbidden"))
        if not isinstance(patterns, list) or not all(isinstance(p, str) and p for p in patterns):
            raise PolicyError(f"role {role!r}'s patterns must be a list of non-empty strings")
    extra = policy.get("universal_forbidden", [])
    if not isinstance(extra, list) or not all(isinstance(p, str) and p for p in extra):
        raise PolicyError("universal_forbidden must be a list of non-empty strings")
    return policy


def matches(path: str, pattern: str) -> bool:
    """``dir/**`` means at or below ``dir/``. Anything else is ``fnmatch``. Nothing else: its ``*``
    crosses ``/``, so a narrow vocabulary is easier to predict than a rich one."""
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def role_of(branch: str, prefix: str) -> str | None:
    """``<prefix>parker/fix-thing`` -> ``parker``; a branch outside the prefix -> ``None``. A
    branch that is the prefix with no role names an empty role, which no policy declares."""
    if not branch.startswith(prefix):
        return None
    role, _, _ = branch[len(prefix) :].partition("/")
    return role


def violations(files: list[str], role: str, policy: dict[str, Any]) -> list[str]:
    """Each changed file outside ``role``'s boundary, once, in the order the files came."""
    found: list[str] = []
    for f in files:
        if any(matches(f, p) for p in (*GUARD_FILES, *policy.get("universal_forbidden", []))):
            found.append(f"{f}: no operator branch may change this (it is the boundary itself)")
            continue
        spec = policy["roles"][role]
        if "allowed" in spec:
            if not any(matches(f, p) for p in spec["allowed"]):
                found.append(f"{f}: {role} may only touch {', '.join(spec['allowed'])}")
        else:
            hit = next((p for p in spec["forbidden"] if matches(f, p)), None)
            if hit is not None:
                found.append(f"{f}: {role} may not touch {hit}")
    return found


def judge(
    *,
    branch: str,
    files: list[str],
    authors: list[str] | None,
    expected_author: str | None,
    policy_text: str | None,
) -> tuple[bool, list[str]]:
    """``(allowed, lines)``: the verdict, and every line that explains it."""
    try:
        policy = load_policy(policy_text)
    except PolicyError as e:
        return False, [f"FAIL: {e}. The check fails closed until the policy is set."]
    role = role_of(branch, policy["branch_prefix"])
    if role is None:
        return True, [f"ok: {branch or '<empty>'} isn't an operator branch; no boundary applies"]
    if role not in policy["roles"]:
        return False, [
            f"FAIL: {branch} names role {role!r}, which the policy doesn't declare. A namespace "
            "with no declared boundary is an unreviewed boundary."
        ]
    lines: list[str] = []
    allowed = True
    found = violations(files, role, policy)
    if found:
        allowed = False
        lines.append(f"FAIL: {len(found)} path boundary violation(s) on {branch}")
        lines.extend(f"  {v}" for v in found)
        lines.append(
            "Work outside the boundary belongs to another role; widening it is the owner's."
        )
    else:
        lines.append(f"ok: {len(files)} changed file(s) are inside {role}'s boundary")
    if not expected_author:
        allowed = False
        lines.append(
            f"FAIL: {role}'s commit identity couldn't be resolved, so attribution can't be "
            "checked, and an unchecked operator branch is refused"
        )
    elif authors is None:
        allowed = False
        lines.append("FAIL: the pull request's commit authors weren't read")
    else:
        wrong = sorted({a for a in authors if a != expected_author})
        if wrong:
            allowed = False
            lines.append(f"FAIL: {len(wrong)} commit author(s) aren't {role}'s identity")
            lines.extend(f"  {a}" for a in wrong)
            lines.append(f"  expected: {expected_author}")
        else:
            lines.append(f"ok: every commit is authored by {expected_author}")
    return allowed, lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--branch", required=True)
    ap.add_argument("--files-from", required=True, help="a file of paths, one per line, or -")
    ap.add_argument("--authors", nargs="*", default=None)
    ap.add_argument("--expected-author", default=None)
    ap.add_argument("--policy-json", default=None)
    args = ap.parse_args(argv)
    raw = sys.stdin.read() if args.files_from == "-" else Path(args.files_from).read_text()
    files = [line.strip() for line in raw.splitlines() if line.strip()]
    allowed, lines = judge(
        branch=args.branch,
        files=files,
        authors=args.authors,
        expected_author=args.expected_author,
        policy_text=(
            args.policy_json if args.policy_json is not None else os.environ.get(POLICY_VARIABLE)
        ),
    )
    print("\n".join(lines))
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())

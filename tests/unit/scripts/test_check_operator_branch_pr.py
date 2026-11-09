"""#2975 (the 2.7 plan's R7): an outside operator's pull request is held to its branch's path
boundary and commit identity, by a policy the repository doesn't hold, and the check fails closed.
The policy here is invented: the repository names no operator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "check_operator_branch_pr.py"
_spec = importlib.util.spec_from_file_location("check_operator_branch_pr", _SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

BOT = "101+ops-designer[bot]@users.noreply.github.com"
POLICY = {
    "branch_prefix": "ops/",
    "bot_login": "ops-{role}[bot]",
    "universal_forbidden": [".github/rulesets/**"],
    "roles": {
        "designer": {"forbidden": ["src/**", "tests/**"]},
        "prover": {"allowed": ["tests/**"]},
    },
}


def _judge(branch="ops/designer/a-plan", files=("docs/plans/x.md",), authors=(BOT,), **kw):
    return check.judge(
        branch=branch,
        files=list(files),
        authors=None if authors is None else list(authors),
        expected_author=kw.get("expected", BOT),
        policy_text=kw.get("policy", json.dumps(POLICY)),
    )


def test_a_branch_outside_the_prefix_passes_without_reading_anything_else():
    """Bug caught: every contributor's pull request held to an operator's boundary, or failed for
    an identity it never had."""
    allowed, lines = _judge(branch="fix/2975-thing", files=["src/x.py"], authors=None, expected="")

    assert allowed and lines == ["ok: fix/2975-thing isn't an operator branch; no boundary applies"]


def test_an_operator_branch_inside_its_boundary_with_its_own_commits_passes():
    allowed, lines = _judge()

    assert allowed and lines == [
        "ok: 1 changed file(s) are inside designer's boundary",
        f"ok: every commit is authored by {BOT}",
    ]


@pytest.mark.parametrize(
    ("branch", "files", "line"),
    [
        ("ops/designer/x", ["src/a.py"], "src/a.py: designer may not touch src/**"),
        ("ops/prover/x", ["docs/a.md"], "docs/a.md: prover may only touch tests/**"),
        ("ops/prover/x", [".github/workflows/operator-branch-checks.yml"],
         ".github/workflows/operator-branch-checks.yml: no operator branch may change this (it is the boundary itself)"),
        ("ops/prover/x", ["scripts/dev/check_operator_branch_pr.py"],
         "scripts/dev/check_operator_branch_pr.py: no operator branch may change this (it is the boundary itself)"),
        ("ops/designer/x", [".github/rulesets/r.json"],
         ".github/rulesets/r.json: no operator branch may change this (it is the boundary itself)"),
    ],
    ids=["a-denylisted-path", "outside-an-allowlist", "the-workflow", "the-script", "a-policy-extra"],
)  # fmt: skip
def test_a_path_outside_the_boundary_is_refused_and_named(branch, files, line):
    """Bug caught: an out-of-bounds change accepted, or the guard's own files left editable by the
    branch it guards (an allowlist role that may touch tests/** still can't touch the check)."""
    expected = BOT.replace("designer", branch.split("/")[1])
    allowed, lines = _judge(branch=branch, files=files, authors=[expected], expected=expected)

    assert not allowed and f"  {line}" in lines


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        (dict(policy=None), "no policy: the repository variable OPERATOR_BRANCH_POLICY is unset"),
        (dict(policy=""), "no policy"),
        (dict(policy="{not json"), "isn't JSON"),
        (dict(policy=json.dumps({**POLICY, "branch_prefix": ""})), "branch_prefix"),
        (dict(policy=json.dumps({**POLICY, "roles": {"designer": {"allowed": [], "forbidden": []}}})),
         "exactly one of allowed or forbidden"),
        (dict(branch="ops/stranger/x"), "names role 'stranger', which the policy doesn't declare"),
        (dict(branch="ops/"), "names role '', which the policy doesn't declare"),
        (dict(expected=""), "commit identity couldn't be resolved"),
        (dict(authors=None), "commit authors weren't read"),
        (dict(authors=[BOT, "someone@example.com"]), "commit author(s) aren't designer's identity"),
    ],
    ids=["unset", "empty", "malformed", "no-prefix", "both-lists", "unknown-role", "no-role",
         "identity-unresolved", "authors-unread", "a-foreign-author"],
)  # fmt: skip
def test_the_check_fails_closed(kw, reason):
    """R7: missing configuration, an unknown role and a failed identity resolution never silently
    disable the protection. Bug caught: the old check's "attribution not checked" pass when the
    bot's identity couldn't be resolved, or a missing policy read as "no operator, nothing to do"."""
    allowed, lines = _judge(**kw)

    assert not allowed
    assert any(reason in line for line in lines), lines


def test_the_cli_reads_the_policy_from_the_environment_and_exits_by_the_verdict(
    tmp_path, monkeypatch, capsys
):
    """The workflow's call. Bug caught: the policy read from a tracked file, which a guarded pull
    request could edit, or an exit code that doesn't follow the verdict."""
    files = tmp_path / "files.txt"
    files.write_text("src/a.py\n")
    monkeypatch.setenv(check.POLICY_VARIABLE, json.dumps(POLICY))

    refused = check.main(["--branch", "ops/designer/x", "--files-from", str(files),
                          "--expected-author", BOT, "--authors", BOT])  # fmt: skip
    files.write_text("docs/a.md\n")
    allowed = check.main(["--branch", "ops/designer/x", "--files-from", str(files),
                          "--expected-author", BOT, "--authors", BOT])  # fmt: skip
    monkeypatch.delenv(check.POLICY_VARIABLE)
    unset = check.main(["--branch", "fix/x", "--files-from", str(files), "--expected-author", ""])

    assert (refused, allowed, unset) == (1, 0, 1)
    assert "src/a.py: designer may not touch src/**" in capsys.readouterr().out

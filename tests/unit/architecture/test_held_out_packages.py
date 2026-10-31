"""The campaign package's outcome readings never reach a squad task (SIP-0113 §4.1, phase 1; IR-4).

Since #2418 the campaign's evidence package carries each cycle's scenario results, contribution and
quality. It is a project-level vault artifact: it names no cycle and no run
(``CampaignProgress._store_evidence``). Every vault read that feeds a squad task lists artifacts by
cycle or by run, so the package is in none of them. This guard holds that: a ``list_artifacts`` call
that names neither is one of the project-level readers below, each read by a person or by the
campaign's own records, or it fails here before a squad role can be handed the readings.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

#: (file, function): project-level reads, and why no squad task's inputs come from them.
_PROJECT_LEVEL = {
    ("src/squadops/campaigns/progress.py", "materialize_package"): (
        "finds the package it is about to write, by the campaign's own identity"
    ),
    ("src/squadops/api/routes/campaigns/campaigns.py", "read_package"): (
        "the owner's read of the package (campaigns:read); the agent role holds only agents:write"
    ),
    ("src/squadops/api/routes/cycles/artifacts.py", "list_project_artifacts"): (
        "the artifacts API, read by a person through the CLI (cycles:read); the agent role holds "
        "only agents:write"
    ),
}


def _calls_without_cycle_or_run() -> list[tuple[str, str, int]]:
    found = []
    for base in ("src/squadops", "adapters"):
        for path in (_ROOT / base).rglob("*.py"):
            rel = path.relative_to(_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if not (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "list_artifacts"
                    ):
                        continue
                    named = {k.arg for k in node.keywords}
                    positional = len(node.args) >= 2  # (project_id, cycle_id, ...) by position
                    if not ({"cycle_id", "run_id"} & named or positional):
                        found.append((rel, fn.name, node.lineno))
    return found


def test_every_vault_listing_names_a_cycle_or_a_run_or_is_a_project_level_reader():
    """Bug caught: a new reader that lists a project's artifacts to feed a squad task, the shape
    a prior-cycle brief or a memory projection would take, so the next proposal is handed the
    campaign's scenario results before phase 2 is ruled."""
    unexplained = [
        f"{rel}:{line} ({fn})"
        for rel, fn, line in _calls_without_cycle_or_run()
        if (rel, fn) not in _PROJECT_LEVEL
    ]

    assert unexplained == [], (
        "a list_artifacts call that names no cycle and no run can reach the campaign package's "
        "held-out readings: list by cycle or run, or name it in _PROJECT_LEVEL with why no squad "
        f"task reads it: {unexplained}"
    )


def test_each_named_reader_still_exists():
    """A stale entry would excuse the next reader of the same name."""
    still = {(rel, fn) for rel, fn, _ in _calls_without_cycle_or_run()}

    assert set(_PROJECT_LEVEL) <= still, set(_PROJECT_LEVEL) - still

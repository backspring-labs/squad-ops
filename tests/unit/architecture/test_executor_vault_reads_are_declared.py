"""#3128 (the 2.9 plan's item 4): a vault read in the executor declares what a failure means.

``squadops.cycles.vault_reads.retrieve_recorded`` is the read for an artifact a run's record
names: a failure ends the run ``infrastructure_failed`` and names the artifact. A bare
``vault.retrieve(...)`` in ``squadops.execution`` declares nothing. Eleven of them caught the
failure and went on, and three more ended the run as ``other``. ``retrieve_or_absent`` declares
the opposite rule (#1990), which holds only where no run exists to end.

What bug would this catch? The next read added to the executor the old way: wrapped in a catch
that logs and continues, so a run goes on without an input its record names.
"""

from __future__ import annotations

import ast
from pathlib import Path

EXECUTION = Path(__file__).resolve().parents[3] / "src" / "squadops" / "execution"

#: A read that declares its failure in its own way, with what that is.
DECLARED_ANOTHER_WAY: dict[tuple[str, str], str] = {
    (
        "dispatched_flow_executor.py",
        "_resolve_artifact_contents",
    ): "raises ContentsUnavailable, which names the task and the file as well (#3120)",
    (
        "cycle_evidence.py",
        "_json_content",
    ): "the assessment's record then reads unaskable, a stated reading of its own, never absent",
}


def _undeclared_reads() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(EXECUTION.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                called = node.func
                bare = isinstance(called, ast.Attribute) and called.attr == "retrieve"
                absent = isinstance(called, ast.Name) and called.id == "retrieve_or_absent"
                if bare or absent:
                    found.add((path.name, function.name))
    return found


def test_every_vault_read_in_the_executor_is_declared():
    undeclared = _undeclared_reads() - set(DECLARED_ANOTHER_WAY)

    assert undeclared == set(), (
        "a vault read in squadops.execution must go through "
        "squadops.cycles.vault_reads.retrieve_recorded, so a failed retrieval ends the run by "
        f"name and is never read as absence (#3128): {sorted(undeclared)}"
    )


def test_the_list_names_only_reads_that_are_still_there():
    """The list can't outlive what it excuses: an entry whose read was fixed must be removed."""
    stale = set(DECLARED_ANOTHER_WAY) - _undeclared_reads()

    assert stale == set(), f"these reads are declared now, so they leave the list: {sorted(stale)}"

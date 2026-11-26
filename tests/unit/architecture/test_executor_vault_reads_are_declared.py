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

#: Reads that still use the older rule, each with why. They run at the gate between workloads,
#: after the run has completed, where a raise ends the cycle and not a run. Failing them closed
#: needs the cycle's ending to name the artifact and a Campaign to read it as the environment's
#: (SIP-0109 rows 10 and 11), which is #3128's last part. This list empties with it.
PENDING: dict[tuple[str, str], str] = {
    (
        "framing_gate_check.py",
        "reject_invalid_plan_before_workload_gate",
    ): "the framing gate's scan of the run's refs",
    ("dispatched_flow_executor.py", "_run_artifact_text"): "the run's merge decisions and plan",
    ("dispatched_flow_executor.py", "_run_manifest_content"): "the manifest the run authored",
    ("cycle_evidence.py", "_json_content"): "the assessment's evidence, read as unaskable",
    (
        "dispatched_flow_executor.py",
        "_load_contract_for_run",
    ): "the bound contract, read by the run's provisioning and by the framing gate alike",
}


#: A read that declares its failure in its own way, with what that is.
DECLARED_ANOTHER_WAY: dict[tuple[str, str], str] = {
    (
        "dispatched_flow_executor.py",
        "_resolve_artifact_contents",
    ): "raises ContentsUnavailable, which names the task and the file as well (#3120)",
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


def test_every_vault_read_in_the_executor_is_declared_or_named_as_pending():
    undeclared = _undeclared_reads() - set(PENDING) - set(DECLARED_ANOTHER_WAY)

    assert undeclared == set(), (
        "a vault read in squadops.execution must go through "
        "squadops.cycles.vault_reads.retrieve_recorded, so a failed retrieval ends the run by "
        f"name and is never read as absence (#3128): {sorted(undeclared)}"
    )


def test_the_pending_list_names_only_reads_that_are_still_there():
    """The list can't outlive what it excuses: an entry whose read was fixed must be removed."""
    stale = (set(PENDING) | set(DECLARED_ANOTHER_WAY)) - _undeclared_reads()

    assert stale == set(), f"these reads are declared now, so they leave the lists: {sorted(stale)}"

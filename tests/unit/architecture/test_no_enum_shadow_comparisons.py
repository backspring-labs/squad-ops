"""Architecture test: no enum-shadow string-literal comparisons (#380).

A comparison against a bare string literal that matches an existing ``StrEnum``
value is latent drift — an untyped shadow of a type that already exists (the
``terminal_status == "COMPLETED"`` class that propagated across three SIPs
before review caught it). It never fails at runtime because the two vocabularies
don't collide, so tests stay green and only human review — the least reliable
gate — can catch it. This test makes it fail CI instead.

Off-the-shelf ruff ``PLR2004`` (magic-value-comparison) is numeric-only and does
not flag string literals, hence this custom AST rule (same vehicle as
``test_forbidden_imports.py``).

The rule: in ``src/squadops`` domain code, a variable must not be compared
against a raw string literal that equals a domain enum's value (case-insensitive,
to catch upper/lower shadows). Compare against the enum member (or ``.value``),
or — at an adapter boundary translating an external vocabulary — add a justified
allowlist entry.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src" / "squadops"

# Reviewed, justified exceptions: {(repo_relative_path, literal_lower)}.
# Each entry MUST carry a comment explaining why the raw literal is correct here
# (a genuine boundary-translation point, or a word that coincidentally matches an
# enum value but is not that concept). A shared status WORD ("failed", "active")
# is defined by several enums AND by non-enum vocabularies, so value-matching
# flags coincidences — those are triaged here, not silently swept.
_ALLOWLIST: set[tuple[str, str]] = {
    # TaskResult.status is an UPPERCASE bare-str vocabulary ("SUCCEEDED"/...), NOT
    # the lowercase TaskStatus enum — case-mismatched, so the naive enum fix would
    # break it. Reconciliation tracked in #381 (twin of #377).
    ("src/squadops/capabilities/runner.py", "succeeded"),
    ("src/squadops/orchestration/orchestrator.py", "succeeded"),
    # CheckOutcome.status vocabulary (passed/failed/skipped/error) — CheckOutcome
    # is a dataclass, not a StrEnum (SIP-0092); "failed"/"error" coincide with
    # RunStatus/TaskStatus but are a different concept.
    ("src/squadops/capabilities/handlers/cycle/develop.py", "failed"),
    ("src/squadops/capabilities/handlers/cycle/develop.py", "error"),
    # External Ollama model-pull job status — a vendor vocabulary, not a domain enum.
    ("src/squadops/cli/commands/models.py", "failed"),
    # window_state() returns a duty-window lifecycle token ("active"/
    # "in_reserve_before"/...), not a CycleStatus/FlowState.
    ("src/squadops/runtime/recruitment.py", "active"),
    ("src/squadops/runtime/scheduler.py", "active"),
    # RuntimeMode is a Literal["duty","cycle","ambient"] (models.py:24), not an
    # enum; "cycle"/"duty" are its own values, coincidental with LifecycleScope.
    ("src/squadops/runtime/coordinator.py", "cycle"),
    # workload_statuses is a DTO-derived progress-token Sequence[str] that mixes
    # gate states ("gate_awaiting"/"rejected") with WorkloadStatus values; a
    # broader ad-hoc vocabulary, not a single enum (enum-ifying it is a follow-up).
    ("src/squadops/cycles/lifecycle.py", "rejected"),
    ("src/squadops/cycles/lifecycle.py", "pending"),
}

# Enum values this short/common that they produce coincidental matches are not
# worth guarding — matching them would flag unrelated string handling. (None today;
# kept as the escape hatch if a future enum defines e.g. "r"/"a".)
_IGNORED_VALUES: set[str] = set()


def _enum_base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _discover_enum_values(root: Path) -> dict[str, set[str]]:
    """Map each StrEnum/Enum string value (lowercased) -> the enum class(es) that own it."""
    values: dict[str, set[str]] = {}
    for py in root.rglob("*.py"):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not ({"StrEnum", "Enum"} & _enum_base_names(node)):
                continue
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                    and stmt.value.value
                ):
                    values.setdefault(stmt.value.value.lower(), set()).add(node.name)
    return values


def _string_literals_in_comparator(node: ast.expr):
    """Yield str-literal values directly in a comparator (incl. tuple/list/set members)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                yield elt.value


def _find_violations(root: Path, enum_values: dict[str, set[str]]) -> list[str]:
    violations: list[str] = []
    for py in root.rglob("*.py"):
        rel = str(py.relative_to(REPO_ROOT))
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for comparator in [node.left, *node.comparators]:
                for literal in _string_literals_in_comparator(comparator):
                    key = literal.lower()
                    if key in _IGNORED_VALUES or key not in enum_values:
                        continue
                    if (rel, key) in _ALLOWLIST:
                        continue
                    owners = ", ".join(sorted(enum_values[key]))
                    violations.append(f'  {rel}:{node.lineno}  == "{literal}"  shadows {owners}')
    return violations


def test_no_enum_shadow_string_comparisons() -> None:
    enum_values = _discover_enum_values(SRC)
    assert enum_values, "no StrEnum vocabularies discovered — discovery is broken"
    violations = _find_violations(SRC, enum_values)
    assert not violations, (
        f"{len(violations)} enum-shadow string comparison(s) — compare against the enum "
        f"member (or .value), not a raw literal (#380):\n" + "\n".join(violations)
    )

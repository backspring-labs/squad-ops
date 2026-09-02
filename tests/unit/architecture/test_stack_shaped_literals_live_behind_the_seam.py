"""A stack-shaped literal lives in a ``stack_*`` module or behind a stack parameter (#1131).

"Generic" scaffold code was stack #1 for six weeks: the FastAPI+React expander lived inline
in ``scaffold.py`` while stack #2 had a module of its own, so a check written while working
on one stack was exercised against only that stack. The commit that produced the 1.6.5 set's
false discard (``1b9b93a9``) defined "invokes the application" as an ``app/api/`` import — the
Next.js in-process model — inside the shared ``handlers/stub_detection.py``, and a green
React suite was thrown away (#1126). This test is the structural answer to the owner's
question of 2026-08-27, whether they must keep reminding us to stay stack-aware.

The rule: no string literal in live code under ``capabilities/handlers/`` or ``cycles/``
names a stack's file shape or toolchain unless the module is a ``stack_*`` module or the
line is allowlisted below with its reason. Comments and docstrings are not live code and
are not scanned; the literal has to be one the program executes on.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_capabilities]

REPO_ROOT = Path(__file__).resolve().parents[3]
SEARCH_ROOTS = (
    REPO_ROOT / "src" / "squadops" / "capabilities" / "handlers",
    REPO_ROOT / "src" / "squadops" / "cycles",
)

#: The shapes that name one stack's layout or toolchain. Matched inside string literals
#: only — an ``import pytest`` or a variable called ``vitest_report`` is not a literal.
STACK_SHAPED = re.compile(
    r"app/api/|\.test\.tsx?\b|\.spec\.tsx?\b|page\.tsx|App\.jsx|routes\.py|conftest|"
    r"\bmain\.py|\bvitest\b|\bpytest\b"
)

# Reviewed, justified exceptions: {(repo_relative_path, literal_as_matched)}. Each entry
# carries the reason the literal is correct where it is. Two-sided: an entry that no longer
# fires fails the test too, so the list cannot outlive the literal it excuses.
_H = "src/squadops/capabilities/handlers/"
_C = "src/squadops/cycles/"
_ALLOWLIST: set[tuple[str, str]] = {
    # --- the test runner: dispatch keyed by its `test_framework` parameter. The argv it
    # builds, the timeouts it reports and the report headings it writes name the tool it
    # runs; that is the runner's own vocabulary, parameterised by the stack that chose it.
    *{(_H + "test_runner.py", lit) for lit in ("pytest", "vitest")},
    # The backend import-check driver script (Python stacks only) names the pytest anchor
    # and the entry module it must not import — keyed by `test_framework` at the call.
    (_H + "test_runner.py", "conftest"),
    (_H + "test_runner.py", "main.py"),
    # SIP-0104's scaffold executor runs the fill-mode suite; the only registered emitter is
    # `nextjs_ts`, so vitest is the only runner it has. Becomes the stack's the day a second
    # emitter registers (#1122).
    (_H + "scaffold_execution.py", "vitest"),
    # Task-type classification keywords: both stacks' runner names as words that mark a
    # task as a test task. Vocabulary over the union, not a layout assumption.
    *{(_H + "cycle/validation.py", lit) for lit in ("pytest", "vitest")},
    # --- the check specs render into `docs/architecture/typed-check-menu.md`: an `example=`
    # names one real path from one stack each, and descriptions are prose. Documentation
    # embedded in the spec, not a predicate the program branches on.
    *{
        (_C + "acceptance_check_spec.py", lit)
        for lit in ("routes.py", "app/api/", "main.py", ".test.ts")
    },
    (_C + "acceptance_check_spec.py", "pytest"),
    # Prose in a validation message naming the pytest `test_*` convention.
    (_C + "implementation_plan.py", "pytest"),
    # Prompt text naming the frozen conftest — a string literal where a prompt fragment
    # belongs (#448's class); recorded here, not fixed by a structural guard.
    (_C + "contract_expectations.py", "conftest"),
}


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    return lines


def _live_string_hits(path: Path) -> list[tuple[int, str]]:
    """``(line, literal)`` for every stack-shaped match inside a non-docstring string."""
    text = path.read_text(encoding="utf-8")
    skip = _docstring_lines(ast.parse(text))
    hits: list[tuple[int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type not in (tokenize.STRING, tokenize.FSTRING_MIDDLE):
            continue
        if tok.start[0] in skip:
            continue
        for m in STACK_SHAPED.finditer(tok.string):
            hits.append((tok.start[0], m.group(0)))
    return hits


def _scan() -> tuple[list[str], set[tuple[str, str]]]:
    offenders: list[str] = []
    fired: set[tuple[str, str]] = set()
    for root in SEARCH_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if path.name.startswith("stack_") or "__pycache__" in path.parts:
                continue
            rel = str(path.relative_to(REPO_ROOT))
            for lineno, literal in _live_string_hits(path):
                key = (rel, literal)
                if key in _ALLOWLIST:
                    fired.add(key)
                    continue
                offenders.append(f"{rel}:{lineno}: {literal!r}")
    return offenders, fired


def test_stack_shaped_literals_live_behind_the_seam():
    offenders, _ = _scan()
    assert offenders == [], (
        "stack-shaped literal in a shared module — move it behind the stack seam "
        "(a stack_* module or a stack-parameterised predicate), or allowlist it with "
        "its reason:\n" + "\n".join(offenders)
    )


def test_no_allowlist_entry_outlives_its_literal():
    _, fired = _scan()
    stale = sorted(_ALLOWLIST - fired)
    assert stale == [], "allowlist entries that no longer fire — remove them:\n" + "\n".join(
        f"{p}: {lit!r}" for p, lit in stale
    )


def test_the_guard_would_have_caught_the_1b9b93a9_shape(tmp_path: Path):
    """The commit that discarded a green React suite keyed a shared detector on ``app/api/``."""
    module = tmp_path / "stub_detection.py"
    module.write_text('_ROUTE_IMPORT = r"""app/api/"""\n', encoding="utf-8")
    assert _live_string_hits(module) == [(1, "app/api/")]
    stack_module = tmp_path / "stack_nextjs_ts.py"
    stack_module.write_text('# app/api/ in a comment\n"""app/api/ in a docstring"""\n')
    assert _live_string_hits(stack_module) == []

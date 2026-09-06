"""#1316: the regression gate runs the tree, and what it leaves out is named with a reason.

The defect class, four times over (#200, #220, #207, #1316): the gate enumerated the
directories to run, a new directory under tests/unit missed the list, and its tests
never ran in the job CI marks Required — 437 of them at the last count, green for
up to ten months without ever executing. Each fix appended to the list; the next
directory missed it again. The fact "which tests are gated" had two authors.

The fix inverts the default: pytest and the test-quality lint run `tests/unit` whole,
and EXCLUDED_DIRS names what is deliberately left out. This module guards the shape:
a return to an include list, an exclusion without a reason, an exclusion that has
outlived its directory, and the lint and pytest reading different exclusions.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "dev" / "run_regression_tests.sh"
_UNIT_ROOT = _REPO / "tests" / "unit"

_spec = importlib.util.spec_from_file_location(
    "lint_test_quality", _REPO / "scripts" / "dev" / "lint_test_quality.py"
)
assert _spec is not None and _spec.loader is not None
lint = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lint
_spec.loader.exec_module(lint)


# --- the guard's model of the script ---------------------------------------------------


@dataclass(frozen=True)
class Gate:
    population: str | None
    excluded: tuple[tuple[str, str], ...]  # (path, reason)
    pytest_line: str | None
    lint_line: str | None


_POPULATION_RE = re.compile(r'^UNIT_TESTS="([^"]+)"\s*$', re.M)
_EXCLUDED_BLOCK_RE = re.compile(r"^EXCLUDED_DIRS=\(\n(.*?)^\)", re.M | re.S)
_ENTRY_RE = re.compile(r'^\s*"([^"]+)"\s*(?:#\s*(.*?))?\s*$')
_PYTEST_RE = re.compile(r"^pytest\b.*$", re.M)
_LINT_RE = re.compile(r"^python .*lint_test_quality\.py.*$", re.M)


def parse_gate(text: str) -> Gate:
    pop = _POPULATION_RE.search(text)
    block = _EXCLUDED_BLOCK_RE.search(text)
    excluded: list[tuple[str, str]] = []
    if block:
        for raw in block.group(1).splitlines():
            if not raw.strip() or raw.strip().startswith("#"):
                continue
            m = _ENTRY_RE.match(raw)
            if m:
                excluded.append((m.group(1), (m.group(2) or "").strip()))
    py = _PYTEST_RE.search(text)
    ln = _LINT_RE.search(text)
    return Gate(
        population=pop.group(1) if pop else None,
        excluded=tuple(excluded),
        pytest_line=py.group(0) if py else None,
        lint_line=ln.group(0) if ln else None,
    )


def _invocation_violations(kind: str, line: str | None, ignores_var: str) -> list[str]:
    if line is None:
        return [f"no {kind} invocation"]
    out: list[str] = []
    if '"$UNIT_TESTS"' not in line:
        out.append(f"{kind} does not run the population variable")
    if ignores_var not in line:
        out.append(f"{kind} does not apply EXCLUDED_DIRS")
    if re.search(r"tests/unit/\w", line):
        out.append(f"{kind} names directories — an include list is back")
    return out


def _exclusion_violations(excluded: tuple[tuple[str, str], ...], repo: Path) -> list[str]:
    out: list[str] = []
    for path, reason in excluded:
        if not reason:
            out.append(f"excluded {path} carries no reason")
        rel = Path(path)
        if rel.parts[:2] != ("tests", "unit") or len(rel.parts) != 3:
            out.append(f"excluded {path} is not a direct child of tests/unit")
        elif not (repo / rel).is_dir():
            out.append(f"excluded {path} no longer exists")
    return out


def gate_violations(gate: Gate, unit_root: Path) -> list[str]:
    """Every way the gate can drift, as one message each."""
    out: list[str] = []
    if gate.population != "tests/unit":
        out.append(f"population is {gate.population!r}, not 'tests/unit'")
    out += _invocation_violations("pytest", gate.pytest_line, "PYTEST_IGNORES")
    out += _invocation_violations("lint", gate.lint_line, "LINT_EXCLUDES")
    out += _exclusion_violations(gate.excluded, unit_root.parent.parent)
    return out


def unit_test_dirs(unit_root: Path) -> set[str]:
    """Direct children of tests/unit that hold at least one test file."""
    return {
        f"tests/unit/{d.name}"
        for d in unit_root.iterdir()
        if d.is_dir() and any(d.rglob("test_*.py"))
    }


# --- the real script ------------------------------------------------------------------


def test_the_gate_runs_the_tree_and_names_every_exclusion_with_a_reason():
    """Bug caught: the four-times-recurring drift — a hand-written include list
    that a new directory misses; or an exclusion added without saying why; or one
    that outlived its directory and now excludes nothing while reading as deliberate."""
    gate = parse_gate(_SCRIPT.read_text(encoding="utf-8"))
    assert gate_violations(gate, _UNIT_ROOT) == []


def test_every_unit_directory_is_either_run_or_named_excluded():
    """The issue's literal ask. With the population inverted this is exactly the
    set difference: a directory is gated unless EXCLUDED_DIRS names it — so any
    directory created tomorrow is gated tomorrow, which the old list could not say."""
    gate = parse_gate(_SCRIPT.read_text(encoding="utf-8"))
    excluded = {path.rstrip("/") for path, _ in gate.excluded}
    on_disk = unit_test_dirs(_UNIT_ROOT)
    run = on_disk - excluded
    assert run | (excluded & on_disk) == on_disk
    # The nine directories #1316 found ungated must be in the run set, by name — a
    # regression to the pre-#1316 list would drop exactly these.
    for name in (
        "memory",
        "config",
        "auth",
        "core",
        "ports",
        "bootstrap",
        "observability",
        "maintainer",
        "cli_tools",
    ):
        assert f"tests/unit/{name}" in run, name


# --- the guard against fabricated drift, so an empty exclusion list is not a free pass ----


_GOOD = """
UNIT_TESTS="tests/unit"
EXCLUDED_DIRS=(
)
python "$SCRIPT_DIR/lint_test_quality.py" ${LINT_EXCLUDES[@]+"${LINT_EXCLUDES[@]}"} "$UNIT_TESTS"
pytest -n auto ${PYTEST_IGNORES[@]+"${PYTEST_IGNORES[@]}"} "$UNIT_TESTS" "$@"
"""


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda s: s.replace(
                'pytest -n auto ${PYTEST_IGNORES[@]+"${PYTEST_IGNORES[@]}"} "$UNIT_TESTS" "$@"',
                'pytest -n auto tests/unit/api/ tests/unit/tasks/ "$@"',
            ),
            "an include list is back",
        ),
        (
            lambda s: s.replace(
                "EXCLUDED_DIRS=(\n)", 'EXCLUDED_DIRS=(\n    "tests/unit/memory/"\n)'
            ),
            "carries no reason",
        ),
        (
            lambda s: s.replace(
                "EXCLUDED_DIRS=(\n)",
                'EXCLUDED_DIRS=(\n    "tests/unit/no_such_dir/"   # retired in 1.9\n)',
            ),
            "no longer exists",
        ),
        (
            lambda s: s.replace(
                "EXCLUDED_DIRS=(\n)",
                'EXCLUDED_DIRS=(\n    "tests/unit/auth/adapters/"   # too deep\n)',
            ),
            "not a direct child",
        ),
        (
            lambda s: s.replace(
                'python "$SCRIPT_DIR/lint_test_quality.py" ${LINT_EXCLUDES[@]+"${LINT_EXCLUDES[@]}"} "$UNIT_TESTS"',
                'python "$SCRIPT_DIR/lint_test_quality.py" "$UNIT_TESTS"',
            ),
            "lint does not apply EXCLUDED_DIRS",
        ),
        (
            lambda s: s.replace('UNIT_TESTS="tests/unit"', 'UNIT_TESTS="tests/unit/api"'),
            "population",
        ),
    ],
    ids=["include-list", "no-reason", "stale-dir", "nested-dir", "lint-unshared", "narrowed"],
)
def test_the_guard_sees_each_way_the_gate_can_drift(mutation, expected):
    """Bug caught: a guard that passes on today's empty exclusion list and would
    also pass on the drift it exists to stop. Each mutation is one drift; the
    guard must name it."""
    assert gate_violations(parse_gate(_GOOD), _UNIT_ROOT) == []
    violations = gate_violations(parse_gate(mutation(_GOOD)), _UNIT_ROOT)
    assert any(expected in v for v in violations), violations


# --- the lint's --exclude, which the script relies on ------------------------------------


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    for rel in ("keep/test_a.py", "drop/test_b.py", "drop/deeper/test_c.py", "keep/helper.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("def test_x():\n    assert 1 == 1\n", encoding="utf-8")
    return tmp_path


def test_exclude_drops_the_directory_and_everything_under_it(tree: Path):
    """Bug caught: --exclude parsed but not applied, or applied only to the
    directory's own files — the script would then lint what pytest skips."""
    files = lint._collect_test_files([str(tree)], exclude=[str(tree / "drop")])
    assert [f.relative_to(tree).as_posix() for f in files] == ["keep/test_a.py"]


def test_a_file_named_explicitly_is_linted_even_under_an_excluded_directory(tree: Path):
    """Bug caught: an exclusion silently swallowing a file the caller asked for by
    name — the wrong direction for a lint that exists to be run on the file you edited."""
    target = tree / "drop" / "test_b.py"
    files = lint._collect_test_files([str(target)], exclude=[str(tree / "drop")])
    assert files == [target]


@pytest.mark.parametrize(
    ("argv", "paths", "exclude"),
    [
        (["--exclude", "a", "x"], ["x"], ["a"]),
        (["--exclude=a", "--exclude", "b", "x", "y"], ["x", "y"], ["a", "b"]),
        (["x"], ["x"], []),
    ],
)
def test_parse_args_separates_paths_from_exclusions(argv, paths, exclude):
    assert lint._parse_args(argv) == (paths, exclude)


def test_a_dangling_exclude_flag_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        lint._parse_args(["x", "--exclude"])
    assert exc.value.code == 2

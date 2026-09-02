"""``[project.dependencies]`` mirrors what the code imports, in both directions (#582).

Until 1.7.1 the package declared no runtime dependencies at all — the truth lived only in
``requirements/*.txt`` — so ``pip install squadops`` produced a package that raised
``ModuleNotFoundError: pydantic`` at first import, and every tool that reads metadata
(dependabot, pip-audit, a downstream ``pip install``) saw an empty tree. Two files now
carry the same fact; this test is what keeps them one fact:

* every third-party module the code imports is declared — in core, in an extra, or by a
  provider named here with its reason;
* every declared package is imported somewhere, or is listed here as runtime-only with
  the reason it must be installed although nothing imports it;
* the core list is ``requirements/base.txt`` plus the console script's own imports, and
  the ``api`` / ``agent`` extras are their ``requirements/*.txt`` line for line.

Guarded imports (``if TYPE_CHECKING:``, ``try: … except ImportError:``) are the package's
own opt-ins and are not required to be declared; if they are, the declaration must still
correspond to a real import. Every exception below is two-sided: an entry that stops
firing fails the test, so the list cannot outlive what it excuses.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_contracts]

REPO = Path(__file__).resolve().parents[3]
PYPROJECT = REPO / "pyproject.toml"
SOURCE_ROOTS = (REPO / "src" / "squadops", REPO / "adapters")
LOCAL_PACKAGES = {"squadops", "adapters"}

#: Top-level module -> the distribution(s) providing it, where the two differ. Everything
#: else is identity. A namespace shared by several distributions lists all of them.
MODULE_TO_DISTRIBUTION: dict[str, str | tuple[str, ...]] = {
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "a2a": "a2a-sdk",
    "ulid": "ulid-py",
    "aio_pika": "aio-pika",
    "multipart": "python-multipart",
    "opentelemetry": ("opentelemetry-api", "opentelemetry-sdk"),
}

#: Imported directly, declared only through the named provider — with the reason that
#: makes the transitive import safe rather than a drift trap. The provider must itself be
#: declared.
PROVIDED_BY: dict[str, tuple[str, str]] = {
    "starlette": (
        "fastapi",
        "FastAPI pins its Starlette range and does not re-export BaseHTTPMiddleware; "
        "importing it directly is the documented FastAPI form (api/middleware/auth.py).",
    ),
    "pyarrow": (
        "lancedb",
        "LanceDB's table API is Arrow; pyarrow is lancedb's own hard dependency, imported "
        "lazily beside it (adapters/memory/lancedb.py).",
    ),
}

#: Declared, never imported — with the reason it must be installed anyway.
RUNTIME_ONLY: dict[str, str] = {
    "python-multipart": (
        "FastAPI parses Form(...)/File(...) parameters through it at request time "
        "(api/routes/cycles/artifacts.py) and raises at route registration without it."
    ),
}

#: Imports of modules that exist nowhere — a defect on record, keyed to its issue. The
#: entry must go when the import is fixed (the stale check below).
KNOWN_DEAD_IMPORTS: dict[str, str] = {
    "agents": "#1241 — adapters/capabilities/aci_executor.py imports agents.tasks.models",
}

#: The console script's own imports, core because `[project.scripts]` installs it
#: unconditionally; they are not in base.txt because the images never run the CLI.
CONSOLE_SCRIPT_DEPENDENCIES = {"typer", "rich"}


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*([^#;]*)")


def _requirement(line: str) -> tuple[str, str] | None:
    """``(normalised name, specifier)`` for a requirement line, or None for a non-line."""
    stripped = line.split("#", 1)[0].strip()
    if not stripped or stripped.startswith("-"):
        return None
    m = _REQ.match(stripped)
    assert m, f"unparseable requirement line {line!r}"
    return _normalise(m.group(1)), m.group(3).strip()


def _declared() -> dict[str, dict[str, str]]:
    """``{"core": {name: spec}, "<extra>": {name: spec}}`` from pyproject.toml."""
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    out: dict[str, dict[str, str]] = {"core": {}}
    for dep in project.get("dependencies", ()):
        name, spec = _requirement(dep)  # type: ignore[misc]
        out["core"][name] = spec
    for extra, deps in project.get("optional-dependencies", {}).items():
        out[extra] = dict(_requirement(d) for d in deps)  # type: ignore[misc]
    return out


def _requirements_file(name: str) -> dict[str, str]:
    return dict(
        req
        for req in (
            _requirement(ln) for ln in (REPO / "requirements" / name).read_text().splitlines()
        )
        if req
    )


def _top_level(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module.split(".")[0]]
    return []


def _handles_import_error(node: ast.Try) -> bool:
    names = {"ImportError", "ModuleNotFoundError"}
    for handler in node.handlers:
        t = handler.type
        if t is None or getattr(t, "id", None) in names:
            return True
        if isinstance(t, ast.Tuple) and any(getattr(e, "id", None) in names for e in t.elts):
            return True
    return False


def _guarded_lines(tree: ast.AST) -> set[int]:
    """Line numbers inside ``if TYPE_CHECKING:`` bodies and import-error-guarded ``try`` bodies."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        body = None
        if isinstance(node, ast.If) and (
            getattr(node.test, "id", None) == "TYPE_CHECKING"
            or getattr(node.test, "attr", None) == "TYPE_CHECKING"
        ):
            body = node.body
        elif isinstance(node, ast.Try) and _handles_import_error(node):
            body = node.body
        if body:
            for stmt in body:
                lines.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return lines


def _imports() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """``(unguarded, guarded)``: third-party top-level module -> files importing it."""
    stdlib = set(sys.stdlib_module_names)
    unguarded: dict[str, set[str]] = {}
    guarded: dict[str, set[str]] = {}
    for root in SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = _guarded_lines(tree)
            rel = str(path.relative_to(REPO))
            for node in ast.walk(tree):
                for top in _top_level(node):
                    if top in stdlib or top in LOCAL_PACKAGES or top == "__future__":
                        continue
                    bucket = guarded if node.lineno in skip else unguarded
                    bucket.setdefault(top, set()).add(rel)
    return unguarded, guarded


def _distributions(module: str) -> set[str]:
    mapped = MODULE_TO_DISTRIBUTION.get(module, module)
    names = (mapped,) if isinstance(mapped, str) else mapped
    return {_normalise(n) for n in names}


def _imported_distributions(modules) -> set[str]:
    return {dist for module in modules for dist in _distributions(module)}


def _all_declared() -> set[str]:
    return {name for group in _declared().values() for name in group}


def test_every_unguarded_import_is_declared():
    """An import nothing declares is the empty-metadata defect one package at a time."""
    unguarded, _ = _imports()
    declared = _all_declared()
    missing = []
    for module, files in sorted(unguarded.items()):
        if module in KNOWN_DEAD_IMPORTS:
            continue
        dists = _distributions(module)
        if dists <= declared:
            continue
        if module in PROVIDED_BY:
            provider, _reason = PROVIDED_BY[module]
            assert _normalise(provider) in declared, (
                f"{module} is excused as provided by {provider}, which is not declared itself"
            )
            continue
        missing.append(f"  {module:18} ({', '.join(sorted(dists))}) in {sorted(files)[0]}")
    assert not missing, (
        "These third-party modules are imported unconditionally and declared nowhere in\n"
        "pyproject.toml (core or an extra):\n"
        + "\n".join(missing)
        + "\n\nDeclare the distribution, or if it is deliberately reached through another\n"
        "package, add it to PROVIDED_BY with the reason."
    )


def test_every_declared_package_is_imported():
    """A declared package nothing imports is dead weight in every image that installs it —\n
    the shape the #582 audit found twice (`sqlalchemy`, `jinja2`, both in api.txt for years)."""
    unguarded, guarded = _imports()
    imported = _imported_distributions((*unguarded, *guarded))
    unused = sorted(
        name
        for name in _all_declared()
        if name not in imported and name not in {_normalise(k) for k in RUNTIME_ONLY}
    )
    assert not unused, (
        "These packages are declared in pyproject.toml but no module imports them:\n"
        + "\n".join(f"  {n}" for n in unused)
        + "\n\nRemove the declaration, or add the package to RUNTIME_ONLY with the reason it must\n"
        "be installed although nothing imports it."
    )


def test_core_is_base_txt_plus_the_console_script():
    """One fact, two files: the floors in base.txt are the floors in pyproject.toml."""
    core = _declared()["core"]
    base = _requirements_file("base.txt")
    assert set(core) - CONSOLE_SCRIPT_DEPENDENCIES == set(base), (
        f"core differs from requirements/base.txt: "
        f"only in pyproject {sorted(set(core) - CONSOLE_SCRIPT_DEPENDENCIES - set(base))}, "
        f"only in base.txt {sorted(set(base) - set(core))}"
    )
    drift = {n: (core[n], base[n]) for n in base if core[n] != base[n]}
    assert not drift, f"specifier drift between pyproject core and base.txt: {drift}"
    assert CONSOLE_SCRIPT_DEPENDENCIES <= set(core)


@pytest.mark.parametrize("extra, requirements", [("api", "api.txt"), ("agent", "agent.txt")])
def test_image_extras_mirror_their_requirements_files(extra: str, requirements: str):
    declared = _declared()[extra]
    expected = _requirements_file(requirements)
    assert declared == expected, (
        f"[{extra}] extra and requirements/{requirements} disagree:\n"
        f"  only in pyproject: {sorted(set(declared) - set(expected))}\n"
        f"  only in {requirements}: {sorted(set(expected) - set(declared))}\n"
        f"  specifier drift: "
        f"{ {n: (declared[n], expected[n]) for n in set(declared) & set(expected) if declared[n] != expected[n]} }"
    )


def test_no_exception_outlives_what_it_excuses():
    """Two-sided: an excused module that is no longer imported, a runtime-only package no
    longer declared, or a dead import that has been fixed must be removed from this file."""
    unguarded, guarded = _imports()
    imported = set(unguarded) | set(guarded)
    stale = []
    for module in PROVIDED_BY:
        if module not in imported:
            stale.append(f"PROVIDED_BY[{module!r}] — nothing imports it any more")
    declared = _all_declared()
    for name in RUNTIME_ONLY:
        if _normalise(name) not in declared:
            stale.append(f"RUNTIME_ONLY[{name!r}] — no longer declared")
        elif _normalise(name) in _imported_distributions(imported):
            stale.append(f"RUNTIME_ONLY[{name!r}] — now imported; it is an ordinary dependency")
    for module, issue in KNOWN_DEAD_IMPORTS.items():
        if module not in unguarded:
            stale.append(f"KNOWN_DEAD_IMPORTS[{module!r}] — the import is gone; close out {issue}")
    assert not stale, "remove these entries:\n" + "\n".join(f"  {s}" for s in stale)


def test_the_console_script_imports_without_the_api_framework():
    """``squadops.cli.main`` is what ``[project.scripts]`` installs, and a bare install
    carries no FastAPI. Until #582 the chain cli → contracts/cycle_request_profiles → the
    routes package ``__init__`` → artifacts.py reached fastapi (and python-multipart, at
    route registration), so the console script ran only where the api extra happened to
    be installed. The DTO it needs now lives in ``api/cycle_schemas.py``.

    Blocking the modules in ``sys.modules`` makes the import raise exactly as it does in a
    venv that never installed them; the fresh-venv CI job proves the same from metadata."""
    code = (
        "import sys; sys.modules['fastapi'] = None; sys.modules['starlette'] = None; "
        "import squadops.cli.main"
    )
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'src'}{os.pathsep}{REPO}"}
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO, env=env
    )
    assert proc.returncode == 0, (
        "the console script's import chain reaches the API framework:\n" + proc.stderr[-2500:]
    )


def test_the_scan_sees_the_package():
    """A scanner that silently reads nothing would make every check above vacuous."""
    unguarded, guarded = _imports()
    assert "pydantic" in unguarded and len(unguarded["pydantic"]) >= 5
    assert "yaml" in unguarded
    assert "lancedb" in guarded, "the TYPE_CHECKING / try-except guard detection is broken"


def test_the_guard_detection_reads_both_forms(tmp_path: Path):
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import lancedb\n"
        "try:\n"
        "    import langfuse\n"
        "except ImportError:\n"
        "    langfuse = None\n"
        "import pydantic\n"
    )
    tree = ast.parse(source)
    guarded = _guarded_lines(tree)
    assert 3 in guarded and 5 in guarded and 8 not in guarded

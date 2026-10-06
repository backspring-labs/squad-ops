"""Reporting-only lint and complexity findings on the delivered app (#1937).

The record of the app's technical debt that 2.4's lead-proposed refactors start from: ruff over
the Python, ESLint over the JS/TS, once per qa run over the tree the run evaluated, counted by rule
and by file. **Never a gate.** Nothing reads these findings to judge a task: they ride the qa
task's outputs, the run's summary and the campaign's evidence package, and no check, verdict,
signature or prompt reads them. A failed check costs a correction round, and lint findings are
not defects.

The rule sets are fixed here, chosen up front, so the corpus counts the same things across every
run. The tools come from the qa image's provisioning (``requirements/agent.txt`` for ruff,
``agents/instances/qa/npm-global-packages.txt`` for ESLint), and nothing in the delivered tree
decides what is linted or how: ruff runs ``--isolated``, and ESLint takes only the config shipped
in ``delivered_lint_eslint.cjs``. A tool that is missing, fails, or runs past its limit is named
under ``unavailable``, and the reading says what it did not cover, never a silent zero.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping
from importlib.resources import files as package_files
from pathlib import Path, PurePosixPath
from typing import Any

from squadops.core.bounded_run import run_bounded_sync

#: Bumped when the reading's shape changes; a reader checks it first.
LINT_READING_VERSION = 1

#: ruff's rule families, beyond the pyflakes F-rules: pycodestyle errors and warnings (E, W),
#: bugbear's likely bugs (B), mccabe complexity (C90), simplifications (SIM), outdated syntax
#: (UP) and pylint's refactor family (PLR: too many branches, statements, arguments, returns).
RUFF_RULES = ("F", "E", "W", "B", "C90", "SIM", "UP", "PLR")

#: What ESLint reads; every other file is ruff's or nobody's.
JS_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")

#: Generated or installed trees: never the authored app.
SKIPPED_DIRS = frozenset({"node_modules", ".next", "dist", "build", "__pycache__", ".venv"})

#: Each tool's limit, so a pathological tree cannot hold the qa task.
TOOL_TIMEOUT_S = 120.0

#: The most files a reading names; past it, the count of the rest is kept instead.
MAX_FILES_NAMED = 50

_ESLINT_RUNNER = "delivered_lint_eslint.cjs"


def _authored(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool(parts) and not any(p in SKIPPED_DIRS for p in parts) and ".." not in parts


def _ruff(root: Path) -> tuple[str | None, list[tuple[str, str]], str | None]:
    """(version, [(rule, file)], why it could not run)."""
    if shutil.which("ruff") is None:
        return None, [], "ruff is not installed"
    try:
        version = run_bounded_sync(["ruff", "--version"], cwd=root, timeout=10)
        run = run_bounded_sync(
            [
                "ruff",
                "check",
                "--isolated",
                "--no-cache",
                "--exit-zero",
                "--output-format",
                "json",
                "--select",
                ",".join(RUFF_RULES),
                ".",
            ],
            cwd=root,
            timeout=TOOL_TIMEOUT_S,
        )
    except OSError as e:
        return None, [], f"ruff did not start: {e}"
    if run.timed_out:
        return None, [], f"ruff ran past {TOOL_TIMEOUT_S:.0f}s"
    if run.returncode != 0:
        return None, [], f"ruff exited {run.returncode}: {run.stderr.decode()[-300:]}"
    try:
        found = json.loads(run.stdout or b"[]")
    except json.JSONDecodeError as e:
        return None, [], f"ruff's report did not parse: {e}"
    named = version.stdout.decode().strip() or None
    return (
        named,
        [(f"ruff:{f.get('code') or 'syntax'}", _relative(f["filename"], root)) for f in found],
        None,
    )


def _eslint(root: Path) -> tuple[str | None, list[tuple[str, str]], str | None]:
    if shutil.which("node") is None:
        return None, [], "node is not installed"
    runner = package_files("squadops.capabilities") / _ESLINT_RUNNER
    try:
        run = run_bounded_sync(["node", str(runner), str(root)], cwd=root, timeout=TOOL_TIMEOUT_S)
    except OSError as e:
        return None, [], f"node did not start: {e}"
    if run.timed_out:
        return None, [], f"eslint ran past {TOOL_TIMEOUT_S:.0f}s"
    if run.returncode != 0:
        return None, [], f"eslint exited {run.returncode}: {run.stderr.decode()[-300:]}"
    try:
        report = json.loads(run.stdout)
    except json.JSONDecodeError as e:
        return None, [], f"eslint's report did not parse: {e}"
    found = [
        (f"eslint:{rule}", entry["file"]) for entry in report["results"] for rule in entry["rules"]
    ]
    return report.get("version"), found, None


def _relative(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path


def reading(
    findings: list[tuple[str, str]],
    *,
    tools: Mapping[str, str | None],
    linted: Mapping[str, int],
    unavailable: Mapping[str, str],
) -> dict[str, Any]:
    """The findings counted by rule and by file: the shape the run summary keeps."""
    by_file = Counter(file for _, file in findings)
    named = dict(by_file.most_common(MAX_FILES_NAMED))
    return {
        "version": LINT_READING_VERSION,
        "tools": {k: v for k, v in tools.items() if v},
        "files_linted": dict(linted),
        "total": len(findings),
        "by_rule": dict(sorted(Counter(rule for rule, _ in findings).items())),
        "by_file": dict(sorted(named.items())),
        "files_not_named": len(by_file) - len(named),
        "unavailable": dict(unavailable),
    }


def lint_delivered(tree: Mapping[str, str]) -> dict[str, Any]:
    """The reading for ``tree`` (path to content): every authored file written to a scratch
    directory, ruff over its Python and ESLint over its JS/TS. Never raises: a tool that cannot
    run is named under ``unavailable``."""
    authored = {p: c for p, c in tree.items() if _authored(p)}
    py = [p for p in authored if p.endswith(".py")]
    js = [p for p in authored if p.endswith(JS_SUFFIXES)]
    findings: list[tuple[str, str]] = []
    tools: dict[str, str | None] = {}
    unavailable: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="qa_lint_") as tmp:
        root = Path(tmp)
        for path, content in authored.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for name, files_of_kind, run in (("ruff", py, _ruff), ("eslint", js, _eslint)):
            if not files_of_kind:
                continue
            version, found, why = run(root)
            if why:
                unavailable[name] = why
                continue
            tools[name] = version
            findings.extend(found)
    return reading(
        findings,
        tools=tools,
        linted={"python": len(py), "js": len(js)},
        unavailable=unavailable,
    )

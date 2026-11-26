"""The loaded checks' rows are the tracked file's and each file's beside it (#3268).

While every row was appended to ``loaded_checks.yaml``'s end, any two open pull requests
conflicted there. A new row now goes in a file of its own, and every reader takes both.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"
TRACKED = _DEV / "loaded_checks.yaml"
#: The first issue whose rows go in a file of their own. A pull request for an earlier issue was
#: already open when the directory came, and may still land a row in the tracked file.
FIRST_ISSUE_IN_FILES = 3268
#: The tracked file's rows whose id starts with no issue number: these seven, and no more.
UNNUMBERED = frozenset(
    {
        "retake-after-patch",
        "route-response-fields",
        "nextjs-client-surface",
        "scenario-entity-resolution",
        "nextjs-page-suite-invokes",
        "nextjs-page-suite-invokes-api",
        "h10-vitest-reader",
    }
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _DEV / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rows = _load("loaded_check_rows")
loaded = _load("verify_loaded")


def _row(row_id: str, code: str = "print(1)") -> dict:
    return {"id": row_id, "what": "w", "container": "squadops-nat", "code": code, "expect": "1"}


def _write(path: Path, *listed: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"checks": list(listed)}))
    return path


def test_the_rows_are_the_tracked_files_then_each_file_beside_it_by_name(tmp_path):
    tracked = _write(tmp_path / "loaded_checks.yaml", _row("100"), _row("200"))
    _write(tmp_path / "loaded_checks.d" / "3300.yaml", _row("3300"))
    _write(tmp_path / "loaded_checks.d" / "3250.yaml", _row("3250-a"), _row("3250-b"))
    (tmp_path / "loaded_checks.d" / "README.md").write_text("not rows")

    assert [r["id"] for r in rows.rows_at(tracked)] == ["100", "200", "3250-a", "3250-b", "3300"]


def test_a_tracked_file_with_nothing_beside_it_is_read_alone(tmp_path):
    """The edge every checkout was in before the directory existed."""
    tracked = _write(tmp_path / "loaded_checks.yaml", _row("100"))

    assert [r["id"] for r in rows.rows_at(tracked)] == ["100"]


def test_an_id_held_twice_is_refused_naming_both_files(tmp_path):
    """Bug caught: two files each adding row ``3300``, and ``--only 3300`` running one of them
    while the other's check is never read."""
    tracked = _write(tmp_path / "loaded_checks.yaml", _row("3300"))
    beside = _write(tmp_path / "loaded_checks.d" / "3300.yaml", _row("3300"))

    with pytest.raises(ValueError) as refused:
        rows.rows_at(tracked)

    assert str(refused.value) == (
        f"loaded check '3300' is in both {tracked} and {beside}: an id names one row"
    )


@pytest.mark.parametrize(
    "content",
    ["rows:\n  - {id: a}\n", "checks: {id: a}\n", "- id: a\n", "checks:\n  - a\n"],
    ids=["another key", "checks that aren't a list", "a bare list", "a row that isn't an object"],
)
def test_a_file_that_holds_no_rows_is_refused_by_name(tmp_path, content):
    """Bug caught: a misnamed key read as "no rows", so the file's checks are never run and the
    deploy reads fully loaded."""
    tracked = _write(tmp_path / "loaded_checks.yaml", _row("100"))
    beside = tmp_path / "loaded_checks.d" / "3300.yaml"
    beside.parent.mkdir()
    beside.write_text(content)

    with pytest.raises(ValueError, match="holds no `checks` list of rows") as refused:
        rows.rows_at(tracked)

    assert str(beside) in str(refused.value)


def test_verify_loaded_runs_a_row_kept_in_a_file_of_its_own(tmp_path, monkeypatch, capsys):
    """Wiring, entered at ``verify_loaded.main`` as a rebuild's check is. Bug caught: the
    script reading the one file alone, so a new row is "no loaded check has id" and a deploy
    that lacks its fix reads fully loaded."""
    tracked = _write(tmp_path / "loaded_checks.yaml", _row("100"))
    _write(tmp_path / "loaded_checks.d" / "3300.yaml", _row("3300", "print('beside')"))
    monkeypatch.setattr(loaded, "CHECKS", tracked)
    asked = []

    def run(cmd, **kwargs):
        asked.append((cmd, kwargs.get("input")))
        return subprocess.CompletedProcess(cmd, 0, "1\n", "")

    monkeypatch.setattr(loaded.subprocess, "run", run)

    assert loaded.main(["--only", "3300"]) == 0

    [(cmd, code)] = [a for a in asked if a[0][:2] == ["docker", "exec"]]
    assert ("squadops-nat" in cmd, code) == (True, "print('beside')")
    assert "1 loaded" in capsys.readouterr().out


def test_the_tracked_file_takes_no_new_row():
    """A row appended to the tracked file conflicts with every other open pull request's. Bug
    caught: the habit. A row for an issue filed since the directory came, or one with no issue
    number, goes in ``scripts/dev/loaded_checks.d/<issue>.yaml``."""
    import re

    ids = [str(row["id"]) for row in yaml.safe_load(TRACKED.read_text())["checks"]]
    numbered = {i: int(m.group()) for i in ids if (m := re.match(r"\d+", i))}

    misplaced = sorted(
        [i for i, issue in numbered.items() if issue >= FIRST_ISSUE_IN_FILES]
        + [i for i in ids if i not in numbered and i not in UNNUMBERED]
    )

    assert misplaced == [], (
        f"rows {misplaced} were added to scripts/dev/loaded_checks.yaml: move each to a file of "
        "its own under scripts/dev/loaded_checks.d/, named for its issue (see that directory's "
        "README)"
    )

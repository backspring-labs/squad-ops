"""The loaded checks' rows, read from the tracked file and the files beside it (#3268).

``loaded_checks.yaml`` holds the rows up to 2026-11-26. A new row goes in a file of its own
under ``loaded_checks.d/``, named for its issue (``3268.yaml``), with the same top-level
``checks:`` list. Two pull requests that each add a row then touch different files: while every
row was appended to the one file's end, each merge put every other open pull request in conflict
there (counted on #3268).

Every reader takes its rows from :func:`rows_at`, so the file and the directory are one set:
``verify_loaded.py``, ``verification_set_driver.py`` and the test that runs each row on the
source. A YAML anchor reaches only its own file, so rows that share one stay in one file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def rows_directory(tracked: Path) -> Path:
    """The directory of row files beside ``tracked``: ``loaded_checks.yaml`` has
    ``loaded_checks.d``."""
    return tracked.with_suffix(".d")


def rows_at(tracked: Path) -> list[dict[str, Any]]:
    """Every row: the tracked file's, then each file's under its directory, by file name.

    Raises ``ValueError`` naming the file for one that holds no ``checks`` list, and naming both
    files for an id held twice: a row asked for by id must be one row."""
    files = [tracked, *sorted(rows_directory(tracked).glob("*.yaml"))]
    rows: list[dict[str, Any]] = []
    held_in: dict[str, Path] = {}
    for path in files:
        document = yaml.safe_load(path.read_text())
        listed = document.get("checks") if isinstance(document, dict) else None
        if not isinstance(listed, list) or not all(isinstance(row, dict) for row in listed):
            raise ValueError(f"{path} holds no `checks` list of rows")
        for row in listed:
            row_id = str(row.get("id"))
            if row_id in held_in:
                raise ValueError(
                    f"loaded check {row_id!r} is in both {held_in[row_id]} and {path}: an id "
                    "names one row"
                )
            held_in[row_id] = path
            rows.append(row)
    return rows

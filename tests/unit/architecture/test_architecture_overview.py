"""The architecture map cannot drift silently (#1989).

CLAUDE.md's package list, the map every session reads first, omitted 9 of the 25 core packages and 8
of the 18 adapter packages by 2026-10-04 (``campaigns``, 2.0's headline, among them). The map now
lives in ``docs/architecture/overview.md``, with one ``### `package` `` entry per package, and this
holds it both ways: every package has an entry, and every entry names a package that exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = REPO_ROOT / "docs" / "architecture" / "overview.md"


def _packages(root: Path, prefix: str) -> set[str]:
    return {
        f"{prefix}.{d.name}" for d in root.iterdir() if d.is_dir() and (d / "__init__.py").exists()
    }


def _entries(text: str) -> set[str]:
    return set(re.findall(r"^### `((?:squadops|adapters)\.[a-z_]+)`$", text, re.M))


def test_every_package_has_an_entry_and_every_entry_a_package():
    """Bugs caught: a package added with no map entry (how ``campaigns`` went unlisted), and an
    entry outliving the package it describes (how the map gets trusted while wrong)."""
    packages = _packages(REPO_ROOT / "src" / "squadops", "squadops") | _packages(
        REPO_ROOT / "adapters", "adapters"
    )
    entries = _entries(OVERVIEW.read_text(encoding="utf-8"))

    assert sorted(packages - entries) == [], (
        "packages with no entry in docs/architecture/overview.md"
    )
    assert sorted(entries - packages) == [], "overview entries naming no package"


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("### `squadops.campaigns`\nbody\n", {"squadops.campaigns"}),
        ("### `adapters.cycles`\n", {"adapters.cycles"}),
        # Prose that names a package is not an entry.
        ("The `squadops.cycles` package runs cycles.\n", set()),
        ("### squadops.cycles\n", set()),
    ],
)
def test_only_an_entry_heading_counts(text, found):
    """Bug caught: a mention in another entry's prose satisfying the guard for a package that has
    no entry of its own."""
    assert _entries(text) == found

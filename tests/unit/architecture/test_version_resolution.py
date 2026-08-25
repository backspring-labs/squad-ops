"""The framework version comes from the file, not from an install-time copy (#1089).

`pyproject.toml` is the single source. Installed metadata is a copy made when the
package was installed — correct for a real install, and stale from the moment the file
changes in an editable one. On a tree at 1.6.3 the documented-authoritative call
returned **1.4.0**, the CLI printed it, and `version_cli.py` — whose entire job is
version correctness — announced "Version bumped: 1.4.0 -> 1.6.3" while correctly
editing 1.6.2.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PYPROJECT = REPO / "pyproject.toml"

pytestmark = [pytest.mark.domain_contracts]


def _file_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(), re.MULTILINE)
    assert m, "pyproject.toml has no version"
    return m.group(1)


def test_package_version_matches_the_file_not_the_installed_copy():
    """The bug, pinned. This fails whenever an editable install goes stale."""
    import squadops

    assert squadops.__version__ == _file_version()


def test_maintainer_tool_reads_the_file_it_edits():
    """`version_cli.py`'s "from" is a claim about `pyproject.toml`, so it must read it."""
    import importlib.util
    import sys

    path = REPO / "scripts" / "maintainer" / "version_cli.py"
    spec = importlib.util.spec_from_file_location("version_cli_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["version_cli_under_test"] = mod
    spec.loader.exec_module(mod)

    assert mod.get_framework_version() == _file_version()


class TestResolutionOrder:
    """The order matters in both directions, so both directions are tested."""

    def test_a_foreign_pyproject_is_ignored(self, tmp_path, monkeypatch):
        """A checkout nested inside an unrelated project must not read the neighbour's
        version. The guard is the `name = "squadops"` declaration, not the filename."""
        from squadops._version import resolve_version

        foreign = tmp_path / "pkg" / "squadops"
        foreign.mkdir(parents=True)
        (tmp_path / "pyproject.toml").write_text('name = "something-else"\nversion = "9.9.9"\n')

        monkeypatch.setattr("squadops._version.__file__", str(foreign / "_version.py"))
        # Falls through to metadata rather than reporting 9.9.9.
        assert resolve_version() != "9.9.9"

    def test_falls_back_to_metadata_with_no_source_tree(self, tmp_path, monkeypatch):
        """The installed-package case: no `pyproject.toml` anywhere above the package.

        This is the path a deployed container takes, and it must keep working — the
        fix must not trade a stale dev version for a broken production one.
        """
        from squadops._version import resolve_version

        installed = tmp_path / "site-packages" / "squadops"
        installed.mkdir(parents=True)
        monkeypatch.setattr("squadops._version.__file__", str(installed / "_version.py"))

        resolved = resolve_version()
        assert re.fullmatch(r"\d+\.\d+\.\d+", resolved), (
            f"metadata fallback returned {resolved!r}; a deployed image resolves its "
            "version this way and has no pyproject.toml to fall back to"
        )

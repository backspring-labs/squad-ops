"""#1976: the runs, artifacts and campaigns lists answer a page, 50 by default. A console view that
reads one with a bare fetch shows its first page as the whole list (and the flow metrics count
from it), so every view reads them through ``shared/paging.js``'s ``fetchAllPages``.

The scan reads a URL written at the fetch. One built into a variable first (``apiFetch(url)``) is
not seen: on main it found four of the five bare fetches this replaced, all but the cycle view's
artifact read.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGINS = Path(__file__).resolve().parents[3] / "console" / "continuum-plugins"

#: A bare fetch of a paged list: a URL ending in ``/runs``, ``/artifacts`` or
#: ``/api/v1/campaigns`` (before any query), handed straight to ``apiFetch`` or ``fetch``.
_BARE = re.compile(
    r"\b(?:apiFetch|fetch)\(\s*`[^`]*(?:/runs|/artifacts|/api/v1/campaigns)(?:\?[^`]*)?`"
)


def _bare_fetches(root: Path) -> list[str]:
    return [
        f"{path.relative_to(root)}:{source[: m.start()].count(chr(10)) + 1}"
        for path in sorted(root.glob("*/ui/src/**/*"))
        if path.suffix in (".svelte", ".js")
        for source in [path.read_text(encoding="utf-8")]
        for m in _BARE.finditer(source)
    ]


def test_no_view_reads_a_paged_list_with_a_bare_fetch():
    assert _bare_fetches(_PLUGINS) == []


def test_the_scan_finds_each_bare_form(tmp_path):
    src = tmp_path / "squadops.x" / "ui" / "src"
    src.mkdir(parents=True)
    (src / "View.svelte").write_text(
        "const a = await apiFetch(`${apiBase}/api/v1/projects/${p}/cycles/${c}/runs`);\n"
        "const b = await fetch(`${apiBase}/api/v1/projects/${p}/artifacts?artifact_type=x`);\n"
        "const c = await apiFetch(`${apiBase}/api/v1/campaigns`);\n"
        "const d = await apiFetch(`${apiBase}/api/v1/projects/${p}/cycles/${c}/runs/${r}`);\n"
        "const e = await fetchAllPages(apiFetch, `${apiBase}/api/v1/projects/${p}/artifacts`);\n",
        encoding="utf-8",
    )

    assert _bare_fetches(tmp_path) == [
        "squadops.x/ui/src/View.svelte:1",
        "squadops.x/ui/src/View.svelte:2",
        "squadops.x/ui/src/View.svelte:3",
    ]

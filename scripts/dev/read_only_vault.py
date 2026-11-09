"""The filesystem artifact vault, for a dev script that reads a deploy's vault and never writes it.

Two scripts read the Spark's vault from the host: the benchmark re-grade
(``regrade_benchmark.py``) and the pre-memory rejection baseline (``emit_rejection_baseline.py``).
Both need two things the adapter does not give an operator:
- **no write, ever.** Every index write is refused, so a read cannot rebuild or rewrite the
  deploy's index.
- **a readable index.** The containers write ``_index.json`` as root with mode 600, so the
  operator's ``retrieve`` raises ``PermissionError`` on every artifact (#1562). When the index
  cannot be read, it is rebuilt in memory from the ``metadata.json`` files the vault itself
  indexes, the same walk the adapter's ``_rebuild_index`` makes, and never written.

The listing summaries (#2973) are the same: a summary a listing finds behind is rebuilt from the
tree and kept in memory, never written. Each entry is checked against the metadata file it was read
from, so a summary kept in memory while the deploy writes the vault is never read stale.
"""

from __future__ import annotations

from pathlib import Path

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault


class ReadOnlyVault(FilesystemArtifactVault):
    """The filesystem vault with every index write refused, and every listing summary kept in
    memory."""

    _memory_index: dict[str, str] | None = None
    _memory_listings: dict[Path, dict] | None = None

    def _load_index(self) -> dict[str, str]:
        if self._memory_index is not None:
            return self._memory_index
        try:
            return super()._load_index()
        except PermissionError:
            self._memory_index = self._index_from_tree()
            return self._memory_index

    def _replace_unreadable_index(self, index: dict[str, str]) -> None:
        """An unreadable index (#2931) is rebuilt in memory too, and never written."""
        self._memory_index = index

    def _save_index(self, index: dict[str, str]) -> None:
        raise RuntimeError("a read-only vault never writes its index")

    def _load_listing_summary(self, group: Path) -> dict:
        if self._memory_listings is not None and group in self._memory_listings:
            return dict(self._memory_listings[group])
        return super()._load_listing_summary(group)

    def _save_listing_summary(self, group: Path, summary: dict) -> None:
        """A summary a listing rebuilt is kept in memory, and never written."""
        if self._memory_listings is None:
            self._memory_listings = {}
        self._memory_listings[group] = dict(summary)

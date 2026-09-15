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
"""

from __future__ import annotations

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault


class ReadOnlyVault(FilesystemArtifactVault):
    """The filesystem vault with every index write refused."""

    _memory_index: dict[str, str] | None = None

    def _load_index(self) -> dict[str, str]:
        try:
            return super()._load_index()
        except PermissionError:
            if self._memory_index is None:
                self._memory_index = {
                    meta.parent.name: str(meta.parent.relative_to(self._base_dir))
                    for meta in self._base_dir.rglob("metadata.json")
                }
            return self._memory_index

    def _save_index(self, index: dict[str, str]) -> None:
        raise RuntimeError("a read-only vault never writes its index")

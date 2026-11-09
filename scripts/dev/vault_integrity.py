#!/usr/bin/env python3
"""The artifact vault's integrity pass (#2931; the 2.7 plan, §4.6): every corrupt record under a
vault, counted and named, for the cut record. Read-only.

A record is corrupt when it exists but can't be read whole, by the same reading the vault uses
(``FilesystemArtifactVault``, whose module docstring is the write order this checks):

- ``metadata_unreadable``: an artifact's ``metadata.json`` doesn't parse, or doesn't hold an artifact;
- ``content_missing``: its metadata names a content file that isn't there;
- ``content_mismatch``: the content isn't the size or the hash its metadata records;
- ``content_without_metadata``: an artifact directory with no ``metadata.json``. A crash between the
  content's rename and the metadata's leaves one; it is no artifact, and is named so it can be read;
- ``stray_temp_files``: a ``*.tmp`` beside a record, a write that never reached its rename.

A directory's ``.listing.json`` (#2973) is the listing's cache of its artifacts' metadata, not a
record: the pass reads every record from its own metadata, and a listing rebuilds a summary that is
behind or doesn't parse. A stray temp file of one is named, as any write that never landed.

    python scripts/dev/vault_integrity.py [VAULT_DIR] [--under PROJECT[/CYCLE[/RUN]]]

VAULT_DIR is ``data/artifacts`` when not given. The output is JSON on stdout: each kind's count and
paths, relative to the vault. Exit 0 when nothing is corrupt, 1 when anything is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

#: Where a project's artifacts attached to no run live (the vault's layout).
UNATTACHED = "_unattached"

KINDS = (
    "metadata_unreadable",
    "content_missing",
    "content_mismatch",
    "content_without_metadata",
    "stray_temp_files",
)


def artifact_dirs(vault: Path) -> list[Path]:
    """Every artifact's directory, by its place in the vault's layout: ``<project>/<cycle>/<run>/<id>``
    and ``<project>/_unattached/<id>``. Not by a name prefix: ids are ``art_``, ``delta_``,
    ``term_`` and others."""
    dirs: list[Path] = []
    for project in (d for d in vault.iterdir() if d.is_dir()):
        for cycle in (d for d in project.iterdir() if d.is_dir()):
            if cycle.name == UNATTACHED:
                dirs.extend(d for d in cycle.iterdir() if d.is_dir())
                continue
            for run in (d for d in cycle.iterdir() if d.is_dir()):
                dirs.extend(d for d in run.iterdir() if d.is_dir())
    return sorted(dirs)


def check(vault: Path, under: str | None = None) -> dict[str, list[str]]:
    """Each kind of corrupt record under ``vault`` (or its ``under`` subtree), by relative path."""
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

    vault = vault.resolve()
    root = vault / under if under else vault
    found: dict[str, list[str]] = {kind: [] for kind in KINDS}
    if not root.exists():
        return found

    def rel(path: Path) -> str:
        return str(path.relative_to(vault))

    for tmp in sorted(root.rglob("*.tmp")):
        found["stray_temp_files"].append(rel(tmp))
    for directory in artifact_dirs(vault):
        if not directory.is_relative_to(root):
            continue
        meta = directory / "metadata.json"
        if not meta.exists():
            found["content_without_metadata"].append(rel(directory))
            continue
        try:
            ref = FilesystemArtifactVault._parse_metadata(meta.read_text())
        except (ValueError, TypeError, KeyError):
            found["metadata_unreadable"].append(rel(meta))
            continue
        content_path = directory / ref.filename
        if not content_path.is_file():
            found["content_missing"].append(rel(content_path))
            continue
        content = content_path.read_bytes()
        if (ref.size_bytes is not None and len(content) != ref.size_bytes) or (
            ref.content_hash and hashlib.sha256(content).hexdigest() != ref.content_hash
        ):
            found["content_mismatch"].append(rel(content_path))
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(usage=__doc__.split("\n\n")[2].strip())
    parser.add_argument("vault", nargs="?", default="data/artifacts")
    parser.add_argument("--under", default=None)
    args = parser.parse_args(argv)
    found = check(Path(args.vault), args.under)
    corrupt = sum(len(paths) for paths in found.values())
    print(
        json.dumps(
            {
                "vault": args.vault,
                "under": args.under,
                "corrupt": corrupt,
                **{kind: {"count": len(found[kind]), "paths": found[kind]} for kind in KINDS},
            },
            indent=2,
        )
    )
    return 1 if corrupt else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

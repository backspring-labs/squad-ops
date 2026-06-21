#!/usr/bin/env python3
"""Verify or regenerate the prompt-fragment manifest sha256 entries.

The manifest (``src/squadops/prompts/fragments/manifest.yaml``) records a
``sha256`` for each fragment's body. Editing a fragment without updating its
hash makes the runtime integrity check
(:meth:`FileSystemPromptRepository.validate_integrity`) and the unit tests
diverge, and a stale manifest lets the assembler raise ``HashMismatchError`` at
runtime — exactly the drift behind issue #195.

This is the single tool that keeps fragments and the manifest in sync:

    python scripts/dev/regen_fragment_manifest.py --check   # CI / pre-commit: exit 1 if stale
    python scripts/dev/regen_fragment_manifest.py --write   # recompute + update hashes in place

Hashing is delegated to ``FileSystemPromptRepository`` so this script, the
runtime, and the tests all agree on what a fragment's hash is.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from adapters.prompts.filesystem import FileSystemPromptRepository

FRAGMENTS_DIR = Path(__file__).resolve().parents[2] / "src" / "squadops" / "prompts" / "fragments"
MANIFEST_PATH = FRAGMENTS_DIR / "manifest.yaml"

_FILE_MISSING = "<file missing>"


def _entries() -> list[dict]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data.get("fragments", []) if data else []


def _drift() -> list[tuple[str, str, str, str]]:
    """Return ``(fragment_id, path, stored, computed)`` for each drifted entry."""
    out: list[tuple[str, str, str, str]] = []
    for entry in _entries():
        path = FRAGMENTS_DIR / entry["path"]
        if not path.exists():
            out.append((entry["fragment_id"], entry["path"], entry["sha256"], _FILE_MISSING))
            continue
        computed = FileSystemPromptRepository.hash_fragment_file(path)
        if computed != entry["sha256"]:
            out.append((entry["fragment_id"], entry["path"], entry["sha256"], computed))
    return out


def check() -> int:
    drift = _drift()
    total = len(_entries())
    if not drift:
        print(f"OK: all {total} fragment hashes match {MANIFEST_PATH.name}")
        return 0
    print(f"STALE: {len(drift)}/{total} fragment hash(es) out of date in {MANIFEST_PATH.name}:")
    for fid, path, stored, computed in drift:
        print(f"  - {fid} ({path})")
        print(f"      stored:   {stored}")
        print(f"      computed: {computed}")
    print("\nFix: python scripts/dev/regen_fragment_manifest.py --write")
    return 1


def write() -> int:
    drift = _drift()
    missing = [d for d in drift if d[3] == _FILE_MISSING]
    if missing:
        for fid, path, _stored, _computed in missing:
            print(f"ERROR: fragment file missing for {fid} ({path})", file=sys.stderr)
        return 1
    if not drift:
        print(f"OK: manifest already current ({len(_entries())} fragments)")
        return 0
    # Minimal edit: replace only the changed (globally unique) hash strings so
    # the diff is exactly the stale lines and all other formatting is preserved.
    raw = MANIFEST_PATH.read_text(encoding="utf-8")
    for fid, path, stored, computed in drift:
        raw = raw.replace(stored, computed)
        print(f"updated {fid} ({path})")
    MANIFEST_PATH.write_text(raw, encoding="utf-8")
    print(f"\nwrote {len(drift)} hash(es) to {MANIFEST_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="exit 1 if any hash is stale (default)")
    group.add_argument("--write", action="store_true", help="recompute and update hashes in place")
    args = parser.parse_args()
    return write() if args.write else check()


if __name__ == "__main__":
    raise SystemExit(main())

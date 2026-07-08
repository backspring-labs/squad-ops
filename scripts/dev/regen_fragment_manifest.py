#!/usr/bin/env python3
"""Verify or regenerate the prompt-fragment manifest sha256 entries.

The manifest (``src/squadops/prompts/fragments/manifest.yaml``) records a
``sha256`` for each fragment's body AND a top-level ``manifest_hash`` over
(version, fragments). Editing a fragment without updating its hash makes the
runtime integrity check
(:meth:`FileSystemPromptRepository.validate_integrity`) and the unit tests
diverge, and a stale manifest lets the assembler raise ``HashMismatchError`` at
runtime — exactly the drift behind issue #195. A stale ``manifest_hash`` is
the #327 drift: it now fails manifest loading hard instead of warning, so
this tool maintains it too (both ``--check`` and ``--write``).

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


def _manifest_hash_drift() -> tuple[str, str] | None:
    """Return ``(stored, computed)`` when the top-level manifest_hash is stale.

    Computed the same way the runtime does (PromptManifest.compute_manifest_hash
    over version + fragment entries), so this tool, the loader, and the tests
    can't disagree (#327).
    """
    from squadops.prompts.models import ManifestFragment, PromptManifest

    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    fragments = tuple(
        ManifestFragment(
            fragment_id=f["fragment_id"],
            path=f["path"],
            layer=f["layer"],
            roles=tuple(f.get("roles", ["*"])),
            sha256=f["sha256"],
        )
        for f in data.get("fragments", [])
    )
    stored = data.get("manifest_hash", "")
    computed = PromptManifest.compute_manifest_hash(data.get("version", "0.0.0"), fragments)
    return None if stored == computed else (stored, computed)


def check() -> int:
    drift = _drift()
    total = len(_entries())
    rc = 0
    if drift:
        print(f"STALE: {len(drift)}/{total} fragment hash(es) out of date in {MANIFEST_PATH.name}:")
        for fid, path, stored, computed in drift:
            print(f"  - {fid} ({path})")
            print(f"      stored:   {stored}")
            print(f"      computed: {computed}")
        rc = 1
    else:
        print(f"OK: all {total} fragment hashes match {MANIFEST_PATH.name}")
    hash_drift = _manifest_hash_drift()
    if hash_drift:
        stored, computed = hash_drift
        print(f"STALE: top-level manifest_hash out of date in {MANIFEST_PATH.name}:")
        print(f"      stored:   {stored}")
        print(f"      computed: {computed}")
        rc = 1
    else:
        print("OK: top-level manifest_hash matches")
    if rc:
        print("\nFix: python scripts/dev/regen_fragment_manifest.py --write")
    return rc


def write() -> int:
    drift = _drift()
    missing = [d for d in drift if d[3] == _FILE_MISSING]
    if missing:
        for fid, path, _stored, _computed in missing:
            print(f"ERROR: fragment file missing for {fid} ({path})", file=sys.stderr)
        return 1
    if drift:
        # Minimal edit: replace only the changed (globally unique) hash strings
        # so the diff is exactly the stale lines and all other formatting is
        # preserved.
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        for fid, path, stored, computed in drift:
            raw = raw.replace(stored, computed)
            print(f"updated {fid} ({path})")
        MANIFEST_PATH.write_text(raw, encoding="utf-8")
        print(f"wrote {len(drift)} fragment hash(es) to {MANIFEST_PATH}")
    hash_drift = _manifest_hash_drift()
    if hash_drift:
        stored, computed = hash_drift
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        if stored and stored in raw:
            raw = raw.replace(stored, computed)
        else:
            print(
                "ERROR: could not locate stored manifest_hash for in-place update", file=sys.stderr
            )
            return 1
        MANIFEST_PATH.write_text(raw, encoding="utf-8")
        print(f"updated manifest_hash -> {computed}")
    if not drift and not hash_drift:
        print(f"OK: manifest already current ({len(_entries())} fragments)")
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

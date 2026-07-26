#!/usr/bin/env python3
"""Materialize a walking skeleton from an interface manifest (SIP-0099 skeleton gate).

Loads an interface manifest, expands it via the scaffold expander, and writes every
``{name, content}`` file under ``out_dir``. The skeleton-gate CI job runs this and then
proves the expanded skeleton builds (``vite build``) and boots (``uvicorn``) on plain
runners — SIP-0099's own acceptance surface, and the gate SIP-0098 phase 98.2 emits its
contract checks into. Kept deliberately thin: expansion + chroot-safe writes only, no
build/boot logic (that is the CI job's shell steps, and later the sandbox's).

Usage:
    python scripts/dev/materialize_skeleton.py <manifest.yaml> <out_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold import materialize as materialize_skeleton


def materialize(manifest_path: Path, out_dir: Path) -> int:
    manifest = InterfaceManifest.from_yaml(manifest_path.read_text(encoding="utf-8"))
    count = materialize_skeleton(manifest, out_dir)
    print(
        f"materialized {count} files from {manifest_path} "
        f"(manifest_hash={manifest.content_hash()[:12]}) -> {out_dir.resolve()}"
    )
    return count


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    materialize(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

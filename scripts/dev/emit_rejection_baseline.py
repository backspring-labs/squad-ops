#!/usr/bin/env python3
"""Emit the pre-memory rejection baseline for one or more cycles (#809, B1).

Reads only durable, already-stored facts — rejection records, the manifest's authoring
provenance, and the cycle's framing run count — so a baseline can be produced at any time,
including retrospectively over cycles that ran before this script existed. **Nothing in 1.6
consumes the output.** It exists because the pre-memory picture becomes unrecoverable the
moment Cross-Cycle Memory is live, and this is the cheap moment to capture it.

Usage:
    .venv/bin/python scripts/dev/emit_rejection_baseline.py CYCLE_ID [CYCLE_ID ...] \
        [--project group_run] [--out baseline.json]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from adapters.cycles.filesystem_artifact_vault import FileSystemArtifactVault  # noqa: E402
from squadops.capabilities.scaffold import InterfaceManifest  # noqa: E402
from squadops.cycles.contract_derivation import is_interface_manifest  # noqa: E402
from squadops.cycles.rejection_baseline import (  # noqa: E402
    REJECTION_ARTIFACT_TYPE,
    build_baseline,
    render,
)


async def _cycle_baseline(vault, cycle_id: str):
    """One cycle's baseline, assembled from what the vault already holds."""
    import json

    artifacts = await vault.list_artifacts(cycle_id=cycle_id)

    rejection_records = []
    provenance = None
    run_ids = set()
    for ref in artifacts:
        if ref.run_id:
            run_ids.add(ref.run_id)
        try:
            _, content = await vault.retrieve(ref.artifact_id)
        except Exception:
            continue
        if ref.artifact_type == REJECTION_ARTIFACT_TYPE:
            try:
                rejection_records.append(json.loads(content.decode()))
            except Exception:
                continue
        elif is_interface_manifest(ref) and provenance is None:
            try:
                manifest = InterfaceManifest.from_yaml(content.decode(errors="replace"))
            except Exception:
                continue
            if manifest.provenance is not None:
                provenance = {
                    "attempts": manifest.provenance.attempts,
                    "revisions": [
                        {"attempt": r.attempt, "classes": r.classes}
                        for r in manifest.provenance.revisions
                    ],
                }

    # Framing re-rolls: the sequence creates one extra framing run per re-roll, so counting
    # the runs that produced a manifest or a rejection is the record. Conservative floor of 1
    # — a cycle always had at least one framing run to reject anything at all.
    return build_baseline(
        cycle_id,
        rejection_records=rejection_records,
        manifest_provenance=provenance,
        framing_run_count=max(1, len(run_ids)),
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle_ids", nargs="+")
    parser.add_argument("--project", default="group_run")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    vault = FileSystemArtifactVault(base_dir=str(REPO_ROOT / "data" / "artifacts"))
    baselines = [await _cycle_baseline(vault, c) for c in args.cycle_ids]
    output = render(baselines)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"wrote {args.out} ({len(baselines)} cycle(s))")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

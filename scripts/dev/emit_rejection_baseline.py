#!/usr/bin/env python3
"""Emit the pre-memory rejection baseline for one or more cycles (#809, B1).

Reads only durable, already-stored facts — rejection records, the manifest's authoring
provenance, and the cycle's framing run count — so a baseline can be produced at any time,
including retrospectively over cycles that ran before this script existed. **Nothing in 1.6
consumes the output.** It exists because the pre-memory picture becomes unrecoverable the
moment Cross-Cycle Memory is live, and this is the cheap moment to capture it.

**A baseline that cannot read its inputs refuses** (#1562). Every read failure used to be
skipped, so a vault whose index the operator cannot read (the containers write it as root)
emitted zero classes for every cycle: a hollow capture that looks like evidence. A rejection
record or manifest that cannot be read or parsed now stops the emission, naming the artifact.

Usage:
    .venv/bin/python scripts/dev/emit_rejection_baseline.py CYCLE_ID [CYCLE_ID ...] \
        --vault data/artifacts [--project group_run] [--out baseline.json]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault  # noqa: E402
from squadops.capabilities.scaffold import InterfaceManifest  # noqa: E402
from squadops.cycles.contract_derivation import is_interface_manifest  # noqa: E402
from squadops.cycles.rejection_baseline import (  # noqa: E402
    REJECTION_ARTIFACT_TYPE,
    build_baseline,
    render,
)


class BaselineInputUnreadable(RuntimeError):
    """A stored input the baseline needs could not be read; the emission stops."""


async def _content(vault, ref) -> str:
    try:
        _, content = await vault.retrieve(ref.artifact_id)
        return content.decode()
    except Exception as exc:
        raise BaselineInputUnreadable(
            f"{ref.cycle_id}: {ref.artifact_type} {ref.artifact_id} could not be read"
            f" ({type(exc).__name__}: {exc})"
        ) from exc


async def _cycle_baseline(vault, cycle_id: str, *, project_id: str):
    """One cycle's baseline, assembled from what the vault already holds."""
    import json

    artifacts = await vault.list_artifacts(project_id=project_id, cycle_id=cycle_id)

    rejection_records = []
    provenance = None
    framing_runs = set()
    for ref in artifacts:
        if ref.artifact_type == REJECTION_ARTIFACT_TYPE:
            text = await _content(vault, ref)
            try:
                rejection_records.append(json.loads(text))
            except ValueError as exc:
                raise BaselineInputUnreadable(
                    f"{cycle_id}: rejection record {ref.artifact_id} is not JSON ({exc})"
                ) from exc
        elif is_interface_manifest(ref):
            text = await _content(vault, ref)
            try:
                manifest = InterfaceManifest.from_yaml(text)
            except Exception as exc:
                raise BaselineInputUnreadable(
                    f"{cycle_id}: manifest {ref.artifact_id} does not parse ({exc})"
                ) from exc
            if manifest.provenance is not None and provenance is None:
                provenance = {
                    "attempts": manifest.provenance.attempts,
                    "revisions": [
                        {"attempt": r.attempt, "classes": r.classes}
                        for r in manifest.provenance.revisions
                    ],
                }
        else:
            continue
        if ref.run_id:
            framing_runs.add(ref.run_id)

    # Framing re-rolls: the sequence creates one extra framing run per re-roll, and a framing
    # run is the one that stores the manifest or the rejection record. Counting every run that
    # stored anything also counted the implementation run, so a cycle with no re-roll read one
    # (#1562). A framing run that stored neither is not counted; the cycle assessment's
    # `framing_rerolls`, read from the registry's runs, is the count that sees it. Floor of 1
    # — a cycle always had at least one framing run to reject anything at all.
    return build_baseline(
        cycle_id,
        rejection_records=rejection_records,
        manifest_provenance=provenance,
        framing_run_count=max(1, len(framing_runs)),
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle_ids", nargs="+")
    parser.add_argument("--vault", required=True, type=Path, help="the artifact vault directory")
    parser.add_argument("--project", default="group_run")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    vault = FilesystemArtifactVault(base_dir=str(args.vault))
    try:
        baselines = [
            await _cycle_baseline(vault, c, project_id=args.project) for c in args.cycle_ids
        ]
    except BaselineInputUnreadable as exc:
        raise SystemExit(f"refusing to emit a baseline over an unread input: {exc}") from exc
    output = render(baselines)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"wrote {args.out} ({len(baselines)} cycle(s))")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

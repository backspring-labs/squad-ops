#!/usr/bin/env python3
"""The Autonomous Work Envelope: AOR per declared work class, read from the campaigns' packages
(SIP-0113 §4.6; #2418).

Reads each campaign's latest evidence package from the deploy's vault and prints, per work class,
how many of its closed campaigns were reliable, not, or unread, and for each unread campaign which
of AOR's four inputs couldn't be read. A class has a rate only once every campaign in it is read;
no composite is formed across classes. Reporting-only, and it writes nothing.

    python scripts/dev/aor_reading.py [--vault data/artifacts] [--campaign cmp_… …]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from squadops.outcomes.aor import ClassReading, work_envelope

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = "campaign_evidence"


def latest_packages(vault: Path, campaigns: Iterable[str] = ()) -> list[dict]:
    """Each campaign's latest stored package (by its artifact's ``created_at``), optionally only
    those named."""
    wanted = set(campaigns)
    latest: dict[str, tuple[str, Path]] = {}
    for meta in vault.glob("*/**/metadata.json"):
        try:
            ref = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        extra = ref.get("metadata") or {}
        if ref.get("artifact_type") != EVIDENCE or extra.get("part") != "package":
            continue
        cid = extra.get("campaign_id")
        if not cid or (wanted and cid not in wanted):
            continue
        stamp = ref.get("created_at") or ""
        if cid not in latest or stamp > latest[cid][0]:
            latest[cid] = (stamp, meta.parent / ref["filename"])
    return [json.loads(path.read_text()) for _, path in sorted(latest.values(), key=lambda v: v[0])]


def render(readings: Iterable[ClassReading]) -> str:
    lines = [
        "| work class | campaigns | reliable | not | unread | AOR |",
        "|---|---|---|---|---|---|",
    ]
    unread: list[str] = []
    for r in readings:
        named = ", ".join(str(x) for x in r.work_class) if r.work_class else "none declared"
        rate = f"{r.rate:.2f}" if r.rate is not None else "not yet read"
        lines.append(
            f"| {named} | {len(r.campaigns)} | {len(r.reliable)} | {len(r.not_reliable)} | "
            f"{len(r.unread)} | {rate} |"
        )
        unread += [f"- `{cid}` ({named}): {', '.join(inputs)}" for cid, inputs in r.unread]
    if unread:
        lines += ["", "Unread, by the inputs that kept each from being read:", *unread]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--vault", type=Path, default=main_checkout(REPO) / "data/artifacts")
    ap.add_argument("--campaign", action="append", default=[], help="read only these campaigns")
    args = ap.parse_args(argv)
    packages = latest_packages(args.vault, args.campaign)
    if not packages:
        print(f"no campaign package under {args.vault}", file=sys.stderr)
        return 1
    print(render(work_envelope(packages)), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

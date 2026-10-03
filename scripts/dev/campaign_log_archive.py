#!/usr/bin/env python3
"""Archive a campaign's container logs per cycle, before a rebuild destroys them (#1710).

The squad's logs hold what the readouts read: emission shapes, suite lines, typed checks, the
corrections' briefs and authorizations. ``docker logs`` keeps them only until the container is
recreated, and a framework fix between campaigns recreates every one. This is the triage tier of
the owner's two tiers (#1710, 2026-09-28): kept on the Spark, read through the CLI and the files,
until the frontier triage and any fix loop are done.

For each cycle the campaign launched, every container's log window (the cycle's first run start
to its last run end, with a margin either side) is written to
``var/campaigns/<campaign>/logs/<cycle>/<container>.log``. A ``manifest.json`` beside them records
each file's window, size and sha256. A cycle whose runs have all ended is archived once; one still
running is re-archived on each pass, so ``--follow`` keeps the latest window.

Reads only: Postgres through ``docker exec … psql`` (read-only queries) and ``docker logs``.

Usage::

    python scripts/dev/campaign_log_archive.py <campaign_id>            # one pass
    python scripts/dev/campaign_log_archive.py <campaign_id> --follow   # until the campaign closes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402

#: The archive is written under the main checkout whichever checkout runs this, as the set
#: driver's records are (1.8.2 plan §3.2 item 8): a worktree's ``var/`` looks disposable.
REPO = main_checkout(Path(__file__).resolve().parents[2])
CONTAINERS = (
    "squadops-runtime-api",
    "squadops-max",
    "squadops-neo",
    "squadops-nat",
    "squadops-bob",
    "squadops-eve",
    "squadops-data",
)
#: Before a cycle's first run and after its last: a dispatch logged a moment before the run's
#: start stamp, and a reply logged after its end, are the cycle's lines too.
MARGIN = timedelta(minutes=2)
_TERMINAL_RUN = {"completed", "failed", "cancelled"}


@dataclass(frozen=True)
class CycleWindow:
    cycle_id: str
    since: datetime
    until: datetime | None  # None while a run is still going: read to now
    ended: bool


def cycle_window(
    cycle_id: str, runs: Sequence[tuple[str, datetime | None, datetime | None]]
) -> CycleWindow | None:
    """The cycle's log window from its runs (status, started_at, finished_at), or None before any
    run has started. Ended only when every run has a terminal status and a finish time."""
    started = [s for _st, s, _f in runs if s is not None]
    if not started:
        return None
    ended = all(st in _TERMINAL_RUN and f is not None for st, _s, f in runs)
    finished = [f for _st, _s, f in runs if f is not None]
    until = max(finished) + MARGIN if ended and finished else None
    return CycleWindow(cycle_id, min(started) - MARGIN, until, ended)


def already_archived(manifest: dict | None, window: CycleWindow) -> bool:
    """An ended cycle whose manifest records the same ended window is not archived again."""
    return bool(
        manifest
        and manifest.get("ended")
        and window.ended
        and manifest.get("since") == window.since.isoformat()
        and manifest.get("until") == (window.until.isoformat() if window.until else None)
    )


def _psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        [
            "docker",
            "exec",
            "squadops-postgres",
            "psql",
            "-U",
            "squadops",
            "-d",
            "squadops",
            "-At",
            "-F",
            "\t",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def _ts(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _campaign(campaign_id: str) -> tuple[str, list[str]]:
    """The campaign's state and its launched cycles, oldest first."""
    if not campaign_id.replace("_", "").isalnum():
        raise SystemExit(f"not a campaign id: {campaign_id!r}")
    [[state]] = _psql(f"select state from campaigns where campaign_id = '{campaign_id}'")
    cycles = [
        r[0]
        for r in _psql(
            "select cycle_id from campaign_launch_intents where campaign_id = "
            f"'{campaign_id}' and cycle_id is not null order by created_at"
        )
    ]
    return state, cycles


def _runs(cycle_id: str) -> list[tuple[str, datetime | None, datetime | None]]:
    return [
        (st, _ts(s), _ts(f))
        for st, s, f in _psql(
            "select status, coalesce(started_at::text, ''), coalesce(finished_at::text, '') "
            f"from cycle_runs where cycle_id = '{cycle_id}' order by run_number"
        )
    ]


def _docker_logs(container: str, since: datetime, until: datetime | None) -> bytes:
    cmd = ["docker", "logs", "--since", since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")]
    if until is not None:
        cmd += ["--until", until.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")]
    done = subprocess.run([*cmd, container], capture_output=True)
    return done.stdout + done.stderr


def _created(container: str) -> datetime | None:
    done = subprocess.run(
        ["docker", "inspect", "-f", "{{.Created}}", container], capture_output=True, text=True
    )
    value = done.stdout.strip()
    if done.returncode != 0 or not value:
        return None
    # Docker reports nanoseconds; datetime keeps microseconds.
    head, _, frac = value.rstrip("Z").partition(".")
    return datetime.fromisoformat(f"{head}.{frac[:6] or '0'}+00:00")


def archive_cycle(
    root: Path,
    window: CycleWindow,
    read_logs: Callable[[str, datetime, datetime | None], bytes],
    created: Callable[[str], datetime | None] = _created,
) -> dict:
    """Write each container's window and the manifest; return the manifest.

    A container recreated after the window opened (a rebuild) no longer holds its lines. Its
    file is still written, and the manifest says so (``lost``), so an empty file never reads as
    a quiet cycle."""
    folder = root / window.cycle_id
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for container in CONTAINERS:
        data = read_logs(container, window.since, window.until)
        (folder / f"{container}.log").write_bytes(data)
        born = created(container)
        files[container] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "container_created": born.isoformat() if born else None,
            # Lost when the container is newer than the cycle's first run start: a container
            # recreated inside the margin, before anything ran, lost nothing.
            "lost": born is not None and born > window.since + MARGIN,
        }
    manifest = {
        "cycle_id": window.cycle_id,
        "since": window.since.isoformat(),
        "until": window.until.isoformat() if window.until else None,
        "ended": window.ended,
        "archived_at": datetime.now(UTC).isoformat(),
        "lost": sorted(c for c, f in files.items() if f["lost"]),
        "files": files,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def one_pass(campaign_id: str) -> str:
    root = REPO / "var" / "campaigns" / campaign_id / "logs"
    state, cycles = _campaign(campaign_id)
    for cycle_id in cycles:
        window = cycle_window(cycle_id, _runs(cycle_id))
        if window is None:
            continue
        manifest_path = root / cycle_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        if already_archived(manifest, window):
            continue
        written = archive_cycle(root, window, _docker_logs)
        total = sum(f["bytes"] for f in written["files"].values())
        lost = f"; LOST (recreated since): {', '.join(written['lost'])}" if written["lost"] else ""
        print(
            f"{cycle_id}: {total} bytes over {len(written['files'])} containers"
            f"{'' if window.ended else ' (running)'}{lost}",
            flush=True,
        )
    return state


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("campaign_id")
    parser.add_argument("--follow", action="store_true", help="repeat until the campaign closes")
    parser.add_argument("--interval", type=int, default=300, help="seconds between passes")
    args = parser.parse_args(argv)
    while True:
        state = one_pass(args.campaign_id)
        if not args.follow or state == "completed":
            if args.follow:
                one_pass(args.campaign_id)  # the closing cycle's final window
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())

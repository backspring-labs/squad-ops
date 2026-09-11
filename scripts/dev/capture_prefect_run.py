#!/usr/bin/env python3
"""Photograph a cycle's Prefect flow run for a release package's ``assets/``.

The companion to ``capture_delivered_app.py``: that one shows WHAT the squad delivered, this
one shows HOW it got there. The flow-run timeline is the only view in the stack where a
correction round is legible at a glance — a red ``qa.test`` bar, then
``data.analyze_failure`` → ``governance.correction_decision`` → a repair task, then the
re-take. A record's ``correction_rounds: 2`` says the same thing and shows none of it.

Cut step 7 names "Prefect run" among the screenshots a release package should carry, and
v1.7.0–v1.7.4 all shipped with an empty ``assets/``. See ``capture_delivered_app.py`` for why
that makes this a command rather than a checklist line.

    python scripts/dev/capture_prefect_run.py --cycle cyc_89153929 --version 1.7.5 \\
        --label prefect-flow-run-with-two-correction-rounds

**It refuses a run that is still going.** A timeline captured mid-flight shows a blue RUNNING
bar and a half-drawn story, and pasted into a release page it reads as the finished article —
the #1076 shape, where a capture that could not have been complete looked authoritative.
Pass ``--allow-running`` only to look at something live.

**Keep the chrome.** The left nav and the header are deliberately IN the capture, not cropped
out (owner, 2026-09-11): the Prefect logo and nav attribute the screenshot to the tool that
produced it, and the header carries the flow-run name with its cycle and run ids, the state,
the duration and the task count. A bare timeline is prettier and says nothing about where it
came from — on a release page that is a picture with no provenance.

Prefect here is **2.14.21**, whose flow-run route is ``/flow-runs/flow-run/<id>`` — Prefect 3's
``/runs/flow-run/<id>`` renders the SPA's 404 page, and because the SPA answers 200 for every
path, a wrong route cannot be detected by status code. The tab strip below the timeline is not
URL-addressable in this version, so the capture is the timeline and the header, cropped by
window height.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASES = REPO / "site/content/releases"
PREFECT = "http://localhost:4200"
#: Tall enough for the header and the whole timeline, short enough to crop the log pane off.
DEFAULT_HEIGHT = 520
#: Prefect's own ceiling: anything larger is refused with 422 "Invalid limit: must be less
#: than or equal to 200", which arrives as an HTTPError rather than an empty result.
PAGE = 200


def api(path: str, body: dict | None = None):
    if body is None:
        return json.load(urllib.request.urlopen(f"{PREFECT}/api{path}", timeout=30))
    req = urllib.request.Request(
        f"{PREFECT}/api{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=30))


def resolve(cycle: str) -> dict:
    """The cycle's IMPLEMENTATION flow run, by name.

    Flow runs are named ``<project>/<cycle prefix>/<run prefix>``, and a cycle has two — the
    framing run then the implementation run. The later one is the one with the build in it,
    and it is the only one that can show a correction round.
    """
    short = cycle[:12]
    runs = [
        r
        for r in api("/flow_runs/filter", {"limit": PAGE, "sort": "START_TIME_DESC"})
        if short in (r.get("name") or "")
    ]
    if not runs:
        raise SystemExit(f"no Prefect flow run whose name carries {short}")
    return sorted(runs, key=lambda r: r.get("start_time") or "")[-1]


def repair_tasks(flow_run_id: str) -> list[str]:
    rows = api(
        "/task_runs/filter",
        {
            "flow_runs": {"id": {"any_": [flow_run_id]}},
            "limit": PAGE,
            "sort": "EXPECTED_START_TIME_ASC",
        },
    )
    return [
        f"{(t.get('state') or {}).get('type', '?'):10} {t['name']}"
        for t in rows
        if any(k in t["name"] for k in ("repair", "retest", "correction"))
    ]


def shoot(flow_run_id: str, dest: Path, width: int, height: int) -> None:
    # Snap-confined chromium cannot write to /tmp/claude-* or to dot-directories: permission
    # denied, no file, and no message on stdout. Stage in a plain $HOME directory and move.
    staging = Path.home() / "squadops-capture-staging"
    staging.mkdir(exist_ok=True)
    try:
        tmp = staging / dest.name
        subprocess.run(
            [
                "chromium",
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                f"--window-size={width},{height}",
                "--virtual-time-budget=30000",
                f"--screenshot={tmp}",
                f"{PREFECT}/flow-runs/flow-run/{flow_run_id}",
            ],
            capture_output=True,
            text=True,
        )
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise SystemExit("chromium wrote no file — snap confinement, or Prefect is down")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--cycle", help="cycle id; resolves to its implementation flow run")
    src.add_argument("--flow-run", help="a Prefect flow run uuid, taken straight from the UI url")
    p.add_argument("--version", required=True, help="e.g. 1.7.5")
    p.add_argument(
        "--label",
        default="prefect-flow-run",
        help="filename stem; build_release_package.py turns it into the caption",
    )
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    p.add_argument(
        "--allow-running",
        action="store_true",
        help="capture a run that has not finished (shows a blue RUNNING bar)",
    )
    args = p.parse_args()

    run = resolve(args.cycle) if args.cycle else api(f"/flow_runs/{args.flow_run}")
    state = (run.get("state") or {}).get("type", "?")
    print(f"{run.get('name')}  state={state}  id={run['id']}")

    if state == "RUNNING" and not args.allow_running:
        raise SystemExit(
            "REFUSING: the run is still going, and a half-drawn timeline in a release package "
            "reads as the finished article. Wait for it, or pass --allow-running to look."
        )

    tasks = repair_tasks(run["id"])
    if tasks:
        print(f"  {len(tasks)} correction task(s) the timeline will show:")
        for line in tasks:
            print(f"    {line}")
    else:
        print("  no correction tasks — a clean run's timeline shows no repair to look at")

    dest = RELEASES / f"v{args.version}" / "assets" / f"{args.label}.png"
    shoot(run["id"], dest, args.width, args.height)
    print(f"\n  {dest.relative_to(REPO)} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read every view of a project's Campaign cycles, and say where they disagree.

The 2.8.1 cut record (§2.1) read each Roblox cycle four ways by hand: the cycle route,
``squadops cycles show``, the Campaign's ledger, and the control log's ending row. 26 of 28
agreed, and the two that didn't are #3244. This is that read as a command, with the fifth view
#3224 adds: the status-filtered list.

    python scripts/dev/read_cycle_views.py <project-id> [--json]

For each cycle a Campaign launched it prints:

- **the route:** its ``status``, the ending it names (``recorded_ending``) and any
  ``status_conflict``. ``squadops cycles show`` prints this same answer, so it is one view here;
- **the list:** whether ``cycles?status=<that status>`` returns the cycle;
- **the ledger:** the ending and verdict the Campaign's proposal ledger gives the cycle;
- **the control log:** the ending and row of the ``decide`` entry that names the cycle.

A cycle **disagrees** when:

- the list filtered by the route's own status doesn't return it (#3224);
- the ledger and the control log both name an ending for it, and they differ;
- it ended, and the route names no ending (#3244). A cycle ended when its Campaign's control
  log names an ending for it, or when its last run's status is the cycle's own terminal status.

A view that says nothing of a cycle doesn't disagree with one that does: the ledger has a row
only where a proposal was submitted, and an aborted Campaign's log names no ending for the
cycle it was running. One case is printed as a note and counts as agreeing: a cycle cancelled
while none of its runs was cancelled. That cancel is the cycle's own, and no record names an
ending for it.

It reads, and writes nothing. Exit 0 when every cycle agrees, 1 when one doesn't, and 2 when
a read fails or the project has no Campaign cycle, since reading nothing isn't agreement.

It talks to the runtime API with the CLI's own client and token (``squadops login`` first).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

Get = Callable[..., Any]

#: A page's size, the API's largest (``squadops.api.paging.MAX_LIMIT``). A full page means
#: there may be more, so the next is asked for.
PAGE = 500
#: The statuses a cycle doesn't leave.
TERMINAL = frozenset({"completed", "failed", "cancelled"})


@dataclass
class CycleViews:
    """One cycle, as each view reads it."""

    cycle_id: str
    campaign_id: str
    route_status: str | None = None
    route_ending: str | None = None
    route_conflict: str | None = None
    listed_under_status: bool | None = None
    ledger_ending: str | None = None
    ledger_verdict: str | None = None
    log_ending: str | None = None
    log_row: int | None = None
    last_run_status: str | None = None
    disagreements: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def every_page(get: Get, path: str, **params: Any) -> list[dict]:
    """Every item of a paged list route, asked a page at a time until one comes back short."""
    items: list[dict] = []
    while True:
        page = get(path, params={**params, "limit": PAGE, "offset": len(items)})
        items.extend(page)
        if len(page) < PAGE:
            return items


def campaign_cycles(get: Get, campaign_id: str) -> dict[str, CycleViews]:
    """Each cycle the Campaign launched, with what its ledger and control log say of it."""
    views: dict[str, CycleViews] = {}

    def view(cycle_id: str) -> CycleViews:
        return views.setdefault(cycle_id, CycleViews(cycle_id, campaign_id))

    for row in get(f"/api/v1/campaigns/{campaign_id}/ledger"):
        for cycle in row.get("cycles") or []:
            seen = view(cycle["cycle_id"])
            seen.ledger_ending = cycle.get("ending")
            seen.ledger_verdict = cycle.get("verdict")
    for entry in get(f"/api/v1/campaigns/{campaign_id}/control-log"):
        binding = entry.get("binding") or {}
        # Every cycle the Campaign launched is read, whether or not a proposal or a decision
        # followed: an abort mid-run leaves a cycle neither the ledger nor a decision names.
        if entry.get("operation") == "mark_launched" and binding.get("cycle_id"):
            view(binding["cycle_id"])
        # A decision is logged twice for a cycle: the row that claims it, and the row that
        # decides. The deciding row is the one that names an ending.
        if entry.get("operation") == "decide" and binding.get("cycle_id") and "ending" in binding:
            seen = view(binding["cycle_id"])
            seen.log_ending = binding.get("ending")
            seen.log_row = binding.get("row")
    return views


def read_project(get: Get, project_id: str) -> list[CycleViews]:
    """Every Campaign cycle of the project, read every way, with its disagreements named."""
    views: dict[str, CycleViews] = {}
    for campaign in every_page(get, "/api/v1/campaigns", project_id=project_id):
        views.update(campaign_cycles(get, campaign["campaign_id"]))

    listed: dict[str, set[str]] = {}
    for seen in views.values():
        route = get(f"/api/v1/projects/{project_id}/cycles/{seen.cycle_id}")
        seen.route_status = route.get("status")
        seen.route_ending = route.get("recorded_ending")
        seen.route_conflict = route.get("status_conflict")
        runs = sorted(route.get("runs") or [], key=lambda run: run.get("run_number") or 0)
        seen.last_run_status = runs[-1].get("status") if runs else None
        status = seen.route_status or ""
        if status not in listed:
            under = every_page(get, f"/api/v1/projects/{project_id}/cycles", status=status)
            listed[status] = {c["cycle_id"] for c in under}
        seen.listed_under_status = seen.cycle_id in listed[status]
        seen.disagreements = disagreements(seen)
        seen.notes = notes(seen)
    return sorted(views.values(), key=lambda v: (v.campaign_id, v.cycle_id))


def disagreements(seen: CycleViews) -> list[str]:
    """Where the views of one cycle differ, each in a sentence. ``[]`` when they agree."""
    found = []
    if not seen.listed_under_status:
        found.append(f"the list filtered by status {seen.route_status} doesn't return it")
    if seen.ledger_ending and seen.log_ending and seen.ledger_ending != seen.log_ending:
        found.append(
            f"the ledger says {seen.ledger_ending} and the control log says {seen.log_ending}"
        )
    if seen.route_ending is None and seen.route_status in TERMINAL:
        if seen.log_ending:
            found.append(
                f"the control log says it ended ({seen.log_ending}) and the route names no ending"
            )
        elif seen.last_run_status == seen.route_status:
            found.append(f"its last run ended {seen.last_run_status} and the route names no ending")
    return found


def notes(seen: CycleViews) -> list[str]:
    """What a reader should know of a cycle that agrees: a named case, never a disagreement."""
    if (
        seen.route_status == "cancelled"
        and seen.route_ending is None
        and seen.last_run_status != "cancelled"
        and not seen.log_ending
    ):
        return [
            f"cancelled with its last run {seen.last_run_status}: the cycle's own cancel, "
            "which records no ending"
        ]
    return []


def render(views: list[CycleViews]) -> str:
    lines = []
    for seen in views:
        lines.append(
            f"{seen.cycle_id}  {seen.campaign_id}  route: {seen.route_status}"
            f"/{seen.route_ending or '-'}"
            f"{' (' + seen.route_conflict + ')' if seen.route_conflict else ''}  "
            f"listed: {'yes' if seen.listed_under_status else 'NO'}  "
            f"ledger: {seen.ledger_ending or '-'}/{seen.ledger_verdict or '-'}  "
            f"log: {seen.log_ending or '-'} (row {seen.log_row})"
        )
        lines.extend(f"    DISAGREES: {why}" for why in seen.disagreements)
        lines.extend(f"    note: {what}" for what in seen.notes)
    agreeing = sum(1 for seen in views if not seen.disagreements)
    lines.append(f"{agreeing} of {len(views)} cycles agree in every view")
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, get: Get | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("project_id")
    parser.add_argument("--json", action="store_true", help="print the views as JSON")
    args = parser.parse_args(argv)
    if get is None:
        from squadops.cli.client import get_client

        get = get_client().get
    try:
        views = read_project(get, args.project_id)
    except Exception as e:  # noqa: BLE001 - a read that fails is the answer, named
        print(f"read_cycle_views: a read failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if not views:
        print(
            f"read_cycle_views: project {args.project_id} has no Campaign cycle to read: "
            "check the project id and the deploy",
            file=sys.stderr,
        )
        return 2
    print(json.dumps([asdict(v) for v in views], indent=2) if args.json else render(views))
    return 0 if all(not v.disagreements for v in views) else 1


if __name__ == "__main__":
    sys.exit(main())

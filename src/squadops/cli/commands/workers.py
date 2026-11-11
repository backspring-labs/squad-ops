"""``squadops workers``: the worker registry, as an operator reads it (#3047).

``list`` shows each live session: its health (``offline`` once it has gone silent), when it was
last heard from, and what it serves and holds. ``show`` is one worker's session with its held
operation and its recent refused results. Both read ``GET /api/v1/workers``, which needs
``workers:read``.
"""

from __future__ import annotations

import typer

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_detail, print_error, print_json, print_table

app = typer.Typer(name="workers", help="The remote-execution workers: list them, show one")


def _call(ctx: typer.Context, path: str):
    try:
        client = _get_client(ctx)
        data = client.get(path)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    return data


def _fmt(ctx: typer.Context) -> tuple[bool, bool]:
    obj = ctx.obj or {}
    return obj.get("format") == "json", bool(obj.get("quiet", False))


def _served(worker: dict) -> str:
    return ", ".join(f"{o['provider']}/{o['operation']}" for o in worker["operations"]) or "-"


def _holding(worker: dict) -> str:
    held = [
        f"{h['operation_id']} (attempt {h['attempt']} of {h['max_attempts']}"
        + (", asked to stop" if h["cancel_requested"] else "")
        + ")"
        for h in worker["held"]
    ]
    return ", ".join(held) or "-"


@app.command("list")
def list_workers(ctx: typer.Context):
    """Every live worker session: its health, last heartbeat, what it serves and holds."""
    data = _call(ctx, "/api/v1/workers")
    as_json, quiet = _fmt(ctx)
    if as_json:
        print_json(data)
        return
    print_table(
        ["Worker", "Health", "Last heartbeat", "Serves", "Holding", "Refused lately"],
        [
            [
                w["worker_id"],
                w["health"],
                w["last_heartbeat_at"],
                _served(w),
                _holding(w),
                str(len(w["recent_refusals"])),
            ]
            for w in data
        ],
        quiet=quiet,
        title="Workers",
    )


@app.command("show")
def show_worker(ctx: typer.Context, worker_id: str = typer.Argument(..., help="The worker's id")):
    """One worker's live session, its held operation and its recent refused results."""
    data = _call(ctx, f"/api/v1/workers/{worker_id}")
    as_json, quiet = _fmt(ctx)
    if as_json:
        print_json(data)
        return
    reported = (
        f" (last reported {data['reported_status']})"
        if data["reported_status"] != data["health"]
        else ""
    )
    print_detail(
        {
            "worker": data["worker_id"],
            "session": data["session_id"],
            "platform": data["platform"],
            "health": data["health"] + reported,
            "registered": data["registered_at"],
            "last heartbeat": data["last_heartbeat_at"],
            "serves": _served(data),
            "tool versions": ", ".join(f"{k} {v}" for k, v in data["tool_versions"].items()) or "-",
            "holding": _holding(data),
        },
        quiet=quiet,
    )
    if data["recent_refusals"]:
        print_table(
            ["Operation", "Attempt", "Session", "Refusal", "Received"],
            [
                [
                    r["operation_id"],
                    str(r["attempt"]),
                    r["session_id"],
                    r["refusal"],
                    r["received_at"],
                ]
                for r in data["recent_refusals"]
            ],
            quiet=quiet,
            title="Refused results, newest first",
        )

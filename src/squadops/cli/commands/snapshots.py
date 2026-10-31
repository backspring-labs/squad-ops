"""``squadops snapshots``: a unit's snapshot as it binds now, and its re-binding (SIP-0110 Appendix A
§3.7; #2179).

A standalone cycle or a campaign pins its project instructions when it is admitted, and keeps them
while it runs. ``show`` reads what it binds, with every re-binding since. ``rebind`` replaces a
bound instruction's revision with the record's current one, or removes it when the record is
withdrawn: an intervention, which needs ``memory:instruct`` and the unit's authority, and sets the
unit's measurements apart.
"""

from __future__ import annotations

import typer

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_error, print_json, print_success

app = typer.Typer(name="snapshots", help="A unit's pinned snapshot: show it, re-bind it")

_KIND = typer.Argument(..., help="cycle (a standalone cycle) or campaign")


def _call(ctx: typer.Context, method: str, path: str, **kwargs):
    try:
        client = _get_client(ctx)
        data = getattr(client, method)(path, **kwargs)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    return data


def _json(ctx: typer.Context) -> bool:
    return bool(ctx.obj and ctx.obj.get("format") == "json")


def _bound(data: dict) -> None:
    for i in data["instructions"]:
        print_success(f"binds {i['record_id']} revision {i['revision']}")
    if data["instructions_unread"]:
        print_success(f"its instructions are unknown: {data['instructions_unread']}")
    for r in data["rebindings"]:
        to = (
            f"revision {r['replacement']['revision']}"
            if r["replacement"]
            else "nothing (withdrawn)"
        )
        print_success(
            f"re-bound {r['record_id']} from revision {r['replaced']['revision']} to {to}, "
            f"by {r['by']} at {r['at']}: {r['why']}"
        )


@app.command("show")
def show(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    unit_kind: str = _KIND,
    unit_id: str = typer.Argument(...),
):
    """What the unit binds now, and every re-binding since its admission."""
    data = _call(ctx, "get", f"/api/v1/projects/{project_id}/snapshots/{unit_kind}/{unit_id}")
    if _json(ctx):
        print_json(data)
        return
    print_success(f"{data['unit_kind']} {data['unit_id']}: snapshot {data['snapshot_id']}")
    _bound(data)


@app.command("rebind")
def rebind(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    unit_kind: str = _KIND,
    unit_id: str = typer.Argument(...),
    record_id: str = typer.Option(..., "--record", help="The project instruction to re-bind"),
    why: str = typer.Option(..., "--why", help="Why the running unit is re-bound"),
):
    """Re-bind a running unit to the instruction's current revision, or off it if withdrawn."""
    data = _call(
        ctx,
        "post",
        f"/api/v1/projects/{project_id}/snapshots/{unit_kind}/{unit_id}/rebindings",
        json={"record_id": record_id, "why": why},
    )
    if _json(ctx):
        print_json(data)
        return
    _bound(data)
    print_success(data["next"])

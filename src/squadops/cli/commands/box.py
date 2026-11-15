"""``squadops box lease``: the operator's lease on the box, outside every campaign (SIP-0109
§24dw; #2287), over ``/api/v1/box/lease``.

``show`` reads who holds the box and the operator lease's latest rows, so an operator checks it
is free before starting. ``acquire`` takes it for at most an hour (``--for 30m``), refused while
the supervisor or another operator holds it, a run is running or queued, or a campaign is live.
``release`` gives it back, after the last request served on the box has finished. Each change
sends an idempotency key, minted and printed when none is given, so a retry replays.
"""

from __future__ import annotations

import re
import uuid

import typer

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_detail, print_error, print_json, print_success, print_table

app = typer.Typer(name="box", help="The box: who holds it (SIP-0109 §9.3, §24dw)")
lease_app = typer.Typer(name="lease", help="The operator's lease on the box, outside campaigns")
app.add_typer(lease_app, name="lease")

_DURATION = re.compile(r"^(\d+)([smh]?)$")
_UNIT_S = {"": 1, "s": 1, "m": 60, "h": 3600}


def parse_duration(text: str) -> int:
    """``90``, ``90s``, ``30m`` or ``1h``, in seconds."""
    match = _DURATION.match(text.strip())
    if not match:
        raise typer.BadParameter(f"a duration like 30m or 1h, not {text!r}")
    return int(match.group(1)) * _UNIT_S[match.group(2)]


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
    return (ctx.obj or {}).get("format") == "json"


def _holder_line(lease: dict | None) -> str:
    if lease is None or not (lease["supervisor_holds"] or lease["operator_holds"]):
        return "the squad holds the box: it is free to take"
    who = "the operator" if lease["operator_holds"] else f"the supervisor ({lease['campaign_id']})"
    return f"{who} holds the box: {lease['held_by']}, until {lease['expires_at']}"


@lease_app.command("show")
def show(ctx: typer.Context):
    """Who holds the box now, and the operator lease's latest rows."""
    data = _call(ctx, "get", "/api/v1/box/lease")
    if _json(ctx):
        print_json(data)
        return
    print_success(_holder_line(data["lease"]))
    rows = [
        [
            str(e["seq"]),
            e["operation"],
            e["outcome"] + (f" ({e['refusal']})" if e["refusal"] else ""),
            e["actor"],
            e["committed_at"],
            e["reason"],
        ]
        for e in data["log"]
    ]
    if rows:
        print_table(["Seq", "Change", "Outcome", "By", "At", "Why"], rows)


@lease_app.command("acquire")
def acquire(
    ctx: typer.Context,
    hold_for: str = typer.Option(..., "--for", help="How long, at most 1h: 30m, 1h, 900s"),
    reason: str = typer.Option(..., "--reason", help="Why: recorded on the lease's log"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Take the box for the operator's own inference."""
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {"reason": reason, "idempotency_key": key, "expires_in_s": parse_duration(hold_for)}
    _result(ctx, _call(ctx, "post", "/api/v1/box/lease", json=body), key)


@lease_app.command("release")
def release(
    ctx: typer.Context,
    reason: str = typer.Option(..., "--reason", help="Why: recorded on the lease's log"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Give the box back, after the last request served on it has finished."""
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {"reason": reason, "idempotency_key": key}
    _result(ctx, _call(ctx, "post", "/api/v1/box/lease/release", json=body), key)


def _result(ctx: typer.Context, data: dict, key: str) -> None:
    if _json(ctx):
        print_json(data)
        return
    verb = "replayed" if data["replayed"] else "applied"
    print_success(f"{data['entry']['operation']} {verb} (key {key})")
    print_detail({"holds": _holder_line(data["lease"])})

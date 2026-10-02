"""Campaign commands (SIP-0109 §13, #1799): the CLI over ``/api/v1/campaigns``.

Every control operation sends an idempotency key. Without ``--idempotency-key`` one is minted
and printed, so a retry after a dropped connection can resend the same key and replay, rather
than act twice.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import typer
import yaml

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import print_detail, print_error, print_json, print_success, print_table

app = typer.Typer(name="campaigns", help="Create, read and control campaigns (SIP-0109)")


def _get_client(ctx: typer.Context) -> APIClient:
    return APIClient(load_config())


def _fmt(ctx: typer.Context) -> tuple[str, bool]:
    obj = ctx.obj or {}
    return obj.get("format", "table"), obj.get("quiet", False)


def _call(ctx: typer.Context, method: str, path: str, **kwargs):
    try:
        client = _get_client(ctx)
        data = getattr(client, method)(path, **kwargs)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    return data


def _key(given: str | None) -> str:
    return given or f"cli-{uuid.uuid4().hex}"


def _show_result(ctx: typer.Context, data: dict, key: str) -> None:
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
        return
    entry, campaign = data["entry"], data["campaign"]
    verb = "replayed" if data.get("replayed") else "applied"
    print_success(
        f"{entry['operation']} {verb}: {campaign['campaign_id']} "
        f"{entry['prior_state']} → {entry['next_state']} (key {key})"
    )
    if data.get("cancelled_cycles"):
        print_success(f"cancelled cycles: {', '.join(data['cancelled_cycles'])}")
    if data.get("launched_cycles"):
        print_success(f"launched cycles: {', '.join(data['launched_cycles'])}")


@app.command("create")
def create_campaign(
    ctx: typer.Context,
    file: Path = typer.Option(
        ..., "--file", "-f", help="YAML or JSON: project_id, objective, policy"
    ),
    reason: str = typer.Option(..., "--reason", help="Why: recorded on the control log"),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
    campaign_id: str | None = typer.Option(None, "--campaign-id"),
):
    """Create a campaign, in draft. Every policy limit is required."""
    try:
        spec = yaml.safe_load(file.read_text())
    except (OSError, yaml.YAMLError) as e:
        print_error(f"cannot read {file}: {e}")
        raise typer.Exit(code=2) from e
    key = _key(idempotency_key)
    body = {**spec, "reason": reason, "idempotency_key": key}
    if campaign_id:
        body["campaign_id"] = campaign_id
    _show_result(ctx, _call(ctx, "post", "/api/v1/campaigns", json=body), key)


@app.command("list")
def list_campaigns(
    ctx: typer.Context,
    project_id: str = typer.Option(..., "--project", "-p"),
):
    """List a project's campaigns, newest first."""
    data = _call(ctx, "get", "/api/v1/campaigns", params={"project_id": project_id})
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
        return
    rows = [[c["campaign_id"], c["state"], c.get("outcome") or "", c["updated_at"]] for c in data]
    print_table(["Campaign ID", "State", "Outcome", "Updated"], rows, quiet=quiet)


@app.command("show")
def show_campaign(ctx: typer.Context, campaign_id: str = typer.Argument(...)):
    """Show a campaign."""
    data = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}")
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
    else:
        print_detail(
            {
                **data,
                "objective": json.dumps(data["objective"]),
                "policy": json.dumps(data["policy"]),
            },
            quiet=quiet,
        )


@app.command("log")
def control_log(ctx: typer.Context, campaign_id: str = typer.Argument(...)):
    """The campaign's control log, refusals included."""
    data = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}/control-log")
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
        return
    rows = _log_rows(data)
    print_table(["#", "At", "Operation", "Outcome", "State", "Actor", "Reason"], rows, quiet=quiet)


def _log_rows(entries: list[dict]) -> list[list]:
    """One table row per control-log entry; a refusal names its reason in the outcome cell."""
    return [
        [
            e["seq"],
            e["committed_at"],
            e["operation"],
            e["outcome"] + (f" ({e['refusal']})" if e.get("refusal") else ""),
            f"{e['prior_state']} → {e['next_state']}",
            f"{e['actor']} ({e['actor_role']})",
            e["reason"],
        ]
        for e in entries
    ]


def _control(
    ctx: typer.Context,
    operation: str,
    campaign_id: str,
    reason: str,
    idempotency_key: str | None,
    expected_state: str | None,
) -> None:
    key = _key(idempotency_key)
    body = {"reason": reason, "idempotency_key": key}
    if expected_state:
        body["expected_state"] = expected_state
    _show_result(
        ctx, _call(ctx, "post", f"/api/v1/campaigns/{campaign_id}/{operation}", json=body), key
    )


_REASON = typer.Option(..., "--reason", help="Why: recorded on the control log")
_KEY = typer.Option(None, "--idempotency-key", help="Resend a key to replay, not repeat")
_EXPECTED = typer.Option(None, "--expected-state", help="Refuse if the campaign has moved")


@app.command("start")
def start(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
):
    """Start a draft campaign: its calibration cycle launches (the owner's word)."""
    _control(ctx, "start", campaign_id, reason, idempotency_key, None)


@app.command("pause")
def pause(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
    expected_state: str | None = _EXPECTED,
):
    """Pause a campaign (the supervisor's brake)."""
    _control(ctx, "pause", campaign_id, reason, idempotency_key, expected_state)


@app.command("resume")
def resume(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
    expected_state: str | None = _EXPECTED,
):
    """Resume a paused campaign (the owner's word)."""
    _control(ctx, "resume", campaign_id, reason, idempotency_key, expected_state)


@app.command("abort")
def abort(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
    expected_state: str | None = _EXPECTED,
):
    """Abort a campaign: terminal, and its running cycle is cancelled."""
    _control(ctx, "abort", campaign_id, reason, idempotency_key, expected_state)

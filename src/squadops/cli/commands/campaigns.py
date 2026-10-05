"""Campaign commands (SIP-0109 §13, #1799): the CLI over ``/api/v1/campaigns``.

Every control operation sends an idempotency key. Without ``--idempotency-key`` one is minted
and printed, so a retry after a dropped connection can resend the same key and replay, rather
than act twice.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import typer
import yaml

from squadops.campaigns.models import ControlOperation
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
    """Create a campaign, in draft. Every policy limit is required. The file's path and sha256
    are recorded on the creation row (#1954), so the campaign names the file that made it."""
    try:
        raw = file.read_bytes()
        spec = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as e:
        print_error(f"cannot read {file}: {e}")
        raise typer.Exit(code=2) from e
    key = _key(idempotency_key)
    body = {
        **spec,
        "reason": reason,
        "idempotency_key": key,
        "definition": {"path": str(file), "sha256": hashlib.sha256(raw).hexdigest()},
    }
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
    """Show a campaign, and the definition file its creation row records (#1954)."""
    data = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}")
    log = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}/control-log")
    created = next((e for e in log if e["operation"] == ControlOperation.CREATE), None)
    recorded = (created or {}).get("binding", {}).get("definition")
    data = {**data, "definition": recorded}
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
    else:
        print_detail(
            {
                **data,
                "objective": json.dumps(data["objective"]),
                "policy": json.dumps(data["policy"]),
                "definition": (
                    f"{recorded['path']} (sha256 {recorded['sha256']})"
                    if recorded
                    else "not recorded (created before #1954, or without a file)"
                ),
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
    action: str | None = None,
) -> None:
    key = _key(idempotency_key)
    body = {"reason": reason, "idempotency_key": key}
    if expected_state:
        body["expected_state"] = expected_state
    if action:
        body["action"] = action
    _show_result(
        ctx, _call(ctx, "post", f"/api/v1/campaigns/{campaign_id}/{operation}", json=body), key
    )


_REASON = typer.Option(..., "--reason", help="Why: recorded on the control log")
_KEY = typer.Option(None, "--idempotency-key", help="Resend a key to replay, not repeat")
_EXPECTED = typer.Option(None, "--expected-state", help="Refuse if the campaign has moved")


@app.command("digest")
def digest(ctx: typer.Context, campaign_id: str = typer.Argument(...)):
    """Print the campaign's morning digest, from its latest evidence package (§14)."""
    data = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}/package")
    fmt, _quiet = _fmt(ctx)
    if fmt == "json":
        print_json(data)
        return
    typer.echo(data["digest"])


@app.command("ledger")
def ledger(ctx: typer.Context, campaign_id: str = typer.Argument(...)):
    """The proposal ledger (§9.4): each version, its ruling, its outcome, its classification."""
    entries = _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}/ledger")
    fmt, quiet = _fmt(ctx)
    if fmt == "json":
        print_json(entries)
        return
    rows = [
        [
            f"{e['proposal_id']} v{e['version']}",
            (e.get("ruling") or {}).get("decision", "—"),
            str((e.get("outcome") or {}).get("row", "—")),
            (e.get("classification") or {}).get("classification", "—"),
        ]
        for e in entries
    ]
    print_table(["Proposal", "Ruling", "Decided (row)", "Classified"], rows, quiet=quiet)


@app.command("classify")
def classify(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    proposal_id: str = typer.Option(..., "--proposal"),
    version: int = typer.Option(..., "--version"),
    classification: str = typer.Option(
        ...,
        "--as",
        help="scope_too_large | criteria_not_checkable | conflicts_with_an_earlier_increment | "
        "ambiguous_manifest_delta | sound_proposal_built_badly",
    ),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
):
    """Classify what went wrong with a proposal version (the supervisor's reading, §9.4)."""
    key = _key(idempotency_key)
    body = {
        "proposal_id": proposal_id,
        "version": version,
        "classification": classification,
        "reason": reason,
        "idempotency_key": key,
    }
    _show_result(
        ctx, _call(ctx, "post", f"/api/v1/campaigns/{campaign_id}/classifications", json=body), key
    )


@app.command("start")
def start(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
):
    """Start a draft campaign: its calibration cycle launches (the owner or the supervisor)."""
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
    action: str | None = typer.Option(
        None,
        "--action",
        help=(
            "The action the owner names: required to resume an escalated campaign (propose, "
            "abandon_and_propose, repair, retry), except one escalated over a launch the box "
            "kept refusing, which resumes into launch_blocked; a paused one resumes into its "
            "held action"
        ),
    ),
):
    """Resume a paused or escalated campaign. An escalation, a limit's pause and the owner's own
    pause need the owner's word (§10, §24az); the supervisor resumes its own pause."""
    _control(ctx, "resume", campaign_id, reason, idempotency_key, expected_state, action)


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


# --- the box lease (SIP-0109 §9.3; #1802) ---------------------------------------------------------

lease_app = typer.Typer(
    name="lease", help="The box lease: the supervisor holds the Spark at a gate"
)
app.add_typer(lease_app)


def _show_lease(ctx: typer.Context, lease: dict | None) -> None:
    fmt, _quiet = _fmt(ctx)
    if fmt == "json":
        print_json(lease)
        return
    if lease is None:
        print_success("no lease recorded: the squad holds the box")
        return
    holds = "holds the box" if lease["supervisor_holds"] else "does not hold the box"
    print_success(
        f"{lease['holder']} ({lease['held_by']}) {holds}; campaign {lease['campaign_id']}, "
        f"acquired {lease['acquired_at']}, expires {lease['expires_at']}"
    )


@lease_app.command("show")
def lease_show(ctx: typer.Context, campaign_id: str = typer.Argument(...)):
    """Who holds the box now (one lease, read through any campaign)."""
    _show_lease(ctx, _call(ctx, "get", f"/api/v1/campaigns/{campaign_id}/lease"))


@lease_app.command("acquire")
def lease_acquire(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    expires_in: int = typer.Option(
        ..., "--expires-in", help="Seconds to hold the box, at most the policy's lease_expiry_s"
    ),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
):
    """Take the box for this campaign's increment gate; while held, no cycle launches and no
    run starts. Refused outside the gate, while a run is in flight, or while another holds it."""
    key = _key(idempotency_key)
    data = _call(
        ctx,
        "post",
        f"/api/v1/campaigns/{campaign_id}/lease",
        json={"reason": reason, "idempotency_key": key, "expires_in_s": expires_in},
    )
    _show_lease(ctx, data["lease"])


@lease_app.command("release")
def lease_release(
    ctx: typer.Context,
    campaign_id: str = typer.Argument(...),
    reason: str = _REASON,
    idempotency_key: str | None = _KEY,
):
    """Give the box back to the squad, the crew's models unloaded."""
    key = _key(idempotency_key)
    data = _call(
        ctx,
        "post",
        f"/api/v1/campaigns/{campaign_id}/lease/release",
        json={"reason": reason, "idempotency_key": key},
    )
    _show_lease(ctx, data["lease"])

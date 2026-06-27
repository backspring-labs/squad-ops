"""Assignment commands (SIP-0089 §2.7).

`squadops assignment list <agent-id>` and `squadops assignment show
<assignment-id>` are operator read commands; `squadops assignment create ...`
is EXPERIMENTAL/INTERNAL in v1.1 (not a public operator command).

All three reach the runtime-api over HTTP on the versioned resource lane
(`/api/v1/...`) — the CLI is forbidden from importing the Postgres adapter
directly (D26), mirroring how `agent state` reads runtime-state over HTTP.
"""

from __future__ import annotations

import typer

from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import (
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
)

app = typer.Typer(name="assignment", help="Inspect and manage duty assignments (SIP-0089)")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


def _window_field(assignment: dict, key: str) -> str:
    """Pull a nested active_window field for table display."""
    window = assignment.get("active_window") or {}
    return str(window.get(key, "") or "")


@app.command("list")
def list_assignments(
    ctx: typer.Context,
    agent_id: str = typer.Argument(..., help="Agent identifier (e.g. max, neo)"),
):
    """List all assignments held by an agent (active and inactive)."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        try:
            data = client.get(f"/api/v1/agents/{agent_id}/assignments")
        finally:
            client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
        return

    rows = [
        [
            a["assignment_id"],
            a["assignment_type"],
            a["assigned_role"],
            a["strictness"],
            _window_field(a, "start"),
            _window_field(a, "end"),
            str(a["active"]),
        ]
        for a in data
    ]
    print_table(
        ["Assignment ID", "Type", "Role", "Strictness", "Window Start", "Window End", "Active"],
        rows,
        quiet=quiet,
    )


@app.command("show")
def show_assignment(
    ctx: typer.Context,
    assignment_id: str = typer.Argument(..., help="Assignment identifier"),
):
    """Show one assignment by id."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        try:
            data = client.get(f"/api/v1/assignments/{assignment_id}")
        finally:
            client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("create")
def create_assignment(
    ctx: typer.Context,
    agent_id: str = typer.Argument(..., help="Agent identifier (holder of the assignment)"),
    role: str = typer.Option(..., "--role", help="Assigned role"),
    window_start: str = typer.Option(..., "--window-start", help="Window start (ISO 8601)"),
    window_end: str = typer.Option(..., "--window-end", help="Window end (ISO 8601)"),
    timezone: str = typer.Option("UTC", "--timezone", help="Civil timezone of the window"),
    assignment_id: str | None = typer.Option(
        None, "--assignment-id", help="Explicit id (upsert target); generated if omitted"
    ),
    assignment_type: str = typer.Option("duty", "--type", help="duty|reserve|cycle_eligibility"),
    priority: int = typer.Option(0, "--priority", help="Scheduling priority"),
    strictness: str = typer.Option("hard", "--strictness", help="hard|soft"),
    reserve_before_seconds: int | None = typer.Option(
        None,
        "--reserve-before-seconds",
        help="Pre-window reserve buffer; omitted = D7 default (900 hard / 0 soft)",
    ),
    reserve_after_seconds: int | None = typer.Option(
        None, "--reserve-after-seconds", help="Trailing reserve buffer; omitted = 0"
    ),
    recall_policy: str = typer.Option(
        "graceful", "--recall-policy", help="immediate|graceful|none"
    ),
    graceful_window_seconds: int = typer.Option(0, "--graceful-window-seconds"),
    missed_window_policy: str = typer.Option(
        "skip",
        "--missed-window-policy",
        help="skip|start_late_within_grace|require_operator_review",
    ),
    off_window_mode: list[str] = typer.Option(
        [], "--off-window-mode", help="Allowed off-window mode (repeatable): duty|cycle|ambient"
    ),
    active: bool = typer.Option(
        True, "--active/--inactive", help="Whether the assignment is active"
    ),
):
    """Create (upsert) an assignment. EXPERIMENTAL/INTERNAL — not a public operator command.

    Reserve buffers are optional: omit them to apply the SIP-0089 §11.4 defaults
    (15 minutes before a hard duty window, 0 for soft).
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    body: dict = {
        "agent_id": agent_id,
        "assigned_role": role,
        "window_start": window_start,
        "window_end": window_end,
        "timezone": timezone,
        "assignment_type": assignment_type,
        "priority": priority,
        "strictness": strictness,
        "recall_policy": recall_policy,
        "graceful_window_seconds": graceful_window_seconds,
        "missed_window_policy": missed_window_policy,
        "allowed_off_window_modes": off_window_mode,
        "active": active,
    }
    if assignment_id is not None:
        body["assignment_id"] = assignment_id
    # Only send reserve overrides when provided, so the server applies D7 defaults.
    if reserve_before_seconds is not None:
        body["reserve_before_window_seconds"] = reserve_before_seconds
    if reserve_after_seconds is not None:
        body["reserve_after_window_seconds"] = reserve_after_seconds

    try:
        client = _get_client(ctx)
        try:
            data = client.post("/api/v1/assignments", json=body)
        finally:
            client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Assignment {data.get('assignment_id', '')} created")

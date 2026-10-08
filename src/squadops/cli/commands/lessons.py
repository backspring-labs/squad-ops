"""``squadops lessons``: Cross-Cycle Memory's lessons (SIP-0110 §0.6–§0.7, slice 3d).

The auditor drafts (``draft``); the owner approves and revokes (``approve``, ``revoke``). A draft and
an approval are files: each carries several records (the applicability, the cited observations; the
ruling, the replay check, the combined check) that flags would scatter.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_error, print_json, print_success, print_table

app = typer.Typer(name="lessons", help="Cross-Cycle Memory's lessons: draft, approve, revoke")


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


def _document(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print_error(f"{path}: {e}")
        raise typer.Exit(code=2) from e
    if not isinstance(data, dict):
        print_error(f"{path}: expected a mapping")
        raise typer.Exit(code=2)
    return data


@app.command("list")
def list_lessons(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Every revision of the project's lessons, with its approvals in force."""
    data = _call(ctx, "get", f"/api/v1/projects/{project_id}/lessons")
    if _json(ctx):
        print_json(data)
        return
    rows = [
        [
            lesson["revision_id"],
            lesson["target_behavior"],
            ", ".join(a["approval_id"] for a in lesson["approvals"] if not a["revoked_at"]) or "-",
            lesson["created_at"],
        ]
        for lesson in data
    ]
    print_table(["revision", "target behavior", "approvals in force", "drafted"], rows)


@app.command("draft")
def draft(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="YAML: target_behavior, text, applicability (task_types, roles, stacks, "
        "model_families), template_id, template_version, drafter_model, drafter_version, "
        "cited_observations",
    ),
):
    """Store the auditor's draft as its pattern's next revision. It reaches no task until approved."""
    data = _call(ctx, "post", f"/api/v1/projects/{project_id}/lessons", json=_document(file))
    if _json(ctx):
        print_json(data)
        return
    print_success(f"drafted {data['revision_id']} ({data['target_behavior']})")


@app.command("together")
def together(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    revision_id: str = typer.Argument(...),
):
    """The approved lessons a task could receive beside this revision: what the combined check covers."""
    data = _call(
        ctx, "get", f"/api/v1/projects/{project_id}/lessons/{revision_id}/supplied-together"
    )
    if _json(ctx):
        print_json(data)
        return
    print_success(", ".join(data["revision_ids"]) or "none: no approved lesson meets this one")


@app.command("approve")
def approve(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    revision_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="YAML: ruling, replay_check (reference, result), combined_check (revision_ids, "
        "verdict, reference), and optionally a narrower applicability",
    ),
):
    """The owner's approval of a revision (SIP-0110 §0.6). Units admitted afterwards receive it."""
    data = _call(
        ctx,
        "post",
        f"/api/v1/projects/{project_id}/lessons/{revision_id}/approvals",
        json=_document(file),
    )
    if _json(ctx):
        print_json(data)
        return
    print_success(f"approved {revision_id} as {data['approval_id']}")


@app.command("revoke")
def revoke(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    approval_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason", help="Why the approval is revoked"),
):
    """The owner's revocation (SIP-0110 §0.7). Names the running units that still hold it."""
    data = _call(
        ctx,
        "post",
        f"/api/v1/projects/{project_id}/approvals/{approval_id}/revocation",
        json={"reason": reason},
    )
    if _json(ctx):
        print_json(data)
        return
    print_success(f"revoked {approval_id}")
    for unit in data["units_holding_it"]:
        print_success(f"still held by {unit['unit_kind']} {unit['unit_id']}")
    print_success(data["next"])

"""A Project's goal set (SIP-0115 §8.2, slice 1, #2884): show it, edit it, read its history.

``show`` prints the goal set as YAML, its revision's author and reason as a comment above it, so
``squadops goals show <project> > goals.yaml`` is a file ``goals edit`` takes back as the next
revision. Each edit, a reorder included, writes a revision; none is changed in place.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import typer
import yaml

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_error, print_json, print_success, print_table

app = typer.Typer(name="goals", help="A Project's goal set: its goal, expected results, backlog")


def _format(ctx: typer.Context) -> str:
    return ctx.obj.get("format", "table") if ctx.obj else "table"


@app.command("show")
def show(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    revision: int | None = typer.Option(None, "--revision", help="Default: the active one"),
):
    """Show a Project's goal set: the active revision, or --revision N."""
    path = (
        f"/api/v1/projects/{project_id}/goal-set/revisions/{revision}"
        if revision is not None
        else f"/api/v1/projects/{project_id}/goal-set"
    )
    try:
        client = _get_client(ctx)
        data = client.get(path)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    if _format(ctx) == "json":
        print_json(data)
        return
    typer.echo(_header(data))
    typer.echo(yaml.safe_dump(data["goal_set"], sort_keys=False, allow_unicode=True), nl=False)


def _header(data: dict) -> str:
    """The revision's provenance as YAML comments: kept on screen, ignored when read back."""
    lines = [
        f"# {data['project_id']} goal set, revision {data['revision']}, by {data['author']} "
        f"at {data['created_at']}",
        f"# reason: {data['reason']}",
    ]
    if data.get("source_ref"):
        lines.append(f"# source: {data['source_ref']}")
    return "\n".join(lines)


@app.command("edit")
def edit(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ..., "--file", "-f", help="The goal set, YAML or JSON (the shape `goals show` prints)"
    ),
    reason: str = typer.Option(..., "--reason", help="Why this revision is written"),
    expected_revision: int | None = typer.Option(
        None, "--expected-revision", help="Default: the Project's active revision (0 for none)"
    ),
    source_ref: str | None = typer.Option(
        None, "--source-ref", help="Where the change came from: a conversation's or issue's link"
    ),
    idempotency_key: str | None = typer.Option(
        None, "--idempotency-key", help="Resend the printed key to retry safely"
    ),
):
    """Write a Project's next goal-set revision from a file. Every edit, a reorder included, is a
    new revision with its reason; a concurrent edit is refused, never overwritten."""
    try:
        goal_set = yaml.safe_load(file.read_text())
    except (OSError, yaml.YAMLError) as e:
        print_error(f"cannot read {file}: {e}")
        raise typer.Exit(code=2) from e
    if not isinstance(goal_set, dict):
        print_error(f"{file} holds no goal set: a mapping with `goal`, `backlog` and the rest")
        raise typer.Exit(code=2)
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    try:
        client = _get_client(ctx)
        if expected_revision is None:
            expected_revision = _active_revision(client, project_id)
        data = client.post(
            f"/api/v1/projects/{project_id}/goal-set/revisions",
            json={
                "idempotency_key": key,
                "expected_revision": expected_revision,
                "reason": reason,
                **({"source_ref": source_ref} if source_ref is not None else {}),
                "goal_set": goal_set,
            },
        )
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e
    if _format(ctx) == "json":
        print_json(data)
        return
    written = data["revision"]
    verb = "replayed" if data["replayed"] else "written"
    print_success(
        f"{verb}: {project_id} goal set revision {written['revision']} "
        f"({len(written['goal_set']['backlog'])} backlog item(s); key {data['idempotency_key']})"
    )


def _active_revision(client, project_id: str) -> int:
    """The active revision's number, or 0 when the Project has no goal set yet. An unknown
    Project reads as 0 too: the write that follows is refused naming it."""
    try:
        return client.get(f"/api/v1/projects/{project_id}/goal-set")["revision"]
    except CLIError as e:
        if e.exit_code != exit_codes.NOT_FOUND:
            raise
        return 0


@app.command("history")
def history(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Every revision of a Project's goal set, newest first: who wrote it, and why."""
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False
    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/goal-set/revisions")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    if _format(ctx) == "json":
        print_json(data)
        return
    if not data:
        typer.echo(f"{project_id} has no goal set yet: write one with `squadops goals edit`")
        return
    rows = [
        [
            str(r["revision"]),
            r["created_at"],
            r["author"],
            r["reason"],
            r.get("source_ref") or "",
            str(len(r["goal_set"]["backlog"])),
        ]
        for r in data
    ]
    print_table(["Revision", "Written", "Author", "Reason", "Source", "Backlog"], rows, quiet=quiet)

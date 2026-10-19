"""
Project commands (SIP-0065 §6.3).
"""

from __future__ import annotations

import uuid

import typer

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_detail, print_error, print_json, print_success, print_table

app = typer.Typer(name="projects", help="Manage projects")


@app.command("list")
def list_projects(ctx: typer.Context):
    """List all projects."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get("/api/v1/projects")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        rows = [[p["project_id"], p["name"], p.get("description", "")] for p in data]
        print_table(["Project ID", "Name", "Description"], rows, quiet=quiet)


@app.command("ls", hidden=True)
def list_projects_alias(ctx: typer.Context):
    """Alias for list."""
    list_projects(ctx)


@app.command("show")
def show_project(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Show project details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_project_alias(ctx: typer.Context, project_id: str = typer.Argument(...)):
    """Alias for show."""
    show_project(ctx, project_id)


@app.command("import")
def import_project(
    ctx: typer.Context,
    repo: str = typer.Option(..., "--repo", help="The product's authoritative repository"),
    name: str = typer.Option(..., "--name", help="The Project's name"),
    base_ref: str = typer.Option(
        ..., "--base-ref", help="The ref development starts from, e.g. refs/heads/main"
    ),
    contribution_mode: str = typer.Option(
        ...,
        "--contribution-mode",
        help="How changes reach the product: review_request | patch_export | direct_push",
    ),
    owner: str = typer.Option(..., "--owner", help="The product's owner or maintainer"),
    delegate: list[str] = typer.Option(
        [],
        "--delegate",
        help="An action the owner delegates (repeatable): engineering_decisions | "
        "candidate_acceptance | contribution | integration",
    ),
    project_id: str | None = typer.Option(None, "--id", help="Default: prj- and the name"),
    description: str = typer.Option("", "--description"),
    repository_root: str = typer.Option(".", "--repository-root"),
    acceptance_policy: str | None = typer.Option(None, "--acceptance-policy"),
    idempotency_key: str | None = typer.Option(
        None, "--idempotency-key", help="Resend the printed key to retry safely"
    ),
):
    """Register an existing product (SIP-0112 E.4.1). It stays REGISTERING until its source is
    proven reachable. Without --idempotency-key one is minted and printed, so a retry after a
    dropped connection replays rather than registering twice."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {
        "idempotency_key": key,
        "name": name,
        "description": description,
        "origin": {"mode": "import"},
        "source": {
            "repo_uri": repo,
            "base_ref": base_ref,
            "contribution_mode": contribution_mode,
            "repository_root": repository_root,
        },
        "ownership": {
            "owner": owner,
            "delegated_actions": delegate,
            "acceptance_policy_ref": acceptance_policy,
        },
    }
    if project_id:
        body["project_id"] = project_id
    try:
        client = _get_client(ctx)
        data = client.post("/api/v1/projects", json=body)
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
        return
    project = data["project"]
    verb = "replayed" if data["replayed"] else "registered"
    print_success(
        f"{verb}: {project['project_id']} {project['lifecycle_status']} "
        f"(record version {project['record_version']}, key {data['idempotency_key']})"
    )

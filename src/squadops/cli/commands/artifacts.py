"""
Artifact and baseline commands (SIP-0065 §6.3).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

import typer

from squadops.cli import exit_codes
from squadops.cli.client import APIClient, CLIError
from squadops.cli.config import load_config
from squadops.cli.output import (
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
)

artifacts_app = typer.Typer(name="artifacts", help="Manage artifacts")
baseline_app = typer.Typer(name="baseline", help="Manage baseline artifacts")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


# =============================================================================
# Artifact commands
# =============================================================================


@artifacts_app.command("ingest")
def ingest_artifact(
    ctx: typer.Context,
    project_id: str = typer.Option(..., "--project", help="Project ID"),
    artifact_type: str = typer.Option(..., "--type", help="Artifact type (prd, code, test_report, etc.)"),
    file_path: Path = typer.Option(..., "--file", help="File to ingest"),
):
    """Ingest an artifact via multipart/form-data upload.

    Sends file + metadata matching SIP-0064 T16 transport contract.
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    if not file_path.is_file():
        print_error(f"Error: file not found: {file_path}")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    media_type, _ = mimetypes.guess_type(str(file_path))
    if not media_type:
        media_type = "application/octet-stream"

    fields = {
        "artifact_type": artifact_type,
        "filename": file_path.name,
        "media_type": media_type,
    }

    try:
        client = _get_client(ctx)
        data = client.upload(
            f"/api/v1/projects/{project_id}/artifacts/ingest",
            file_path=file_path,
            fields=fields,
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Artifact {data.get('artifact_id', '')} ingested")
        print_detail({
            "artifact_id": data.get("artifact_id", ""),
            "type": data.get("artifact_type", ""),
            "size": data.get("size_bytes", ""),
        })


@artifacts_app.command("get")
def get_artifact(ctx: typer.Context, artifact_id: str = typer.Argument(...)):
    """Show artifact metadata."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/artifacts/{artifact_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@artifacts_app.command("download")
def download_artifact(
    ctx: typer.Context,
    artifact_id: str = typer.Argument(...),
    out: Path = typer.Option(..., "--out", help="Output file path"),
):
    """Download artifact to a local file."""
    try:
        client = _get_client(ctx)
        content, filename = client.download(f"/api/v1/artifacts/{artifact_id}/download")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    out.write_bytes(content)
    print_success(f"Downloaded to {out}")


@artifacts_app.command("list")
def list_artifacts(
    ctx: typer.Context,
    project_id: str = typer.Option(..., "--project", help="Project ID"),
    cycle_id: Optional[str] = typer.Option(None, "--cycle", help="Filter by cycle ID"),
    artifact_type: Optional[str] = typer.Option(None, "--type", help="Filter by artifact type"),
):
    """List artifacts for a project.

    Selection rule: if --cycle provided, uses cycle-scoped endpoint.
    Otherwise uses project-scoped endpoint with optional --type filter.
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        if cycle_id:
            data = client.get(
                f"/api/v1/projects/{project_id}/cycles/{cycle_id}/artifacts"
            )
        else:
            params = {}
            if artifact_type:
                params["artifact_type"] = artifact_type
            data = client.get(f"/api/v1/projects/{project_id}/artifacts", params=params)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [a["artifact_id"], a.get("artifact_type", ""), a.get("filename", ""), str(a.get("size_bytes", ""))]
            for a in data
        ]
        print_table(["Artifact ID", "Type", "Filename", "Size"], rows, quiet=quiet)


@artifacts_app.command("ls", hidden=True)
def list_artifacts_alias(
    ctx: typer.Context,
    project_id: str = typer.Option(..., "--project"),
    cycle_id: Optional[str] = typer.Option(None, "--cycle"),
    artifact_type: Optional[str] = typer.Option(None, "--type"),
):
    """Alias for list."""
    list_artifacts(ctx, project_id, cycle_id, artifact_type)


# =============================================================================
# Baseline commands
# =============================================================================


@baseline_app.command("set")
def set_baseline(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
):
    """Promote an artifact as the baseline for a given type."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(
            f"/api/v1/projects/{project_id}/baseline/{artifact_type}",
            json={"artifact_id": artifact_id},
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Baseline set: {artifact_type} → {artifact_id}")


@baseline_app.command("get")
def get_baseline(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    artifact_type: str = typer.Argument(...),
):
    """Get the baseline artifact for a given type."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/baseline/{artifact_type}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@baseline_app.command("list")
def list_baselines(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
):
    """List all baselines for a project.

    Returns dict keyed by artifact_type → artifact metadata.
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/baseline")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code)

    if fmt == "json":
        print_json(data)
    else:
        if isinstance(data, dict):
            rows = [
                [art_type, info.get("artifact_id", ""), info.get("filename", "")]
                for art_type, info in data.items()
            ]
        else:
            rows = []
        print_table(["Type", "Artifact ID", "Filename"], rows, quiet=quiet)

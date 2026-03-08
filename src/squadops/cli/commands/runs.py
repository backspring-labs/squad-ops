"""
Run commands (SIP-0065 §6.3).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


def _format_duration(started: str | None, finished: str | None) -> str:
    """Compute human-readable duration from ISO timestamp strings."""
    if not started or not finished:
        return ""
    try:
        s = datetime.fromisoformat(started)
        f = datetime.fromisoformat(finished)
        delta = f - s
        total = int(delta.total_seconds())
        if total < 60:
            return f"{total}s"
        minutes, seconds = divmod(total, 60)
        return f"{minutes}m{seconds}s"
    except (ValueError, TypeError):
        return ""


app = typer.Typer(name="runs", help="Manage execution runs within cycles")


def _get_client(ctx: typer.Context) -> APIClient:
    config = load_config()
    return APIClient(config)


@app.command("list")
def list_runs(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """List runs for a cycle."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [
                r["run_id"],
                str(r["run_number"]),
                r.get("workload_type", "") or "",
                r["status"],
                r.get("started_at", "") or "",
                r.get("finished_at", "") or "",
                _format_duration(r.get("started_at"), r.get("finished_at")),
            ]
            for r in data
        ]
        print_table(
            ["Run ID", "#", "Workload", "Status", "Started", "Finished", "Duration"],
            rows,
            quiet=quiet,
        )


@app.command("ls", hidden=True)
def list_runs_alias(
    ctx: typer.Context, project_id: str = typer.Argument(...), cycle_id: str = typer.Argument(...)
):
    """Alias for list."""
    list_runs(ctx, project_id, cycle_id)


@app.command("show")
def show_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """Show run details."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_detail(data, quiet=quiet)


@app.command("cat", hidden=True)
def show_run_alias(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """Alias for show."""
    show_run(ctx, project_id, cycle_id, run_id)


@app.command("retry")
def retry_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
):
    """Create a new run (retry) for a cycle.

    Creates an execution record. Does not trigger task execution
    (deferred to a future release).
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Run {data.get('run_id', '')} created")


@app.command("cancel")
def cancel_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """Cancel a run."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel")
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Run {run_id} cancelled")


@app.command("gate")
def gate_decision(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
    gate_name: str = typer.Argument(...),
    approve: bool = typer.Option(False, "--approve", help="Approve the gate"),
    reject: bool = typer.Option(False, "--reject", help="Reject the gate"),
    with_refinements: bool = typer.Option(
        False, "--with-refinements", help="Approve with refinements needed"
    ),
    return_for_revision: bool = typer.Option(
        False, "--return-for-revision", help="Return for revision on same workload path"
    ),
    notes: str | None = typer.Option(None, "--notes", help="Decision notes"),
):
    """Record a gate decision.

    Wire mapping: --approve sends "approved", --reject sends "rejected",
    --with-refinements sends "approved_with_refinements",
    --return-for-revision sends "returned_for_revision".
    """
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    # D20: Exactly one decision flag required
    flags = {
        "--approve": approve,
        "--reject": reject,
        "--with-refinements": with_refinements,
        "--return-for-revision": return_for_revision,
    }
    selected = [name for name, val in flags.items() if val]
    if len(selected) != 1:
        valid_flags = ", ".join(flags.keys())
        print_error(f"Error: must specify exactly one decision flag. Valid flags: {valid_flags}")
        raise typer.Exit(code=2)

    # Wire mapping: CLI flag → API decision value
    if approve:
        decision = "approved"
    elif reject:
        decision = "rejected"
    elif with_refinements:
        decision = "approved_with_refinements"
    else:
        decision = "returned_for_revision"

    body = {"decision": decision}
    if notes:
        body["notes"] = notes

    try:
        client = _get_client(ctx)
        data = client.post(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}",
            json=body,
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Gate {gate_name!r} {decision}")


@app.command("resume")
def resume_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
    reason: str | None = typer.Option(None, "--reason", help="Reason for resuming"),
):
    """Resume a paused or failed run from its latest checkpoint."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"

    body = {}
    if reason:
        body["resume_reason"] = reason

    try:
        client = _get_client(ctx)
        data = client.post(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/resume",
            json=body if body else None,
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        print_success(f"Run {run_id} resumed")


@app.command("checkpoints")
def list_checkpoints(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
):
    """List checkpoints for a run."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    try:
        client = _get_client(ctx)
        data = client.get(
            f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/checkpoints"
        )
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
    else:
        rows = [
            [
                str(cp["checkpoint_index"]),
                str(cp["completed_task_count"]),
                str(cp["artifact_ref_count"]),
                cp.get("created_at", ""),
            ]
            for cp in data
        ]
        print_table(["Index", "Tasks Completed", "Artifacts", "Created At"], rows, quiet=quiet)


# Build artifact types eligible for assembly (D9)
_BUILD_ARTIFACT_TYPES = {"source", "test", "config"}


@app.command("assemble")
def assemble_run(
    ctx: typer.Context,
    project_id: str = typer.Argument(..., help="Project ID"),
    cycle_id: str = typer.Argument(..., help="Cycle ID"),
    run_id: str = typer.Argument(..., help="Run ID"),
    out: Path = typer.Option(
        Path("./output"),
        "--out",
        help="Output directory",
    ),
):
    """Assemble build artifacts from a completed run into a local directory.

    Downloads source, test, and config artifacts and writes them
    preserving their original filenames.
    """
    try:
        client = _get_client(ctx)

        # 1. Fetch cycle metadata for output directory naming
        cycle_data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}")
        pid = cycle_data.get("project_id") or ""
        output_dir_name = pid if pid else cycle_id[:12]

        # 2. Fetch run to get artifact_refs
        run_data = client.get(f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}")
        artifact_refs = run_data.get("artifact_refs", [])

        if not artifact_refs:
            client.close()
            print_error("No artifacts found for this run")
            raise typer.Exit(code=exit_codes.NOT_FOUND)

        # 3. Fetch metadata for each artifact, filter to build types
        build_artifacts: list[dict] = []
        for ref_id in artifact_refs:
            meta = client.get(f"/api/v1/artifacts/{ref_id}")
            if meta.get("artifact_type") in _BUILD_ARTIFACT_TYPES:
                build_artifacts.append(meta)

        if not build_artifacts:
            client.close()
            print_error(
                "No build artifacts (source/test/config) found — "
                "this run may only contain planning artifacts"
            )
            raise typer.Exit(code=exit_codes.NOT_FOUND)

        # 4. Create output directory and download each artifact
        target_dir = out / output_dir_name
        target_dir.mkdir(parents=True, exist_ok=True)

        written_files: list[str] = []
        for meta in build_artifacts:
            content, _ = client.download(f"/api/v1/artifacts/{meta['artifact_id']}/download")
            filepath = target_dir / meta["filename"]
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(content)
            written_files.append(meta["filename"])

        client.close()

        # 5. Print file tree and README content (if present)
        print_success(f"Assembled {len(written_files)} file(s) to {target_dir}")
        rows = [
            [meta["filename"], meta.get("artifact_type", ""), str(meta.get("size_bytes", ""))]
            for meta in build_artifacts
        ]
        quiet = ctx.obj.get("quiet", False) if ctx.obj else False
        print_table(["Filename", "Type", "Size"], rows, quiet=quiet)

        # Print README content if one was assembled
        readme_path = target_dir / "README.md"
        if readme_path.exists():
            typer.echo(f"\n--- {readme_path.name} ---")
            typer.echo(readme_path.read_text(encoding="utf-8"))

    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e

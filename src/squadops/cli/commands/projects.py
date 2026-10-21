"""
Project commands (SIP-0065 §6.3).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import typer
import yaml

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_detail, print_error, print_json, print_success, print_table
from squadops.projects.models import ProjectLifecycleStatus

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


@app.command("validate")
def validate_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    token_from_gh: bool = typer.Option(
        False,
        "--token-from-gh",
        help="Reach a private repository with your own GitHub access (`gh auth token`), once",
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Reach a registered product's source (SIP-0112 E.4.2): READY at its base ref's commit, or
    FAILED_REGISTRATION with the reason. Run it again to retry a failed registration."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {"idempotency_key": key}
    if token_from_gh:
        body["token"] = _gh_token()
    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/validate", json=body)
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
        return
    project = data["project"]
    status = project["lifecycle_status"]
    found = (
        project["development_baseline_commit"]
        if status == ProjectLifecycleStatus.READY
        else project["validation_diagnostic"]
    )
    print_success(f"{project['project_id']} {status}: {found} (key {data['idempotency_key']})")
    if status != ProjectLifecycleStatus.READY:
        raise typer.Exit(code=1)


@app.command("configure")
def configure_project(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ..., "--file", "-f", help="YAML or JSON with `technical` (commands, start) and `quality`"
    ),
    expected_revision: int | None = typer.Option(
        None, "--expected-revision", help="Default: the Project's current revision"
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Record a Project's next Development Configuration revision (SIP-0112 E.4.2): its native
    checks and its start declaration, validated, with the repository's instruction sources."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    try:
        spec = yaml.safe_load(file.read_text())
    except (OSError, yaml.YAMLError) as e:
        print_error(f"cannot read {file}: {e}")
        raise typer.Exit(code=2) from e
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    try:
        client = _get_client(ctx)
        if expected_revision is None:
            current = client.get(f"/api/v1/projects/{project_id}")
            expected_revision = current.get("development_configuration_revision") or 0
        data = client.post(
            f"/api/v1/projects/{project_id}/development-configurations",
            json={
                "idempotency_key": key,
                "expected_revision": expected_revision,
                **{k: spec[k] for k in ("technical", "quality") if k in (spec or {})},
            },
        )
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e

    if fmt == "json":
        print_json(data)
        return
    configuration = data["configuration"]
    sources = configuration["document"]["configuration"]["instruction_sources"]
    verb = "replayed" if data["replayed"] else "recorded"
    print_success(
        f"{verb}: {project_id} Development Configuration revision {configuration['revision']} "
        f"({len(sources)} instruction source(s) found; key {data['idempotency_key']})"
    )


@app.command("configuration")
def show_configuration(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    revision: int | None = typer.Option(None, "--revision", help="Default: the current one"),
):
    """Show a Project's Development Configuration, as stored."""
    path = (
        f"/api/v1/projects/{project_id}/development-configurations/{revision}"
        if revision is not None
        else f"/api/v1/projects/{project_id}/development-configuration"
    )
    try:
        client = _get_client(ctx)
        data = client.get(path)
        client.close()
    except CLIError as e:
        print_error(str(e))
        raise typer.Exit(code=e.exit_code) from e
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    if fmt == "json":
        print_json(data)
    else:
        typer.echo(yaml.safe_dump(data["document"], sort_keys=False))


@app.command("baseline")
def baseline(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    capture: bool = typer.Option(
        False, "--capture", help="Run the product's checks now, rather than show the latest"
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """A Project's inherited baseline (SIP-0112 FR-20): each of its own checks on the pinned,
    unmodified source, PASS, FAIL or UNVERIFIED with the reason."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    try:
        client = _get_client(ctx)
        data = (
            # #2605: a capture runs the product's install and every check before it answers.
            client.post(
                f"/api/v1/projects/{project_id}/baselines",
                json={"idempotency_key": key},
                timeout=client.long_timeout,
            )
            if capture
            else client.get(f"/api/v1/projects/{project_id}/baseline")
        )
        client.close()
    except CLIError as e:
        named = not capture or key in str(e)
        print_error(str(e) if named else f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e
    if fmt == "json":
        print_json(data)
        return
    document = data["document"]
    rows = [
        [c["id"], c["result"], c.get("attribution", ""), c.get("reason", "")]
        for c in document["checks"]
    ]
    print_table(["Check", "Result", "Attribution", "Reason"], rows, quiet=False)
    print_success(
        f"{project_id} at {document['commit'][:12]}, configuration revision "
        f"{document['development_configuration_revision']}"
    )


@app.command("contribute")
def contribute(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Option(..., "--cycle", help="The cycle whose run is contributed"),
    run_id: str = typer.Option(..., "--run", help="The run whose verified change is contributed"),
    token_from_gh: bool = typer.Option(
        False,
        "--token-from-gh",
        help="Contribute with your own GitHub access (`gh auth token`), for this act only",
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Contribute a run's verified change through the Project's own process (SIP-0112 FR-06):
    for review_request, push its branch and open the pull request; for patch_export, record
    the run's patch as the contribution. Recorded pending until the product takes it."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {"cycle_id": cycle_id, "run_id": run_id, "idempotency_key": key}
    if token_from_gh:
        body["token"] = _gh_token()
    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/contributions", json=body)
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e
    if fmt == "json":
        print_json(data)
        return
    contribution = data["contribution"]
    print_detail(contribution)
    where = contribution["review_url"] or "the run's source_change.patch"
    again = " (already contributed)" if data.get("replayed") else ""
    print_success(f"{contribution['mode']} {contribution['commit'][:12]}: {where}{again}")


@app.command("initialize")
def initialize(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    manifest: Path = typer.Option(
        ...,
        "--manifest",
        exists=True,
        dir_okay=False,
        help="The approved interface manifest (YAML) the blueprint's layout is rendered from",
    ),
    token_from_gh: bool = typer.Option(
        False,
        "--token-from-gh",
        help="Push with your own GitHub access (`gh auth token`), for this act only",
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Make a greenfield Project's first commit (SIP-0112 E.4.6): its blueprint's layout, rendered
    from the approved interface manifest, pushed to the empty branch you made for it, never
    forced. Then validate it as any registered product."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    body = {"manifest": manifest.read_text(), "idempotency_key": key}
    if token_from_gh:
        body["token"] = _gh_token()
    try:
        client = _get_client(ctx)
        data = client.post(f"/api/v1/projects/{project_id}/initializations", json=body)
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e
    if fmt == "json":
        print_json(data)
        return
    initialization = data["initialization"]
    print_detail({k: v for k, v in initialization.items() if k != "files"})
    again = " (already initialized)" if data.get("replayed") else ""
    print_success(
        f"{initialization['branch']} at {initialization['commit'][:12]}: "
        f"{len(initialization['files'])} files of the {initialization['stack']} blueprint{again}. "
        f"Next: squadops projects validate {project_id}"
    )


def _gh_token() -> str:
    """The caller's own GitHub token, from the GitHub CLI's login. Never printed."""
    import subprocess

    try:
        done = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print_error(f"--token-from-gh needs the GitHub CLI logged in: {type(e).__name__}")
        raise typer.Exit(code=2) from e
    token = done.stdout.strip()
    if done.returncode != 0 or not token:
        print_error("--token-from-gh: `gh auth token` gave no token; run `gh auth login` first")
        raise typer.Exit(code=2)
    return token


@app.command("sync")
def sync(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    token_from_gh: bool = typer.Option(
        False,
        "--token-from-gh",
        help="Read review requests' state with your own GitHub access (`gh auth token`)",
    ),
    idempotency_key: str | None = typer.Option(None, "--idempotency-key"),
):
    """Read a Project's upstream against its approved development baseline (SIP-0112 FR-21):
    what changed, by the evidence it invalidates, and where each pending contribution stands.
    Moves nothing: `projects validate` advances the baseline, then configure and baseline."""
    fmt = ctx.obj.get("format", "table") if ctx.obj else "table"
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    try:
        client = _get_client(ctx)
        body = {"idempotency_key": key, **({"token": _gh_token()} if token_from_gh else {})}
        data = client.post(f"/api/v1/projects/{project_id}/syncs", json=body)
        client.close()
    except CLIError as e:
        print_error(f"{e} (idempotency key {key})")
        raise typer.Exit(code=e.exit_code) from e
    if fmt == "json":
        print_json(data)
        return
    document = data["document"]
    drift = document.get("drift")
    if drift is None:
        print_success(f"{project_id} upstream is its baseline, {document['baseline_commit'][:12]}")
    else:
        rows = [[c, len(paths), ", ".join(paths[:4])] for c, paths in drift["changed"].items()]
        # #2606: what SquadOps's own integrated contributions account for, apart (v1 has none)
        rows += [
            [f"{c}, by {i['cycle_id']}", len(paths), ", ".join(paths[:4])]
            for i in drift.get("integrated", [])
            for c, paths in i["changed"].items()
        ]
        print_table(["Changed", "Paths", "First paths"], rows, quiet=False)
        relevant = ", ".join(drift["relevant"]) or "none beyond source"
        print_success(
            f"{project_id} upstream {document['upstream_commit'][:12]} is past its baseline "
            f"{document['baseline_commit'][:12]}; evidence to revalidate: {relevant}"
        )
    for c in document["contributions"]:
        where = c["integrated_commit"] or c["review_url"] or ""
        print_success(f"contribution {c['cycle_id']}/{c['run_id']}: {c['state']} {where}")

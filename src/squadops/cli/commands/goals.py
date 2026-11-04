"""A Project's goal set (SIP-0115 §8.2, slice 1, #2884): show it, edit it, read its history.

``show`` prints the goal set as YAML, its revision's provenance as comments above it, so
``squadops goals show <project> > goals.yaml`` is a file ``goals edit`` takes back as the next
revision. Each edit, a reorder included, writes a revision; none is changed in place.

**The file carries the revision it was shown at** (``# base-revision: N``), and ``edit`` writes
against that revision, never against whatever is active when it runs: an export from revision 1
submitted after someone else wrote revision 2 is refused as stale, not written over it (the second
review of PR #2899). A file without the line needs ``--expected-revision``.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import typer
import yaml

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


#: The line ``show`` writes and ``edit`` reads: the revision the file was shown at.
_BASE = re.compile(r"^# base-revision: (\d+)\s*$", re.M)


def _comment(label: str, value: object) -> list[str]:
    """``value`` as comment lines, every line of it: a reason or link with a newline in it must
    not leave a line of plain text above the document, which YAML would read (or refuse)."""
    text = str(value).splitlines() or [""]
    return [f"# {label}: {text[0]}", *(f"#   {line}" for line in text[1:])]


def _header(data: dict) -> str:
    """The revision's provenance as YAML comments: kept on screen, ignored when read back, apart
    from ``# base-revision``, which ``edit`` reads."""
    lines = [
        f"# base-revision: {int(data['revision'])}",
        *_comment("goal set of", data["project_id"]),
        *_comment("written by", f"{data['author']} at {data['created_at']}"),
        *_comment("reason", data["reason"]),
    ]
    if data.get("source_ref"):
        lines += _comment("source", data["source_ref"])
    return "\n".join(lines)


def _base_revision(text: str) -> int | None:
    """The revision a file from ``show`` was shown at, or ``None`` for a file written by hand."""
    found = _BASE.findall(text)
    return int(found[0]) if len(found) == 1 else None


@app.command("edit")
def edit(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ..., "--file", "-f", help="The goal set, YAML or JSON (the shape `goals show` prints)"
    ),
    reason: str = typer.Option(..., "--reason", help="Why this revision is written"),
    expected_revision: int | None = typer.Option(
        None,
        "--expected-revision",
        help="The revision this edit replaces (0 for the first). Default: the file's "
        "`# base-revision` line, as `goals show` writes it",
    ),
    source_ref: str | None = typer.Option(
        None, "--source-ref", help="Where the change came from: a conversation's or issue's link"
    ),
    idempotency_key: str | None = typer.Option(
        None, "--idempotency-key", help="Resend the printed key to retry safely"
    ),
):
    """Write a Project's next goal-set revision from a file. Every edit, a reorder included, is a
    new revision with its reason. It is written against the revision the file was shown at, so a
    concurrent edit is refused, never overwritten; a retry with the printed key and the same file
    replays."""
    try:
        text = file.read_text()
        goal_set = _as_written(yaml.safe_load(text))
    except (OSError, yaml.YAMLError) as e:
        print_error(f"cannot read {file}: {e}")
        raise typer.Exit(code=2) from e
    if not isinstance(goal_set, dict):
        print_error(f"{file} holds no goal set: a mapping with `goal`, `backlog` and the rest")
        raise typer.Exit(code=2)
    shown_at = _base_revision(text)
    if expected_revision is None:
        expected_revision = shown_at
    elif shown_at is not None and shown_at != expected_revision:
        print_error(
            f"{file} was shown at revision {shown_at}, and --expected-revision says "
            f"{expected_revision}: say which revision this edit replaces"
        )
        raise typer.Exit(code=2)
    if expected_revision is None:
        print_error(
            f"{file} names no revision it replaces: pass --expected-revision (0 for the first), "
            "or start from `squadops goals show`, which writes it"
        )
        raise typer.Exit(code=2)
    key = idempotency_key or f"cli-{uuid.uuid4().hex}"
    try:
        client = _get_client(ctx)
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
        # A retry must resend the same request to replay it: the key, against the same revision.
        print_error(f"{e} (idempotency key {key}, expected revision {expected_revision})")
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


def _as_written(value: Any) -> Any:
    """The file's values as JSON carries them. YAML reads an unquoted ``found_at`` as a time,
    which the request can't encode; its ISO form is what the server reads."""
    if isinstance(value, dict):
        return {k: _as_written(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_as_written(v) for v in value]
    if isinstance(value, date):  # a datetime is a date
        return value.isoformat()
    return value


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

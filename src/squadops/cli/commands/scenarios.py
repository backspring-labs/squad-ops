"""``squadops scenarios``: Outcome Evaluation's held-out suites (SIP-0113 §4.1; the 2.4 plan's D2).

The supervisor drafts a suite from a file (``draft``); the owner reads its full content
(``review``) and approves it (``approve``). A suite is content-addressed, so approving a digest
approves exactly the content reviewed under it. ``list`` and ``show`` give goals and surfaces only,
never steps or checks.

A suite's file is held out: it never lives in a repository the squad's images or prompts are built
from, so ``draft`` refuses one inside a Git working tree.
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path

import typer
import yaml

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_error, print_json, print_success, print_table

app = typer.Typer(
    name="scenarios", help="Outcome Evaluation's held-out suites: draft, review, approve"
)

_BASE = "/api/v1/scenario-suites"


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


def _working_tree(path: Path) -> Path | None:
    """The Git working tree holding ``path``, if any."""
    for parent in (path.resolve().parent, *path.resolve().parents):
        if (parent / ".git").exists():
            return parent
    return None


def _suite_file(path: Path) -> dict:
    tree = _working_tree(path)
    if tree is not None:
        print_error(
            f"{path} is inside the Git working tree {tree}: a held-out suite lives outside every "
            "repository, so it can't be committed into what the squad is built from"
        )
        raise typer.Exit(code=2)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        print_error(f"{path}: {e}")
        raise typer.Exit(code=2) from e
    if not isinstance(data, dict):
        print_error(f"{path}: expected a mapping with a name and its scenarios")
        raise typer.Exit(code=2)
    return data


def _summary_rows(suite: dict) -> list[list[str]]:
    return [
        [
            s["scenario_id"],
            s["version"][:12],
            s["goal"],
            ", ".join(
                f"{x['kind']} {x.get('method') or ''} {x['path']}".replace("  ", " ")
                for x in s["surfaces"]
            ),
        ]
        for s in suite.get("scenarios", [])
    ]


@app.command("draft")
def draft(
    ctx: typer.Context,
    file: Path = typer.Option(..., "--file", "-f", help="The suite: a name and its scenarios"),
):
    """Draft a suite (the supervisor's, D2). The same content again replays its draft."""
    suite = _suite_file(file)
    data = _call(ctx, "post", _BASE, json=suite)
    if _json(ctx):
        print_json(data)
        return
    print_success(
        f"drafted {data['name']}: {data['digest']} ({data['state']}, {len(data['scenarios'])} scenarios)"
    )


@app.command("list")
def list_suites(ctx: typer.Context):
    """Every suite, with its state: goals and surfaces only."""
    data = _call(ctx, "get", _BASE)
    if _json(ctx):
        print_json(data)
        return
    rows = [
        [
            d["digest"][:16],
            d["name"],
            d["state"],
            str(len(d["scenarios"])),
            d["drafted_by"],
            d.get("approved_by") or "",
        ]
        for d in data
    ]
    print_table(["Digest", "Name", "State", "Scenarios", "Drafted by", "Approved by"], rows)


@app.command("show")
def show(ctx: typer.Context, digest: str = typer.Argument(...)):
    """One suite's goals and surfaces, never its steps or checks."""
    data = _call(ctx, "get", f"{_BASE}/{digest}")
    if _json(ctx):
        print_json(data)
        return
    print_success(f"{data['name']}: {data['digest']} ({data['state']})")
    print_table(["Scenario", "Version", "Goal", "Surfaces"], _summary_rows(data))


@app.command("review")
def review(ctx: typer.Context, digest: str = typer.Argument(...)):
    """The suite's full content, held-out steps included: the owner's review before approving."""
    data = _call(ctx, "get", f"{_BASE}/{digest}/content")
    if _json(ctx):
        print_json(data)
        return
    typer.echo(f"# {data['digest']} ({data['state']})")
    typer.echo(yaml.safe_dump(data["content"], sort_keys=False, allow_unicode=True))


@app.command("approve")
def approve(ctx: typer.Context, digest: str = typer.Argument(...)):
    """Approve the suite with this digest (the owner's, D2): exactly the content ``review`` shows."""
    data = _call(ctx, "post", f"{_BASE}/{digest}/approval")
    if _json(ctx):
        print_json(data)
        return
    print_success(f"approved {data['name']}: {data['digest']} by {data['approved_by']}")


#: SIP-0113 §10p ruling 8 (#2564): an evaluation's page evidence.
_EVALUATIONS = "/api/v1/scenario-evaluations"


@app.command("evidence")
def evidence(
    ctx: typer.Context,
    evaluation_id: str = typer.Argument(...),
    out: Path = typer.Option(..., "--out", help="A directory outside every repository"),
):
    """An evaluation's page evidence (the owner's, ``scenarios:approve``), written under ``--out``:
    a directory per scenario, with its screenshot and its details. Refused inside a Git working
    tree: a screenshot shows the scenario's held-out values, and evidence written into a checkout's
    ``var/`` would reach the line's public Release with its records."""
    tree = _working_tree(out / "evidence")
    if tree is not None:
        print_error(
            f"{out} is inside the Git working tree {tree}: evidence shows held-out values, so it "
            "is written outside every repository"
        )
        raise typer.Exit(code=2)
    data = _call(ctx, "get", f"{_EVALUATIONS}/{evaluation_id}/evidence")
    written = []
    for item in data:
        where = out / item["scenario_id"]
        where.mkdir(parents=True, exist_ok=True)
        stem = where / f"step-{item['step']}"
        if item.get("png_b64"):
            try:
                stem.with_suffix(".png").write_bytes(
                    base64.b64decode(item["png_b64"], validate=True)
                )
            except (binascii.Error, ValueError):
                print_error(f"{item['scenario_id']}: its screenshot isn't base64; not written")
        details = {k: v for k, v in item.items() if k != "png_b64"}
        stem.with_suffix(".json").write_text(json.dumps(details, indent=2), encoding="utf-8")
        written.append(str(stem))
    if _json(ctx):
        print_json({"evaluation_id": evaluation_id, "written": written})
        return
    print_success(f"{len(data)} scenarios' evidence written under {out}")


@app.command("purge-evidence")
def purge_evidence(
    ctx: typer.Context,
    before: str = typer.Option(..., "--before", help="ISO time: the line's cut, e.g. the tag's"),
):
    """Cut step 8 (§10p ruling 8): delete the page evidence of every evaluation made before
    ``--before``, and print the count for ``worktree_hygiene.py --evidence-purged``."""
    data = _call(ctx, "post", f"{_EVALUATIONS}/evidence/purge", json={"before": before})
    if _json(ctx):
        print_json(data)
        return
    print_success(f"purged {data['purged']} scenarios' evidence from before {data['before']}")

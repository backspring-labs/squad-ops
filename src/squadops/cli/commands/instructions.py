"""``squadops instructions``: task instructions, an operator's directive for selected tasks of one
cycle (SIP-0110 Appendix A §3.5; #2178).

``add`` gives one to an existing cycle: an intervention, since the cycle is already admitted.
It is refused once a task it selects has dispatched. A run hands every task its inputs when it is
provisioned, so in practice that is before the run that holds them starts: a later workload, after
the gate between workloads. For a campaign's cycle it is a row in the campaign's control log. ``list`` shows a cycle's instructions, each marked admitted (given with the
cycle's create request) or added after admission.
"""

from __future__ import annotations

import typer

from squadops.cli.client import CLIError
from squadops.cli.client import get_client as _get_client
from squadops.cli.output import print_error, print_json, print_success, print_table

app = typer.Typer(name="instructions", help="Task instructions: give one to a cycle, list them")


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


@app.command("add")
def add(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    text: str = typer.Argument(..., help="The instruction"),
    cycle_id: str = typer.Option(..., "--cycle", help="The cycle it directs"),
    task_types: list[str] = typer.Option(..., "--for", help="A task type it reaches; repeatable"),
    carry: bool = typer.Option(
        False,
        "--carry",
        help="It also reaches a campaign's repair or retry of the cycle (carries_into: "
        "continuations), each with its own copy",
    ),
):
    """Give a cycle's selected tasks an instruction, before the run that holds them starts."""
    data = _call(
        ctx,
        "post",
        "/api/v1/memory-records",
        json={
            "kind": "instruction",
            "scope": "task",
            "project_id": project_id,
            "body": text,
            "target": {
                "cycle_id": cycle_id,
                "task_types": task_types,
                **({"carries_into": "continuations"} if carry else {}),
            },
        },
    )
    if _json(ctx):
        print_json(data)
        return
    print_success(
        f"{data['record_id']}: reaches {', '.join(task_types)} of {cycle_id}, from its next "
        "dispatch. An intervention: set the cycle's measurement apart"
    )
    if data.get("control_log_entry_id"):
        print_success(f"recorded in the campaign's control log as {data['control_log_entry_id']}")


@app.command("list")
def list_instructions(
    ctx: typer.Context,
    project_id: str = typer.Argument(...),
    cycle_id: str = typer.Option(..., "--cycle", help="The cycle whose instructions to show"),
):
    """A cycle's task instructions, each admitted with the cycle or added after."""
    records = _call(ctx, "get", "/api/v1/memory-records", params={"project_id": project_id})
    mine = [
        r
        for r in records
        if r["scope"] == "task" and (r["current"].get("target") or {}).get("cycle_id") == cycle_id
    ]
    if _json(ctx):
        print_json(mine)
        return
    print_table(
        ["Record", "Revision", "Tasks", "Given", "Text"],
        [
            [
                r["record_id"],
                str(r["current"]["number"]),
                ", ".join(r["current"]["target"]["task_types"]),
                "admitted" if r["current"]["source"]["kind"] == "cycle_request" else "added after",
                r["current"]["body"],
            ]
            for r in mine
        ],
    )

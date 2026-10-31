"""``squadops instructions`` (SIP-0110 Appendix A §3.5; #2178): a task instruction given to a cycle,
from the CLI to the records route.

What bugs would these catch? An instruction sent without its cycle or with only the first of
several task types; a refusal (its task already dispatched) reported as saved; a list that mixes
another cycle's instructions in, or reads one added after admission as admitted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.client import CLIError
from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()


@patch("squadops.cli.commands.instructions._get_client")
def test_add_sends_the_cycle_and_every_task_type(mock_get_client):
    client = MagicMock()
    client.post.return_value = {"record_id": "mrec_1", "control_log_entry_id": "ent_9"}
    mock_get_client.return_value = client

    result = runner.invoke(
        app,
        ["instructions", "add", "group_run", "Cover the empty list.", "--cycle", "cyc_1",
         "--for", "qa.test", "--for", "development.develop"],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert client.post.call_args.kwargs["json"] == {
        "kind": "instruction", "scope": "task", "project_id": "group_run",
        "body": "Cover the empty list.",
        "target": {"cycle_id": "cyc_1", "task_types": ["qa.test", "development.develop"]},
    }  # fmt: skip
    said = " ".join(result.output.split())
    assert "mrec_1" in said and "control log as ent_9" in said


@patch("squadops.cli.commands.instructions._get_client")
def test_a_refused_instruction_exits_with_the_refusal(mock_get_client):
    client = MagicMock()
    client.post.side_effect = CLIError("run_1 t_qa already dispatched", exit_code=1)
    mock_get_client.return_value = client

    result = runner.invoke(
        app, ["instructions", "add", "group_run", "x", "--cycle", "cyc_1", "--for", "qa.test"]
    )

    assert result.exit_code == 1
    assert "already dispatched" in " ".join(result.output.split())


def _record(record_id: str, cycle_id: str, source: str, scope: str = "task") -> dict:
    return {
        "record_id": record_id, "scope": scope,
        "current": {"number": 1, "body": f"text of {record_id}", "source": {"kind": source},
                    "target": {"cycle_id": cycle_id, "task_types": ["qa.test"]}},
    }  # fmt: skip


@patch("squadops.cli.commands.instructions._get_client")
def test_list_shows_only_the_cycles_instructions_each_marked_how_it_was_given(mock_get_client):
    client = MagicMock()
    client.get.return_value = [
        _record("mrec_admitted", "cyc_1", "cycle_request"),
        _record("mrec_added", "cyc_1", "api_call"),
        _record("mrec_other", "cyc_2", "api_call"),
    ]
    mock_get_client.return_value = client

    result = runner.invoke(app, ["instructions", "list", "group_run", "--cycle", "cyc_1"])

    assert result.exit_code == 0, result.output
    rows = {line.split()[1]: line for line in result.output.splitlines() if "mrec_" in line}
    assert set(rows) == {"mrec_admitted", "mrec_added"}
    assert "admitted" in rows["mrec_admitted"] and "added after" in rows["mrec_added"]


@patch("squadops.cli.commands.instructions._get_client")
def test_carry_sends_carries_into_continuations(mock_get_client):
    """§3.7. Bug caught: --carry accepted and not sent, so a repair of the cycle runs without the
    instruction its operator asked to carry."""
    client = MagicMock()
    client.post.return_value = {"record_id": "mrec_1"}
    mock_get_client.return_value = client

    result = runner.invoke(
        app,
        ["instructions", "add", "group_run", "x", "--cycle", "cyc_1", "--for", "qa.test",
         "--carry"],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert client.post.call_args.kwargs["json"]["target"]["carries_into"] == "continuations"

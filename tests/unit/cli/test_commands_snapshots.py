"""``squadops snapshots`` (SIP-0110 Appendix A §3.7; #2179): a unit's binding and its re-binding,
from the CLI to the routes.

What bugs would these catch? A re-binding sent to the wrong unit or without its reason; an answer
that doesn't say which revision was replaced and what follows, so the operator doesn't know the
measurements are set apart; a refusal (a run still running) reported as success.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.client import CLIError
from squadops.cli.main import app

pytestmark = [pytest.mark.domain_cli]

runner = CliRunner()

_REBOUND = {
    "unit_kind": "campaign", "unit_id": "cmp_1", "snapshot_id": "snap_1",
    "instructions": [{"record_id": "mrec_a", "revision": 2}], "instructions_unread": None,
    "rebindings": [{
        "record_id": "mrec_a", "replaced": {"revision": 1}, "replacement": {"revision": 2},
        "by": "ada", "at": "2026-10-20T12:00:00+00:00", "why": "clarified",
    }],
    "next": "the campaign's later dispatches bind revision 2 of mrec_a. Its measurements are set apart",
}  # fmt: skip


@patch("squadops.cli.commands.snapshots._get_client")
def test_a_rebinding_names_its_unit_and_reason_and_says_what_it_replaced(mock_get_client):
    client = MagicMock()
    client.post.return_value = _REBOUND
    mock_get_client.return_value = client

    result = runner.invoke(
        app,
        ["snapshots", "rebind", "group_run", "campaign", "cmp_1", "--record", "mrec_a",
         "--why", "clarified"],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert client.post.call_args.args[0] == (
        "/api/v1/projects/group_run/snapshots/campaign/cmp_1/rebindings"
    )
    assert client.post.call_args.kwargs["json"] == {"record_id": "mrec_a", "why": "clarified"}
    said = " ".join(result.output.split())  # the console wraps long lines
    assert "re-bound mrec_a from revision 1 to revision 2" in said
    assert "measurements are set apart" in said


@patch("squadops.cli.commands.snapshots._get_client")
def test_a_refused_rebinding_exits_with_the_refusal(mock_get_client):
    client = MagicMock()
    client.post.side_effect = CLIError("run_1 was handed the revision being replaced", exit_code=1)
    mock_get_client.return_value = client

    result = runner.invoke(
        app, ["snapshots", "rebind", "group_run", "cycle", "cyc_1", "--record", "m", "--why", "x"]
    )

    assert result.exit_code == 1
    assert "run_1 was handed the revision being replaced" in " ".join(result.output.split())

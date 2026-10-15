"""The CLI pages the runs, artifacts and campaigns lists as it pages the cycles list (#1976).

What bugs would these catch? A list command that asks for no page and shows the route's default
50 as if it were the whole list; one that says nothing when a page is full; and the CLI's limits
drifting from the API's, so a ``--limit`` the CLI accepts is refused with a 422.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli.main import app

runner = CliRunner()


def _client(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get.return_value = rows
    return client


_RUN = {"run_id": "run_1", "run_number": 1, "status": "completed", "started_at": None}
_ARTIFACT = {"artifact_id": "art_1", "artifact_type": "source", "filename": "a.py", "size_bytes": 1}
_CAMPAIGN = {"campaign_id": "cmp_1", "state": "completed", "outcome": "success", "updated_at": "t"}


@pytest.mark.parametrize(
    ("module", "argv", "row", "path", "params"),
    [
        (
            "runs",
            ["runs", "list", "p", "cyc_1"],
            _RUN,
            "/api/v1/projects/p/cycles/cyc_1/runs",
            {},
        ),
        (
            "artifacts",
            ["artifacts", "list", "--project", "p"],
            _ARTIFACT,
            "/api/v1/projects/p/artifacts",
            {},
        ),
        (
            "artifacts",
            ["artifacts", "list", "--project", "p", "--cycle", "cyc_1", "--run", "run_1"],
            _ARTIFACT,
            "/api/v1/projects/p/cycles/cyc_1/runs/run_1/artifacts",
            {},
        ),
        (
            "campaigns",
            ["campaigns", "list", "--project", "p"],
            _CAMPAIGN,
            "/api/v1/campaigns",
            {"project_id": "p"},
        ),
    ],
    ids=["runs", "project-artifacts", "run-artifacts", "campaigns"],
)
@pytest.mark.parametrize("shown", [2, 1], ids=["full-page", "last-page"])
def test_a_list_asks_for_its_page_and_says_when_it_is_full(module, argv, row, path, params, shown):
    client = _client([row] * shown)
    with patch(f"squadops.cli.commands.{module}._get_client", return_value=client):
        result = runner.invoke(app, [*argv, "--limit", "2", "--offset", "4"])

    assert result.exit_code == 0, result.output
    call = client.get.call_args
    assert (call.args[0], call.kwargs["params"]) == (path, {**params, "limit": 2, "offset": 4})
    assert ("2 shown; there may be more: --offset 6" in result.output) is (shown == 2)


def test_the_clis_limits_are_the_apis():
    from squadops.api import paging as api
    from squadops.cli import paging as cli

    assert (cli.DEFAULT_LIMIT, cli.MAX_LIMIT) == (api.DEFAULT_LIMIT, api.MAX_LIMIT)

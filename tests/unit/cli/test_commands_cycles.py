"""
Unit tests for cycle commands (SIP-0065 §6.3).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app
from squadops.cycles.lifecycle import compute_config_hash

runner = CliRunner()


def _mock_client(get_val=None, post_val=None):
    mock = MagicMock()
    if get_val is not None:
        mock.get.return_value = get_val
    if post_val is not None:
        mock.post.return_value = post_val
    return mock


class TestCyclesCreate:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_default_profile(self, mock_get_client):
        """cycles create with no --request-profile sends the operator's minimal one, ``smoke``
        (#316: ``default`` stays, frozen, and is no longer the CLI's choice)."""
        from squadops.contracts.cycle_request_profiles import load_profile

        crp = load_profile("smoke")
        expected_hash = compute_config_hash(crp.defaults, {})

        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "cyc_abc",
                "run_id": "run_xyz",
                "status": "queued",
                "resolved_config_hash": expected_hash,
            }
        )

        result = runner.invoke(
            app, ["cycles", "create", "hello_squad", "--squad-profile", "default_v1"]
        )
        assert result.exit_code == 0
        assert "cyc_abc" in result.output

        # Verify the POST body
        call_args = mock_get_client.return_value.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["squad_profile_id"] == "default_v1"
        assert body["applied_defaults"] == crp.defaults
        assert body["execution_overrides"] == {}

    @patch("squadops.cli.commands.cycles._get_client")
    def test_benchmark_profile(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": "abc123",
            }
        )

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--request-profile",
                "benchmark",
            ],
        )
        assert result.exit_code == 0

        body = mock_get_client.return_value.post.call_args.kwargs.get(
            "json"
        ) or mock_get_client.return_value.post.call_args[1].get("json")
        assert body["experiment_context"].get("benchmark") is True

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ('["art_d4b1402e61a1"]', ["art_d4b1402e61a1"]),
            ('{"a": 1}', {"a": 1}),
            ("art_plain", "art_plain"),
        ],
        ids=["list", "mapping", "string-unchanged"],
    )
    @patch("squadops.cli.commands.cycles._get_client")
    def test_a_list_or_mapping_value_reaches_the_overrides_as_data(
        self, mock_get_client, value, expected
    ):
        """#2496: a list kept as its string made the plan loader iterate characters, so an
        operator-supplied plan was never found."""
        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "c",
                "run_id": "r",
                "status": "queued",
                "resolved_config_hash": "x",
            }
        )

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--set",
                f"plan_artifact_refs={value}",
            ],
        )

        assert result.exit_code == 0, result.output
        body = mock_get_client.return_value.post.call_args.kwargs["json"]
        assert body["execution_overrides"]["plan_artifact_refs"] == expected

    def test_a_value_that_looks_structured_but_isnt_json_is_refused(self):
        result = runner.invoke(
            app,
            ["cycles", "create", "proj1", "--squad-profile", "sp1", "--set", "refs=[art_1"],
            env={"COLUMNS": "200"},  # Rich wraps the error box at the console's width (#2491)
        )

        assert result.exit_code != 0
        assert "isn't valid JSON" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_set_override(self, mock_get_client):
        """--set puts value in execution_overrides when it differs from default."""
        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": "x",
            }
        )

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--set",
                "build_strategy=incremental",
            ],
        )
        assert result.exit_code == 0

        body = mock_get_client.return_value.post.call_args.kwargs.get(
            "json"
        ) or mock_get_client.return_value.post.call_args[1].get("json")
        assert body["execution_overrides"]["build_strategy"] == "incremental"
        assert body["build_strategy"] == "incremental"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_hash_round_trip(self, mock_get_client):
        """Local hash matches server response hash."""
        from squadops.contracts.cycle_request_profiles import (
            compute_overrides,
            load_profile,
            merge_config,
        )

        crp = load_profile("smoke")
        user_vals = {"build_strategy": "incremental"}
        merged = merge_config(crp.defaults, user_vals)
        overrides = compute_overrides(crp.defaults, merged)
        expected_hash = compute_config_hash(crp.defaults, overrides)

        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": expected_hash,
            }
        )

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--set",
                "build_strategy=incremental",
            ],
        )
        assert result.exit_code == 0
        # No hash mismatch warning in output
        assert "mismatch" not in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_a_stacks_defaults_are_in_the_local_hash(self, mock_get_client):
        """#316 (R2.3): ``validate`` on a stack sends the stack's request defaults in its applied
        defaults. Bug caught: the CLI hashing the profile's defaults alone, so every create on a
        stack warns of a hash mismatch the server never had."""
        from squadops.contracts.cycle_request_profiles import cycle_request_body

        stack = {"build_profile": "nextjs_ts", "development_profile": "nextjs_ts"}
        sent = cycle_request_body("validate", squad_profile_id="sp1", user_values=stack)
        server_hash = compute_config_hash(sent["applied_defaults"], sent["execution_overrides"])
        mock_get_client.return_value = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": server_hash,
            }
        )

        result = runner.invoke(
            app,
            ["cycles", "create", "proj1", "--squad-profile", "sp1", "--request-profile",
             "validate", "--set", "build_profile=nextjs_ts", "--set", "development_profile=nextjs_ts"],
        )  # fmt: skip

        assert result.exit_code == 0
        assert "mismatch" not in result.output
        body = mock_get_client.return_value.post.call_args.kwargs["json"]
        assert body["applied_defaults"]["time_budget_seconds"] == 10800

    @patch("squadops.cli.commands.cycles._get_client")
    def test_not_found(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "nonexistent",
                "--squad-profile",
                "sp1",
            ],
        )
        assert result.exit_code == exit_codes.NOT_FOUND

    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_file_auto_ingests(self, mock_get_client, tmp_path):
        """--prd with a file path auto-ingests via upload and uses returned artifact ID."""
        prd_file = tmp_path / "prd.md"
        prd_file.write_text("# My PRD\nSome content")

        mock_client = _mock_client(
            post_val={
                "cycle_id": "cyc_prd",
                "run_id": "run_prd",
                "status": "queued",
                "resolved_config_hash": "abc",
            }
        )
        mock_client.upload.return_value = {"artifact_id": "art_prd_123"}
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--prd",
                str(prd_file),
            ],
        )
        assert result.exit_code == 0

        # Verify upload was called with correct args
        upload_call = mock_client.upload.call_args
        assert "/artifacts/ingest" in upload_call[0][0]
        assert upload_call.kwargs["fields"]["artifact_type"] == "prd"

        # Verify the POST body uses the returned artifact ID
        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "art_prd_123"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_artifact_id(self, mock_get_client):
        """--prd with an artifact ID passes it through without upload."""
        mock_client = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": "abc",
            }
        )
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--prd",
                "art_existing",
            ],
        )
        assert result.exit_code == 0

        # No upload call
        mock_client.upload.assert_not_called()

        # Verify body has the artifact ID as-is
        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "art_existing"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_create_with_prd_file_not_found(self, mock_get_client):
        """--prd with a nonexistent file path treats it as an artifact ID."""
        mock_client = _mock_client(
            post_val={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "status": "queued",
                "resolved_config_hash": "abc",
            }
        )
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "proj1",
                "--squad-profile",
                "sp1",
                "--prd",
                "/nonexistent/prd.md",
            ],
        )
        assert result.exit_code == 0

        # No upload — treated as artifact ID
        mock_client.upload.assert_not_called()

        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body["prd_ref"] == "/nonexistent/prd.md"


class TestCyclesList:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_list(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {
                    "cycle_id": "cyc_1",
                    "status": "active",
                    "build_strategy": "fresh",
                    "created_at": "2026-01-01",
                },
            ]
        )
        result = runner.invoke(app, ["cycles", "list", "proj1"])
        assert result.exit_code == 0
        assert "cyc_1" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_list_with_status(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=[])
        result = runner.invoke(app, ["cycles", "list", "proj1", "--status", "active"])
        assert result.exit_code == 0

        call_args = mock_get_client.return_value.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["status"] == "active"

    @patch("squadops.cli.commands.cycles._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val=[
                {"cycle_id": "cyc_1", "status": "active"},
            ]
        )
        result = runner.invoke(app, ["--json", "cycles", "list", "proj1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestCyclesShow:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_show(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            get_val={
                "cycle_id": "cyc_1",
                "project_id": "proj1",
                "status": "active",
            }
        )
        result = runner.invoke(app, ["cycles", "show", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "cyc_1" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_show_renders_workload_progress_table(self, mock_get_client):
        """cycles show renders workload_progress as a dedicated sub-table."""
        mock_get_client.return_value = _mock_client(
            get_val={
                "cycle_id": "cyc_1",
                "project_id": "proj1",
                "status": "active",
                "workload_progress": [
                    {
                        "index": 0,
                        "workload_type": "framing",
                        "status": "completed",
                        "run_id": "run_001",
                    },
                    {
                        "index": 1,
                        "workload_type": "implementation",
                        "status": "running",
                        "run_id": "run_002",
                    },
                    {
                        "index": 2,
                        "workload_type": "wrapup",
                        "status": "pending",
                        "run_id": None,
                    },
                ],
            }
        )
        result = runner.invoke(app, ["cycles", "show", "proj1", "cyc_1"])
        assert result.exit_code == 0
        # Sub-table renders workload types and statuses
        assert "framing" in result.output
        assert "implementation" in result.output
        assert "wrapup" in result.output
        assert "Workload Progress" in result.output
        # Raw nested dict is NOT in output (workload_progress popped before print_detail)
        assert "workload_progress" not in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_show_no_workload_progress(self, mock_get_client):
        """cycles show without workload_progress does not render sub-table."""
        mock_get_client.return_value = _mock_client(
            get_val={
                "cycle_id": "cyc_1",
                "project_id": "proj1",
                "status": "active",
            }
        )
        result = runner.invoke(app, ["cycles", "show", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "Workload Progress" not in result.output


class TestCyclesCancel:
    @patch("squadops.cli.commands.cycles._get_client")
    def test_cancel(self, mock_get_client):
        mock_get_client.return_value = _mock_client(post_val={"status": "cancelled"})
        result = runner.invoke(app, ["cycles", "cancel", "proj1", "cyc_1"])
        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("squadops.cli.commands.cycles._get_client")
    def test_cancel_conflict(self, mock_get_client):
        mock = MagicMock()
        mock.post.side_effect = CLIError("conflict", exit_codes.CONFLICT)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["cycles", "cancel", "proj1", "cyc_1"])
        assert result.exit_code == exit_codes.CONFLICT


class TestCyclesRate:
    """`squadops cycles rate` (SIP-0109 §11a; #1804): the reference proposal's rating."""

    @patch("squadops.cli.commands.cycles._get_client")
    def test_the_rating_file_reaches_the_route_as_written(self, mock_get_client, tmp_path):
        """Bug caught: the file's fields dropped or renamed on the way to the route, so the
        rating stored is not the one the supervisor wrote."""
        rating = {
            "content_hash": "04927a47",
            "verdict": "would_return",
            "reason": "the footprint reaches past the change",
            "ratings": {
                "scope_fit": {"score": 3, "note": "fits"},
                "criteria_discriminability": {"score": 2, "note": "T3 is loose"},
                "footprint_size": {"score": 1, "note": "touches the list view"},
            },
        }
        path = tmp_path / "rating.yaml"
        path.write_text(json.dumps(rating))
        mock_get_client.return_value = _mock_client(
            post_val={
                "artifact_id": "art_r1",
                "proposal_id": "prop_1",
                "version": 1,
                "verdict": "would_return",
            }
        )

        result = runner.invoke(
            app, ["cycles", "rate", "group_run", "cyc_p", "--rating-file", str(path)]
        )

        assert result.exit_code == 0, result.output
        assert "Rated prop_1 v1: would_return (art_r1)" in result.output
        call = mock_get_client.return_value.post.call_args
        assert call.args[0] == "/api/v1/projects/group_run/cycles/cyc_p/proposal-rating"
        assert call.kwargs["json"] == rating

    @patch("squadops.cli.commands.cycles._get_client")
    def test_an_unreadable_file_is_refused_before_any_request(self, mock_get_client, tmp_path):
        path = tmp_path / "rating.yaml"
        path.write_text("- a list, not a rating\n")

        result = runner.invoke(
            app, ["cycles", "rate", "group_run", "cyc_p", "--rating-file", str(path)]
        )

        assert result.exit_code == exit_codes.VALIDATION_ERROR
        mock_get_client.return_value.post.assert_not_called()


class TestCyclesListPages:
    """#1891: `cycles list` ended silently at the API's newest 50."""

    @staticmethod
    def _page(n: int) -> list[dict]:
        return [
            {"cycle_id": f"cyc_{i}", "status": "failed", "build_strategy": "fresh"}
            for i in range(n)
        ]

    @patch("squadops.cli.commands.cycles._get_client")
    def test_a_full_page_says_there_may_be_more(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=self._page(10))

        result = runner.invoke(
            app,
            ["cycles", "list", "p", "--status", "failed", "--limit", "10", "--offset", "20"],
        )

        assert result.exit_code == 0, result.output
        assert "10 shown; there may be more: --offset 30" in result.output
        call = mock_get_client.return_value.get.call_args
        assert call.kwargs["params"] == {"limit": 10, "offset": 20, "status": "failed"}

    @patch("squadops.cli.commands.cycles._get_client")
    def test_a_short_page_is_the_end(self, mock_get_client):
        mock_get_client.return_value = _mock_client(get_val=self._page(3))

        result = runner.invoke(app, ["cycles", "list", "p", "--limit", "10"])

        assert result.exit_code == 0, result.output
        assert "there may be more" not in result.output

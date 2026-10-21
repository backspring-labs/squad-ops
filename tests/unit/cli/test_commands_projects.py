"""
Unit tests for project commands (SIP-0065 §6.3).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import CLIError
from squadops.cli.main import app

runner = CliRunner()


def _mock_client(return_value):
    """Patch APIClient to return a mock with fixed get/post return values."""
    mock = MagicMock()
    mock.get.return_value = return_value
    return mock


class TestProjectsList:
    @patch("squadops.cli.commands.projects._get_client")
    def test_table_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            [
                {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test project"},
            ]
        )
        result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0
        assert "hello_squad" in result.output

    @patch("squadops.cli.commands.projects._get_client")
    def test_json_output(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            [
                {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test"},
            ]
        )
        result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["project_id"] == "hello_squad"

    @patch("squadops.cli.commands.projects._get_client")
    def test_ls_alias(self, mock_get_client):
        mock_get_client.return_value = _mock_client([])
        result = runner.invoke(app, ["projects", "ls"])
        assert result.exit_code == 0

    @patch("squadops.cli.commands.projects._get_client")
    def test_quiet_mode(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            [
                {"project_id": "p1", "name": "P1", "description": "D"},
            ]
        )
        result = runner.invoke(app, ["--quiet", "projects", "list"])
        assert result.exit_code == 0
        assert "p1" in result.output


class TestProjectsShow:
    @patch("squadops.cli.commands.projects._get_client")
    def test_show(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            {"project_id": "hello_squad", "name": "Hello Squad", "description": "Test"}
        )
        result = runner.invoke(app, ["projects", "show", "hello_squad"])
        assert result.exit_code == 0
        assert "hello_squad" in result.output

    @patch("squadops.cli.commands.projects._get_client")
    def test_not_found(self, mock_get_client):
        mock = MagicMock()
        mock.get.side_effect = CLIError("not found", exit_codes.NOT_FOUND)
        mock_get_client.return_value = mock
        result = runner.invoke(app, ["projects", "show", "nope"])
        assert result.exit_code == exit_codes.NOT_FOUND


_IMPORT_ARGS = [
    "projects",
    "import",
    "--repo",
    "https://code.example.invalid/tally/tally.git",
    "--name",
    "Tally",
    "--base-ref",
    "refs/heads/main",
    "--contribution-mode",
    "review_request",
    "--owner",
    "Tally Maintainer",
    "--delegate",
    "contribution",
    "--delegate",
    "candidate_acceptance",
]


class TestProjectsImport:
    """SIP-0112 E.4.1 (D.5, D.6). Bugs caught: a flag dropped between the command line and the
    body; a retry minting a fresh key, so a dropped connection registers twice; a failure
    printed without the key a safe retry needs."""

    @patch("squadops.cli.commands.projects._get_client")
    def test_the_body_carries_every_flag_and_a_minted_key_is_printed(self, mock_get_client):
        client = MagicMock()
        client.post.side_effect = lambda path, json: {
            "project": {
                "project_id": "prj-tally",
                "lifecycle_status": "REGISTERING",
                "record_version": 1,
            },
            "idempotency_key": json["idempotency_key"],
            "replayed": False,
        }
        mock_get_client.return_value = client

        result = runner.invoke(app, _IMPORT_ARGS)

        [(path,), kwargs] = client.post.call_args
        body = kwargs["json"]
        assert (result.exit_code, path) == (0, "/api/v1/projects")
        assert body["origin"] == {"mode": "import"}
        assert body["source"] == {
            "repo_uri": "https://code.example.invalid/tally/tally.git",
            "base_ref": "refs/heads/main",
            "contribution_mode": "review_request",
            "repository_root": ".",
        }
        assert body["ownership"]["delegated_actions"] == ["contribution", "candidate_acceptance"]
        assert "project_id" not in body
        assert body["idempotency_key"].startswith("cli-")
        assert "registered: prj-tally REGISTERING" in result.output
        assert body["idempotency_key"] in result.output

    @patch("squadops.cli.commands.projects._get_client")
    def test_a_given_key_is_resent_and_a_failure_names_it(self, mock_get_client):
        client = MagicMock()
        client.post.side_effect = CLIError("422 LOCATOR_REFUSED", exit_codes.GENERAL_ERROR)
        mock_get_client.return_value = client

        result = runner.invoke(app, [*_IMPORT_ARGS, "--idempotency-key", "import-7"])

        assert client.post.call_args.kwargs["json"]["idempotency_key"] == "import-7"
        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert "idempotency key import-7" in result.output


class TestProjectsValidate:
    """SIP-0112 E.4.2. Bug caught: a failed validation exiting 0, so a script that registers
    and validates carries on with a Project that can never run a Cycle."""

    @pytest.mark.parametrize(
        ("status", "commit", "diagnostic", "exit_code", "shown"),
        [
            ("READY", "c" * 40, None, 0, "prj-tally READY: " + "c" * 40),
            ("FAILED_REGISTRATION", None, "clone: denied", 1, "FAILED_REGISTRATION: clone: denied"),
        ],
    )
    @patch("squadops.cli.commands.projects._get_client")
    def test_the_outcome_is_printed_and_a_failure_exits_nonzero(
        self, mock_get_client, status, commit, diagnostic, exit_code, shown
    ):
        client = MagicMock()
        client.post.return_value = {
            "project": {
                "project_id": "prj-tally",
                "lifecycle_status": status,
                "development_baseline_commit": commit,
                "validation_diagnostic": diagnostic,
            },
            "idempotency_key": "v-1",
            "replayed": False,
        }
        mock_get_client.return_value = client

        result = runner.invoke(
            app, ["projects", "validate", "prj-tally", "--idempotency-key", "v-1"]
        )

        assert client.post.call_args.args == ("/api/v1/projects/prj-tally/validate",)
        assert client.post.call_args.kwargs == {"json": {"idempotency_key": "v-1"}}
        assert result.exit_code == exit_code
        assert shown in result.output


class TestProjectsConfigure:
    """SIP-0112 E.4.2. Bug caught: a recording sent against no revision, so the server's version
    precondition can't refuse a concurrent one; the file's other keys leaking into the body."""

    @patch("squadops.cli.commands.projects._get_client")
    def test_the_current_revision_is_read_and_sent_as_the_expected_one(
        self, mock_get_client, tmp_path
    ):
        spec = tmp_path / "dev.yaml"
        spec.write_text("technical: {project_type: service}\nnotes: ignored\n")
        client = MagicMock()
        client.get.return_value = {"development_configuration_revision": 3}
        client.post.return_value = {
            "configuration": {
                "revision": 4,
                "document": {"configuration": {"instruction_sources": [{}]}},
            },
            "idempotency_key": "c-1",
            "replayed": False,
        }
        mock_get_client.return_value = client

        result = runner.invoke(
            app, ["projects", "configure", "prj-tally", "-f", str(spec), "--idempotency-key", "c-1"]
        )

        assert result.exit_code == 0, result.output
        assert client.post.call_args.kwargs["json"] == {
            "idempotency_key": "c-1",
            "expected_revision": 3,
            "technical": {"project_type": "service"},
        }
        assert "revision 4 (1 instruction source(s) found" in " ".join(result.output.split())

    def test_an_unreadable_file_exits_before_any_call(self, tmp_path):
        result = runner.invoke(
            app, ["projects", "configure", "prj-tally", "-f", str(tmp_path / "missing.yaml")]
        )
        assert result.exit_code == 2


class TestCyclesCreateSourcePrecondition:
    """SIP-0112 §D.3. Bug caught: the expected baseline sent as a --set override inside the
    execution overrides, where the server neither types nor checks it."""

    @patch("squadops.cli.commands.cycles._get_client")
    def test_the_expected_baseline_travels_as_the_typed_precondition(self, mock_get_client):
        client = MagicMock()
        client.post.return_value = {
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "status": "queued",
            "resolved_config_hash": "",
            "source_context": {
                "project_id": "prj-tally",
                "development_baseline_commit": "c" * 40,
                "development_configuration_revision": 2,
            },
        }
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            [
                "cycles", "create", "prj-tally", "--squad-profile", "smoke",
                "--request-profile", "selftest", "--expect-baseline", "c" * 40,
                "--expect-configuration", "2",
            ],
        )  # fmt: skip

        body = client.post.call_args.kwargs["json"]
        assert result.exit_code == 0, result.output
        assert body["source_precondition"] == {
            "development_baseline_commit": "c" * 40,
            "development_configuration_revision": 2,
        }
        assert "source_precondition" not in body["execution_overrides"]
        assert "pinned prj-tally at cccccccccccc, configuration revision 2" in " ".join(
            result.output.split()
        )

    def test_a_configuration_without_a_baseline_is_refused_before_any_call(self):
        result = runner.invoke(
            app,
            [
                "cycles",
                "create",
                "prj-tally",
                "--squad-profile",
                "smoke",
                "--expect-configuration",
                "2",
            ],
        )
        assert result.exit_code == 1


class TestProjectsSync:
    """#2606. Bug caught: the operator's table filing the squad's own merged files as outside
    change, or dropping them, so a sync can't say who changed what."""

    @patch("squadops.cli.commands.projects._get_client")
    def test_the_squads_integrated_paths_are_named_apart_from_outside_change(self, get_client):
        client = MagicMock()
        client.post.return_value = {
            "document": {
                "baseline_commit": "4" * 40,
                "upstream_commit": "b" * 40,
                "drift": {
                    "changed": {"instructions": ["CLAUDE.md"], "source": ["src/c/__init__.py"]},
                    "integrated": [
                        {"cycle_id": "cyc_709e3a912150", "run_id": "run_7", "commit": "2" * 40,
                         "changed": {"source": ["src/c/cli.py", "tests/test_cli_version.py"]}},
                    ],
                    "relevant": ["instructions"],
                },
                "contributions": [],
            }
        }  # fmt: skip
        get_client.return_value = client

        result = runner.invoke(app, ["projects", "sync", "prj-z"])

        assert result.exit_code == 0, result.output
        rows = [" ".join(line.replace("│", " ").split()) for line in result.output.splitlines()]
        assert "source 1 src/c/__init__.py" in rows
        assert "source, by cyc_709e3a912150 2 src/c/cli.py," in rows
        assert "evidence to revalidate: instructions" in " ".join(rows)


class TestBaselineCaptureBound:
    """#2605, entered at the CLI over the real API client."""

    def _invoke(self, handler, *args):
        import httpx

        from squadops.cli.client import APIClient
        from squadops.cli.config import CLIConfig

        api = APIClient(
            CLIConfig(timeout=30, long_timeout=1234),
            client=httpx.Client(
                transport=httpx.MockTransport(handler), base_url="http://api", timeout=30
            ),
        )
        with patch("squadops.cli.commands.projects._get_client", return_value=api):
            return runner.invoke(app, ["--json", "projects", "baseline", "prj-tally", *args])

    def test_a_capture_waits_for_the_long_bound_and_a_read_for_the_default(self):
        """Bug caught: the capture sent under the 30 s default, so it reads as failed while the
        server runs the product's install and checks (#2605's `demo-b-baseline-1`); or every
        request given the long bound, so a dead server takes 30 minutes to say so."""
        seen = []

        def handler(request):
            import httpx

            seen.append((request.method, request.extensions["timeout"]["read"]))
            return httpx.Response(200, json={"document": {}, "replayed": False})

        captured = self._invoke(handler, "--capture", "--idempotency-key", "cap-1")
        read = self._invoke(handler)

        assert (captured.exit_code, read.exit_code) == (0, 0), captured.output + read.output
        assert seen == [("POST", 1234), ("GET", 30)]

    def test_a_capture_that_times_out_names_its_key_once_and_how_to_read_it(self):
        """Bug caught: the timeout printed as a bare failure, or the key printed twice."""

        def handler(request):
            import httpx

            raise httpx.ReadTimeout("timed out", request=request)

        result = self._invoke(handler, "--capture", "--idempotency-key", "cap-2")

        said = " ".join(result.output.split())  # as printed, unwrapped
        assert result.exit_code == exit_codes.NETWORK_ERROR
        assert "timed out after 1234s: it may still complete on the server" in said
        assert said.count("cap-2") == 1

"""The worker as a service on its Mac: its settings, its agent, and what doctor reads (#3046).

The agent's settings are read from one env file and written into the LaunchAgent, and doctor
reads them back from there. Doctor's worker checks are entered at ``check_worker_service``, the
call ``squadops doctor dev-mac`` makes, over a home directory of the test's own, with launchctl's
answer given. The live install on the MacBook is in the PR.
"""

from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadops.bootstrap.setup import checks as checks_mod
from squadops.remote_execution.host_service import (
    LABEL,
    ServicePaths,
    agent_document,
    installed_settings,
    parse_env_file,
    worker_config,
)

NOW = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)


def _env(tmp_path: Path, **over: str) -> dict[str, str]:
    secrets = tmp_path / "secrets"
    secrets.mkdir(exist_ok=True)
    (secrets / "worker_client_secret").write_text("s3cret-value")
    (secrets / "worker_client_secret").chmod(0o600)
    values = {
        "SQUADOPS__WORKER__WORKER_ID": "macbook",
        "SQUADOPS__WORKER__RUNTIME_API_URL": "http://spark.test:8001",
        "SQUADOPS__WORKER__TOKEN_ENDPOINT": "http://spark.test:8180/realms/r/token",
        "SQUADOPS__WORKER__CLIENT_ID": "squadops-worker",
        "SQUADOPS__WORKER__CLIENT_SECRET": "secret://worker_client_secret",
        "SQUADOPS__WORKER__STATUS_FILE": str(tmp_path / "worker-status.json"),
        "SQUADOPS__WORKER__PROVIDER": "fixture",
        "SQUADOPS__SECRETS__PROVIDER": "file",
        "SQUADOPS__SECRETS__FILE_DIR": str(secrets),
    }
    return {**values, **over}


def _env_text(values: dict[str, str]) -> str:
    return "# the worker on the MacBook\n\n" + "".join(f"{k}={v}\n" for k, v in values.items())


@pytest.mark.parametrize(
    ("line", "says"),
    [
        ("PATH=/usr/bin", "line 3: PATH is outside"),
        ("SQUADOPS__WORKER__WORKER_ID=again", "line 3: SQUADOPS__WORKER__WORKER_ID is given twice"),
        ('SQUADOPS__WORKER__CLIENT_ID="squadops-worker"', "value is quoted"),
        ("export SQUADOPS__WORKER__X=1", "line 3 isn't KEY=VALUE"),
    ],
    ids=["another-section", "twice", "quoted", "shell"],
)
def test_an_env_file_is_read_whole_or_refused_by_line(line, says):
    """Bugs caught: a stray variable carried into the agent's environment; a setting given twice
    where the last silently wins; a quoted value whose quotes become part of a path; a shell line
    read as something it isn't."""
    text = "SQUADOPS__WORKER__WORKER_ID=macbook\nSQUADOPS__WORKER__PROVIDER=fixture\n" + line

    with pytest.raises(ValueError, match=says):
        parse_env_file(text, "worker.env")


@pytest.mark.parametrize(
    ("over", "says"),
    [
        ({"SQUADOPS__WORKER__CLIENT_SECRET": "s3cret-value"}, "must be a secret:// reference"),
        ({"SQUADOPS__WORKER__STATUS_FILE": ""}, "status_file"),
        ({"SQUADOPS__WORKER__STATUS_FILES": "x"}, "unknown SQUADOPS__WORKER__ settings"),
    ],
    ids=["a-secret-written-in", "no-status-file", "a-typo"],
)
def test_the_service_runs_only_a_config_the_worker_would_start_with(tmp_path, over, says):
    """Bugs caught: the client's secret written into a plain-text agent under ~/Library; an
    agent that starts a worker which then refuses its own config and restarts forever; a
    misspelt setting deployed as missing."""
    with pytest.raises(ValueError, match=says):
        worker_config(_env(tmp_path, **over))


def test_the_agent_carries_the_settings_and_doctor_reads_them_back(tmp_path):
    """The wiring between the two ends. Bugs caught: a setting dropped between the env file and
    the agent, so the worker starts without it; an agent that runs once and never again after
    an exit, or not at login."""
    values = parse_env_file(_env_text(_env(tmp_path)), "worker.env")
    paths = ServicePaths(tmp_path)
    document = agent_document(
        values, python=Path("/repo/.venv/bin/python"), repo=Path("/repo"), paths=paths
    )
    paths.agent.parent.mkdir(parents=True)
    paths.agent.write_bytes(plistlib.dumps(document))

    assert installed_settings(paths) == values
    assert (document["Label"], document["RunAtLoad"], document["KeepAlive"]) == (LABEL, True, True)
    assert document["ProgramArguments"] == [
        "/repo/.venv/bin/python",
        "-m",
        "squadops.remote_execution.worker_main",
    ]
    assert "s3cret-value" not in paths.agent.read_text(errors="replace")


def _installed(tmp_path: Path, **over: str) -> dict[str, str]:
    values = _env(tmp_path, **over)
    paths = ServicePaths(tmp_path)
    paths.agent.parent.mkdir(parents=True, exist_ok=True)
    paths.agent.write_bytes(
        plistlib.dumps(agent_document(values, python=Path("/p"), repo=Path("/r"), paths=paths))
    )
    return values


def _launchctl(monkeypatch, *, returncode: int = 0, state: str = "running") -> None:
    printed = f"gui/501/{LABEL} = {{\n\tstate = {state}\n\tpid = 4242\n\tlast exit code = 1\n}}\n"

    def run(argv, **kwargs):
        assert argv[:2] == ["launchctl", "print"]
        return subprocess.CompletedProcess(argv, returncode, printed, "")

    monkeypatch.setattr(checks_mod.subprocess, "run", run)


def _status(tmp_path: Path, **over) -> None:
    status = {
        "worker_id": "macbook",
        "runtime_api_url": "http://spark.test:8001",
        "started_at": (NOW - timedelta(minutes=10)).isoformat(),
        "tool_ready": True,
        "tool_note": "",
        "session_id": "wks-1",
        "registered_at": (NOW - timedelta(minutes=9)).isoformat(),
        "last_answer_at": (NOW - timedelta(seconds=20)).isoformat(),
        "last_unreachable_at": None,
        "last_unreachable": "",
        **over,
    }
    (tmp_path / "worker-status.json").write_text(json.dumps(status))


def test_a_mac_without_the_service_is_asked_nothing(tmp_path):
    """Bug caught: every dev-mac failing doctor for a worker it never installed."""
    assert checks_mod.check_worker_service(home=tmp_path) == []


def test_doctor_reports_each_check_by_name_for_a_serving_worker(tmp_path, monkeypatch):
    """The issue's done-when, entered at doctor's call. Bug caught: a check left out, so doctor
    passes a Mac whose service is installed but stopped, or whose worker never registered."""
    _installed(tmp_path)
    _launchctl(monkeypatch)
    _status(tmp_path, last_answer_at=datetime.now(UTC).isoformat())

    results = checks_mod.check_worker_service(home=tmp_path)

    assert [(r.name, r.passed) for r in results] == [
        ("worker:service", True),
        ("worker:config", True),
        ("worker:registered", True),
    ]
    assert results[0].message == f"{LABEL} is running (pid 4242)"
    assert "session wks-1 with http://spark.test:8001" in results[2].message


@pytest.mark.parametrize(
    ("status", "says"),
    [
        (None, "has recorded no status"),
        ({"tool_ready": False, "tool_note": "ConnectionError: Studio"}, "couldn't be reset"),
        ({"session_id": None, "last_unreachable": "connection refused"}, "connection refused"),
        (
            {"last_unreachable_at": (NOW - timedelta(seconds=5)).isoformat(),
             "last_unreachable": "timed out"},
            "hasn't answered since",
        ),
        ({"last_answer_at": (NOW - timedelta(minutes=5)).isoformat()}, "more than a lease ago"),
    ],
    ids=["no-status", "tool-closed", "never-registered", "cut-off", "stale"],
)  # fmt: skip
def test_a_worker_that_isnt_serving_fails_registered_naming_why(tmp_path, status, says):
    """Bugs caught: a worker read as online from a status that predates its cut-off, or one
    whose tool never opened; a stopped worker passing on its last good status."""
    values = _installed(tmp_path)
    if status is not None:
        _status(tmp_path, **status)
    config = worker_config(values)

    result = checks_mod._worker_registered(config, now=NOW)

    assert (result.name, result.passed) == ("worker:registered", False)
    assert says in result.message


def test_a_stopped_service_and_an_unresolvable_secret_each_fail_by_name(tmp_path, monkeypatch):
    """Bugs caught: an agent launchd loaded but left stopped after its worker exited, read as
    running; a secret file removed after install, found only when the worker refuses to start."""
    values = _installed(tmp_path)
    (Path(values["SQUADOPS__SECRETS__FILE_DIR"]) / "worker_client_secret").unlink()
    _launchctl(monkeypatch, state="not running")

    results = {r.name: r for r in checks_mod.check_worker_service(home=tmp_path)}

    assert results["worker:service"].message == f"{LABEL} is not running, and its last exit was 1"
    assert not results["worker:config"].passed
    assert "doesn't resolve" in results["worker:config"].message
    assert "worker:registered" not in results

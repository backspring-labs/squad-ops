"""``scripts/dev/worker_service.py install``: what it refuses before anything is written (#3046).

Entered at ``install`` over a home directory of the test's own. Nothing reaches launchctl: each
case is refused first, and the test fails if launchctl is asked.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from squadops.remote_execution.host_service import ServicePaths

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "worker_service.py"
_spec = importlib.util.spec_from_file_location("worker_service", _PATH)
service = importlib.util.module_from_spec(_spec)
sys.modules["worker_service"] = service
_spec.loader.exec_module(service)


def _env_file(tmp_path: Path, *, provider: str = "file", mode: int = 0o600) -> Path:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    secret = secrets / "worker_client_secret"
    secret.write_text("s3cret-value")
    secret.chmod(mode)
    lines = {
        "SQUADOPS__WORKER__WORKER_ID": "macbook",
        "SQUADOPS__WORKER__RUNTIME_API_URL": "http://spark.test:8001",
        "SQUADOPS__WORKER__TOKEN_ENDPOINT": "http://spark.test:8180/realms/r/token",
        "SQUADOPS__WORKER__CLIENT_ID": "squadops-worker",
        "SQUADOPS__WORKER__CLIENT_SECRET": "secret://worker_client_secret",
        "SQUADOPS__WORKER__STATUS_FILE": str(tmp_path / "status.json"),
        "SQUADOPS__WORKER__PROVIDER": "fixture",
        "SQUADOPS__SECRETS__PROVIDER": provider,
        "SQUADOPS__SECRETS__FILE_DIR": str(secrets),
    }
    path = tmp_path / "worker.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in lines.items()))
    return path


@pytest.fixture(autouse=True)
def no_launchctl(monkeypatch):
    def refuse(*args):
        raise AssertionError(f"launchctl was asked {args} for a settings file it should refuse")

    monkeypatch.setattr(service, "_launchctl", refuse)


@pytest.mark.parametrize(
    ("provider", "mode", "says"),
    [
        ("env", 0o600, "reads its secret with the 'file' provider only"),
        ("file", 0o644, r"is readable by others \(0o644\): chmod 600"),
    ],
    ids=["another-secrets-provider", "a-secret-others-can-read"],
)
def test_install_refuses_a_secret_it_cant_keep_private(tmp_path, provider, mode, says):
    """Bugs caught: the secret's value written into the agent's environment for the env
    provider, in plain text under ~/Library/LaunchAgents; a secret file any user can read."""
    paths = ServicePaths(tmp_path / "home")

    with pytest.raises(SystemExit, match=says):
        service.install(_env_file(tmp_path, provider=provider, mode=mode), Path("/p"), paths)

    assert not paths.agent.exists()


def test_install_refuses_a_secret_that_doesnt_resolve(tmp_path):
    """Bug caught: an agent installed whose worker refuses its own secret at every start, and
    restarts forever."""
    env_file = _env_file(tmp_path)
    (tmp_path / "secrets" / "worker_client_secret").write_text("")
    paths = ServicePaths(tmp_path / "home")

    with pytest.raises(SystemExit, match="secret://worker_client_secret doesn't resolve"):
        service.install(env_file, Path("/p"), paths)

    assert not paths.agent.exists()


def test_a_reinstall_waits_for_the_old_agent_to_unload_before_loading_the_new(monkeypatch):
    """#3046's reinstall from the main checkout failed live: ``bootout`` returned while the old
    job was still loaded, ``bootstrap`` answered "Input/output error", and the Mac was left with
    no agent at all. Bug caught: loading before launchd has let go of the old job."""
    asked = []
    still_loaded = iter([0, 0, 113])  # print finds the job twice, then not

    def launchctl(*args):
        asked.append(args[0])
        code = next(still_loaded) if args[0] == "print" else 0
        return subprocess.CompletedProcess(["launchctl", *args], code, "", "")

    monkeypatch.setattr(service, "_launchctl", launchctl)
    monkeypatch.setattr(service.time, "sleep", lambda seconds: None)

    service._unload()

    assert asked == ["bootout", "print", "print", "print"]


def test_an_agent_that_wont_unload_stops_the_reinstall(monkeypatch):
    """Bug caught: a reinstall that goes on to load a second copy over a job that never left."""
    monkeypatch.setattr(
        service,
        "_launchctl",
        lambda *args: subprocess.CompletedProcess(["launchctl", *args], 0, "", ""),
    )
    clock = iter([0.0, 10.0, 40.0])
    monkeypatch.setattr(service.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(service.time, "sleep", lambda seconds: None)

    with pytest.raises(SystemExit, match="still loaded after 30s"):
        service._unload()

#!/usr/bin/env python3
"""Run the remote-execution worker as a service on this Mac (SIP-0117 R5.7; #3046).

# Platform: dev-mac (launchd, a per-user LaunchAgent)

The worker runs as the per-user LaunchAgent ``xyz.backspring.squadops.worker``. launchd starts it
when you log in, and again whenever it exits. It connects outward to the runtime and opens no
listener. On start it resets its tool, so a Studio worker opens Studio on the place itself.

    worker_service.py install --env-file ~/.config/squadops/worker.env
    worker_service.py status
    worker_service.py run-window --hours 4
    worker_service.py uninstall

**The env file** holds the worker's settings, ``SQUADOPS__WORKER__*``, and the secrets provider
that resolves its one secret, ``SQUADOPS__SECRETS__*``. The client's secret must be a reference,
for example ``secret://worker_client_secret`` with the ``file`` provider, in a file only you can
read. ``install`` refuses a secret written in, a secret file others can read, a setting the
worker doesn't read and a file it can't read whole, and it never prints the secret.

**A run window** keeps the Mac and its display awake for its length (``caffeinate -d -i``),
so a scenario that clicks finds Studio unlocked and in front. Each window is recorded.

**Install it from the main checkout.** The agent runs the worker from the checkout this script
is in, and a worktree is removed when its work merges.

**After a restart,** the agent starts when you log in. With FileVault on, that's after the
password at startup, so a restart needs a person at the Mac before the worker can come back.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from squadops.core.secrets import SecretNotFoundError
from squadops.remote_execution.host_service import (
    LABEL,
    ServicePaths,
    agent_document,
    installed_settings,
    parse_env_file,
    worker_config,
)

REPO = Path(__file__).resolve().parents[2]


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def _require_mac() -> None:
    if sys.platform != "darwin":
        raise SystemExit("worker_service.py runs on the dev-mac profile only (launchd)")


def install(env_file: Path, python: Path, paths: ServicePaths) -> int:
    """Validate the settings whole, then write and load the agent."""
    import plistlib

    from adapters.remote_execution.factory import create_operation_runner
    from squadops.bootstrap.secrets import secret_manager_from_env

    values = parse_env_file(env_file.read_text(encoding="utf-8"), str(env_file))
    config = worker_config(values)
    _require_private_secret(values, config.client_secret)
    _resolves(values, config.client_secret, secret_manager_from_env)
    create_operation_runner(config.provider, config.provider_settings())  # files it names
    if not python.is_file():
        raise SystemExit(f"{python} isn't there: create the venv first (bootstrap dev-mac)")

    paths.logs.mkdir(parents=True, exist_ok=True)
    paths.agent.parent.mkdir(parents=True, exist_ok=True)
    document = agent_document(values, python=python, repo=REPO, paths=paths)
    if paths.agent.exists():
        _unload()
    partial = paths.agent.with_suffix(".partial")
    with partial.open("wb") as f:
        plistlib.dump(document, f)
    os.chmod(partial, 0o644)
    os.replace(partial, paths.agent)
    loaded = _launchctl("bootstrap", _domain(), str(paths.agent))
    if loaded.returncode != 0:
        raise SystemExit(f"launchctl bootstrap refused {paths.agent}: {loaded.stderr.strip()}")
    print(f"installed {LABEL} for worker {config.worker_id} ({config.provider})")
    print(f"  runs:   {python} -m squadops.remote_execution.worker_main, from {REPO}")
    print(f"  agent:  {paths.agent}")
    print(f"  log:    {paths.log}")
    print(f"  status: {config.status_file}")
    return 0


def _unload(wait_seconds: float = 30.0) -> None:
    """Unload the agent and wait until launchd no longer knows it. ``bootout`` returns before the
    old job is gone, and a ``bootstrap`` in that window fails with an I/O error, leaving no agent
    loaded at all."""
    _launchctl("bootout", f"{_domain()}/{LABEL}")
    deadline = time.monotonic() + wait_seconds
    while _launchctl("print", f"{_domain()}/{LABEL}").returncode == 0:
        if time.monotonic() > deadline:
            raise SystemExit(
                f"{LABEL} was asked to stop and is still loaded after {wait_seconds:g}s; "
                "nothing was changed"
            )
        time.sleep(0.5)


def _require_private_secret(values: dict[str, str], reference: str) -> None:
    """The secret is read by the ``file`` provider, from a file its owner alone can read. Any
    other provider would need the secret's value in the agent's environment, which is the plain
    text this service keeps it out of."""
    provider = values.get("SQUADOPS__SECRETS__PROVIDER")
    if provider != "file":
        raise SystemExit(
            f"SQUADOPS__SECRETS__PROVIDER is {provider!r}: the service reads its secret with the "
            "'file' provider only, from a file under SQUADOPS__SECRETS__FILE_DIR"
        )
    directory = Path(values.get("SQUADOPS__SECRETS__FILE_DIR", "")).expanduser()
    key = reference.removeprefix("secret://")
    secret = directory / key
    if not secret.is_file():
        raise SystemExit(f"the secret file {secret} isn't there")
    mode = stat.S_IMODE(secret.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(
            f"the secret file {secret} is readable by others ({oct(mode)}): chmod 600 {secret}"
        )


def _resolves(values: dict[str, str], reference: str, manager_from_env) -> None:
    """The reference resolves under the env file's secrets provider. The value isn't kept."""
    manager = manager_from_env(values)
    if manager is None:
        raise SystemExit("the env file selects no secrets provider for the reference")
    try:
        resolved = manager.resolve(reference)
    except SecretNotFoundError as e:
        raise SystemExit(f"{reference} doesn't resolve: {e}") from e
    if not resolved:
        raise SystemExit(f"{reference} resolves to an empty secret")


def uninstall(paths: ServicePaths) -> int:
    loaded = _launchctl("print", f"{_domain()}/{LABEL}").returncode == 0
    if loaded:
        _unload()
    if paths.agent.exists():
        paths.agent.unlink()
    print(f"removed {LABEL}" + ("" if loaded else " (it wasn't loaded)"))
    return 0


def status(paths: ServicePaths) -> int:
    settings = installed_settings(paths)
    if settings is None:
        print(f"{LABEL} isn't installed ({paths.agent})")
        return 1
    printed = _launchctl("print", f"{_domain()}/{LABEL}")
    state = next(
        (line.strip() for line in printed.stdout.splitlines() if line.strip().startswith("state")),
        "not loaded",
    )
    print(f"{LABEL}: {state}")
    status_file = Path(settings.get("SQUADOPS__WORKER__STATUS_FILE", "")).expanduser()
    if status_file.is_file():
        print(json.dumps(json.loads(status_file.read_text()), indent=2))
    else:
        print(f"no status recorded yet at {status_file}")
    for window in _windows(paths):
        print(f"run window until {window['ends_at']} (caffeinate pid {window['pid']})")
    return 0


def run_window(hours: float, paths: ServicePaths) -> int:
    """Keep the Mac and its display awake for ``hours``, and record the window."""
    if hours <= 0:
        raise SystemExit("a run window needs a length in hours above zero")
    caffeinate = shutil.which("caffeinate") or "/usr/bin/caffeinate"
    seconds = int(hours * 3600)
    started = datetime.now(UTC)
    process = subprocess.Popen(
        [caffeinate, "-d", "-i", "-t", str(seconds)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    window = {
        "started_at": started.isoformat(timespec="seconds"),
        "ends_at": (started + timedelta(seconds=seconds)).isoformat(timespec="seconds"),
        "pid": process.pid,
        "hours": hours,
    }
    paths.logs.mkdir(parents=True, exist_ok=True)
    with paths.run_windows.open("a", encoding="utf-8") as f:
        f.write(json.dumps(window) + "\n")
    print(f"awake until {window['ends_at']} (caffeinate pid {process.pid}), recorded in "
          f"{paths.run_windows}")  # fmt: skip
    return 0


def _windows(paths: ServicePaths) -> list[dict]:
    """The recorded windows still running."""
    if not paths.run_windows.is_file():
        return []
    now = datetime.now(UTC)
    running = []
    for line in paths.run_windows.read_text(encoding="utf-8").splitlines():
        window = json.loads(line)
        if datetime.fromisoformat(window["ends_at"]) > now and _alive(window["pid"]):
            running.append(window)
    return running


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    _require_mac()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("install", help="validate the settings, then write and load the agent")
    add.add_argument("--env-file", type=Path, required=True)
    add.add_argument("--python", type=Path, default=REPO / ".venv" / "bin" / "python")
    sub.add_parser("uninstall", help="unload and remove the agent")
    sub.add_parser("status", help="the agent's state, the worker's status, any run window")
    window = sub.add_parser("run-window", help="keep the Mac and its display awake")
    window.add_argument("--hours", type=float, required=True)
    args = parser.parse_args()
    paths = ServicePaths(Path.home())
    if args.command == "install":
        return install(args.env_file.expanduser(), args.python.expanduser(), paths)
    if args.command == "uninstall":
        return uninstall(paths)
    if args.command == "status":
        return status(paths)
    return run_window(args.hours, paths)


if __name__ == "__main__":
    sys.exit(main())

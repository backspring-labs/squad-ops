"""The worker as a service on its Mac (SIP-0117 R5.7; #3046).

# Platform: dev-mac (launchd, a per-user LaunchAgent)

The worker runs as a per-user LaunchAgent, **not** a system daemon: its tool may be a GUI app,
which needs the user's session, and launchd starts an agent when that user logs in. It connects
outward only, and opens no listener. This module holds the pieces ``scripts/dev/worker_service.py``
and ``squadops doctor`` share:
- **the label and the paths:** where the agent's document, its log and the run windows' record are;
- **the settings:** read from one env file, strictly, and held to the worker's config. The client's
  secret must be a ``secret://`` reference, because the agent's document is plain text under
  ``~/Library/LaunchAgents``;
- **the agent's document:** the worker's settings in its environment, started at login and again
  whenever it exits.

Nothing here runs ``launchctl``. The script does that.
"""

from __future__ import annotations

import plistlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from squadops.config.schema import WorkerConfig

#: The agent's label. Named to the owner before it was first installed (2026-11-16).
LABEL = "xyz.backspring.squadops.worker"
#: The prefixes an env file for the worker may hold: its own section, and the secrets provider
#: that resolves its one reference.
WORKER_PREFIX = "SQUADOPS__WORKER__"
SECRETS_PREFIX = "SQUADOPS__SECRETS__"
#: How long the agent waits before starting the worker again after it exits.
RESTART_SECONDS = 30

_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


@dataclass(frozen=True)
class ServicePaths:
    """Where the agent's files are, under a user's home."""

    home: Path

    @property
    def agent(self) -> Path:
        return self.home / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    @property
    def logs(self) -> Path:
        return self.home / "Library" / "Logs" / "squadops"

    @property
    def log(self) -> Path:
        return self.logs / "worker.log"

    @property
    def run_windows(self) -> Path:
        return self.logs / "run-windows.jsonl"


def parse_env_file(text: str, where: str) -> dict[str, str]:
    """The settings an env file holds. Only ``KEY=VALUE`` lines, comments and blank lines are
    read. Anything else is refused, naming its line, rather than guessed at:
    - a key outside the worker's section and the secrets provider's;
    - a key given twice;
    - a value in quotes, which an env file's reader would keep or strip depending on the reader;
    - an ``export`` prefix, or any other shell."""
    values: dict[str, str] = {}
    problems: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        if match is None:
            problems.append(f"line {number} isn't KEY=VALUE")
            continue
        key, value = match.groups()
        if not key.startswith((WORKER_PREFIX, SECRETS_PREFIX)):
            problems.append(f"line {number}: {key} is outside {WORKER_PREFIX} and {SECRETS_PREFIX}")
        elif key in values:
            problems.append(f"line {number}: {key} is given twice")
        elif value[:1] in "\"'" and value:
            problems.append(f"line {number}: {key}'s value is quoted; write it bare")
        else:
            values[key] = value
    if problems:
        raise ValueError(f"{where} can't be read: " + "; ".join(problems))
    return values


def worker_config(values: Mapping[str, str]) -> WorkerConfig:
    """The worker's config from an env file's settings, as ``worker_main`` will read them, with
    the client's secret required to be a ``secret://`` reference."""
    section = {
        key[len(WORKER_PREFIX) :].lower(): value
        for key, value in values.items()
        if key.startswith(WORKER_PREFIX)
    }
    unknown = set(section) - set(WorkerConfig.model_fields)
    if unknown:
        raise ValueError(f"unknown {WORKER_PREFIX} settings: {sorted(unknown)}")
    config = WorkerConfig.model_validate(section)
    if not config.client_secret.startswith("secret://"):
        raise ValueError(
            f"{WORKER_PREFIX}CLIENT_SECRET must be a secret:// reference: the agent's document "
            "is plain text under ~/Library/LaunchAgents, and a secret written there is a secret "
            "anyone reading the file holds"
        )
    if not any(key.startswith(SECRETS_PREFIX) for key in values):
        raise ValueError(
            f"{WORKER_PREFIX}CLIENT_SECRET is a reference, and no {SECRETS_PREFIX}PROVIDER is "
            "set to resolve it"
        )
    return config


def agent_document(
    values: Mapping[str, str], *, python: Path, repo: Path, paths: ServicePaths
) -> dict[str, object]:
    """The LaunchAgent: the worker's module run by ``python`` from ``repo``, with its settings as
    its environment, started at login and again after it exits, logging to one file."""
    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), "-m", "squadops.remote_execution.worker_main"],
        "WorkingDirectory": str(repo),
        "EnvironmentVariables": dict(values),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": RESTART_SECONDS,
        "StandardOutPath": str(paths.log),
        "StandardErrorPath": str(paths.log),
        "ProcessType": "Interactive",
    }


def installed_settings(paths: ServicePaths) -> dict[str, str] | None:
    """The settings the installed agent runs the worker with, or ``None`` when no agent is
    installed. An agent document that can't be read raises: it is installed, and broken."""
    if not paths.agent.exists():
        return None
    with paths.agent.open("rb") as f:
        document = plistlib.load(f)
    environment = document.get("EnvironmentVariables")
    if document.get("Label") != LABEL or not isinstance(environment, dict):
        raise ValueError(
            f"{paths.agent} isn't this service's agent: its label is {document.get('Label')!r}, "
            "and it must carry the worker's settings as EnvironmentVariables"
        )
    return {str(k): str(v) for k, v in environment.items()}

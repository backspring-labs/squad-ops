"""The Project Development Configuration (SIP-0112 §B.5, FR-20, FR-21; E.4.2) and its start
declaration (contract 7, §8.2.1).

A versioned record of how the product is worked on, kept outside its repository:
- its native checks, each an argv run from the repository's root, after the install and build
  steps the checks need (``commands.install``, ``commands.build``; the start declaration's own
  steps are its own, never borrowed);
- how it is started for evaluation;
- the repository's own instruction sources, found at the commit the record was validated
  against.

A revision is never edited. A change is a new revision, and a unit keeps the revision it pinned
(§B.5.1).

Everything a runner will execute is refused here if it is malformed, rather than mangled later:
- an argv is a list of non-empty strings, never one shell string;
- a working directory stays inside the repository;
- a readiness kind is one the contract names;
- an evaluation secret is a ``secret://`` reference, never a value (Q40).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from squadops.sandbox.findings import READERS

API_VERSION = "squadops.project-development-configuration/v1"
_API_MAJOR = re.compile(r"^squadops\.project-development-configuration/v(\d+)$")

#: Contract 7's readiness kinds: a 2xx from the target URL, a connection to the target
#: host:port, or the target command exiting 0.
READINESS_KINDS = ("http", "tcp", "command")
#: What an entry point serves: an HTTP API, a UI, or something a scenario names itself.
ENTRY_POINT_KINDS = ("http_base", "ui_base", "other")
_URL_READINESS = READINESS_KINDS[:1]
_URL_ENTRY_POINTS = ENTRY_POINT_KINDS[:2]
_CHECK_ID = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")

#: The repository's own instruction sources (§B.5.1): the files a contributor is told to read,
#: found by name at the validated commit. Discovery lists them; SIP-0110 confirms each as a
#: project instruction, so the list itself reaches no task.
INSTRUCTION_FILES = (
    "CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/CONTRIBUTING.md",
    ".github/copilot-instructions.md",
    "docs/CONTRIBUTING.md",
)


class ConfigurationInvalid(ValueError):
    """A Development Configuration that can't be recorded or read, naming its field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


class UnknownConfigurationVersion(ConfigurationInvalid):
    """A major version this reader doesn't know: refused, reading none of it (§8.2.1)."""


@dataclass(frozen=True)
class Check:
    id: str
    argv: tuple[str, ...]
    requires_environment: tuple[str, ...] = ()
    #: #2609: the reader its output is read with, finding by finding, so a check that fails at the
    #: baseline can still show a regression (``squadops.sandbox.findings.READERS``). ``None``: the
    #: check is read whole, by its result alone.
    findings: str | None = None


@dataclass(frozen=True)
class Readiness:
    kind: str
    target: str
    timeout_seconds: float


@dataclass(frozen=True)
class EntryPoint:
    kind: str
    url: str


@dataclass(frozen=True)
class StartDeclaration:
    """Contract 7: how the product is started at a tree, and when it is ready."""

    working_directory: str
    start: tuple[str, ...]
    readiness: Readiness
    entry_points: tuple[EntryPoint, ...]
    install: tuple[tuple[str, ...], ...] = ()
    build: tuple[tuple[str, ...], ...] = ()
    evaluation_environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Commands:
    working_directory: str
    checks: tuple[Check, ...]
    start: StartDeclaration | None
    #: Run before each check, in that check's disposable copy, with the install network (X-3a).
    install: tuple[tuple[str, ...], ...] = ()
    build: tuple[tuple[str, ...], ...] = ()

    @property
    def check_setup(self) -> tuple[tuple[str, ...], ...]:
        return self.install + self.build


@dataclass(frozen=True)
class InstructionSource:
    path: str
    digest: str
    at_commit: str


@dataclass(frozen=True)
class DevelopmentConfiguration:
    project_id: str
    revision: int
    validated_at_commit: str
    project_type: str
    target: str
    stack: str | None
    commands: Commands
    instruction_sources: tuple[InstructionSource, ...]
    workspace_mode: str = "managed_clone"
    quality_contract_ref: str | None = None
    benchmark_profile_ref: str | None = None

    def to_document(self) -> dict[str, Any]:
        """The record as it is stored and read (the shape the shared fixture records)."""
        return {
            "api_version": API_VERSION,
            "configuration": {
                "project_id": self.project_id,
                "revision": self.revision,
                "validated_at_commit": self.validated_at_commit,
                "technical": {
                    "project_type": self.project_type,
                    "target": self.target,
                    "stack": self.stack,
                    "commands": _commands_document(self.commands),
                },
                "workspace": {
                    "mode": self.workspace_mode,
                    "preserve_repository_layout": True,
                },
                "instruction_sources": [
                    {"path": s.path, "digest": s.digest, "at_commit": s.at_commit}
                    for s in self.instruction_sources
                ],
                "quality": {"contract_ref": self.quality_contract_ref},
                "benchmark_profile_ref": self.benchmark_profile_ref,
            },
        }


# --- reading what a caller submits ---


def parse_technical(technical: Mapping[str, Any]) -> tuple[str, str, str | None, Commands]:
    """A submitted ``technical`` block: its project type, target, stack and commands."""
    project_type = _text(technical, "project_type", "technical")
    target = _text(technical, "target", "technical")
    stack = technical.get("stack")
    if stack is not None and not isinstance(stack, str):
        raise ConfigurationInvalid("technical.stack", "a stack's name, or null")
    commands = _mapping(technical, "commands", "technical")
    return project_type, target, stack, _commands(commands, "technical.commands")


def _commands(doc: Mapping[str, Any], at: str) -> Commands:
    checks_doc = doc.get("checks", [])
    if not isinstance(checks_doc, list):
        raise ConfigurationInvalid(f"{at}.checks", "a list of checks")
    checks = tuple(_check(c, f"{at}.checks[{i}]") for i, c in enumerate(checks_doc))
    ids = [c.id for c in checks]
    if len(set(ids)) != len(ids):
        raise ConfigurationInvalid(f"{at}.checks", f"each check's id is unique: {ids}")
    start = doc.get("start")
    return Commands(
        working_directory=_working_directory(
            doc.get("working_directory", "."), f"{at}.working_directory"
        ),
        checks=checks,
        start=_start(start, f"{at}.start") if start is not None else None,
        install=_argvs(doc.get("install", []), f"{at}.install"),
        build=_argvs(doc.get("build", []), f"{at}.build"),
    )


def _check(doc: Any, at: str) -> Check:
    if not isinstance(doc, Mapping):
        raise ConfigurationInvalid(at, "a check is a mapping with an id and an argv")
    check_id = _text(doc, "id", at)
    if not _CHECK_ID.match(check_id):
        raise ConfigurationInvalid(f"{at}.id", f"{check_id!r} is not a check id")
    needs = doc.get("requires_environment", [])
    if not isinstance(needs, list) or not all(
        isinstance(n, str) and _ENV_NAME.match(n) for n in needs
    ):
        raise ConfigurationInvalid(
            f"{at}.requires_environment", "a list of environment variable names"
        )
    reader = doc.get("findings")
    if reader is not None and reader not in READERS:
        raise ConfigurationInvalid(
            f"{at}.findings", f"{reader!r} is not a findings reader ({', '.join(READERS)})"
        )
    return Check(check_id, _argv(doc.get("argv"), f"{at}.argv"), tuple(needs), reader)


def _start(doc: Any, at: str) -> StartDeclaration:
    if not isinstance(doc, Mapping):
        raise ConfigurationInvalid(at, "a start declaration is a mapping")
    return StartDeclaration(
        working_directory=_working_directory(
            doc.get("working_directory", "."), f"{at}.working_directory"
        ),
        start=_argv(doc.get("start"), f"{at}.start"),
        readiness=_readiness(_mapping(doc, "readiness", at), f"{at}.readiness"),
        entry_points=_entry_points(doc.get("entry_points"), f"{at}.entry_points"),
        install=_argvs(doc.get("install", []), f"{at}.install"),
        build=_argvs(doc.get("build", []), f"{at}.build"),
        evaluation_environment=_secrets(
            doc.get("evaluation_environment", {}), f"{at}.evaluation_environment"
        ),
    )


def _readiness(doc: Mapping[str, Any], at: str) -> Readiness:
    kind = _text(doc, "kind", at)
    if kind not in READINESS_KINDS:
        raise ConfigurationInvalid(f"{at}.kind", f"one of {READINESS_KINDS}, not {kind!r}")
    target = _text(doc, "target", at)
    if kind in _URL_READINESS:
        _http_url(target, f"{at}.target")
    timeout = doc.get("timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
        raise ConfigurationInvalid(
            f"{at}.timeout_seconds", "a positive number of seconds, always declared"
        )
    return Readiness(kind, target, float(timeout))


def _entry_points(value: Any, at: str) -> tuple[EntryPoint, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigurationInvalid(at, "at least one entry point")
    entries = []
    for i, entry in enumerate(value):
        where = f"{at}[{i}]"
        if not isinstance(entry, Mapping):
            raise ConfigurationInvalid(where, "an entry point is a mapping with a kind and a url")
        kind = _text(entry, "kind", where)
        if kind not in ENTRY_POINT_KINDS:
            raise ConfigurationInvalid(f"{where}.kind", f"one of {ENTRY_POINT_KINDS}")
        url = _text(entry, "url", where)
        if kind in _URL_ENTRY_POINTS:
            _http_url(url, f"{where}.url")
        entries.append(EntryPoint(kind, url))
    return tuple(entries)


def _secrets(value: Any, at: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ConfigurationInvalid(at, "a mapping of NAME: secret://ref")
    for name, ref in value.items():
        if not (isinstance(name, str) and _ENV_NAME.match(name)):
            raise ConfigurationInvalid(at, f"{name!r} is not a name")
        if not (isinstance(ref, str) and ref.startswith("secret://") and len(ref) > 9):
            raise ConfigurationInvalid(f"{at}.{name}", "a secret:// reference, never a value (Q40)")
    return tuple(sorted(value.items()))


def _argv(value: Any, at: str) -> tuple[str, ...]:
    if isinstance(value, str):
        raise ConfigurationInvalid(at, "an argv is a list of strings, never one shell string")
    if not isinstance(value, list) or not value or not all(isinstance(a, str) and a for a in value):
        raise ConfigurationInvalid(at, "an argv is a non-empty list of non-empty strings")
    return tuple(value)


def _argvs(value: Any, at: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        raise ConfigurationInvalid(at, "a list of argvs")
    return tuple(_argv(v, f"{at}[{i}]") for i, v in enumerate(value))


def _working_directory(value: Any, at: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationInvalid(at, "a repository-relative directory")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationInvalid(at, f"{value!r} leaves the repository")
    return str(path)


def _http_url(value: str, at: str) -> None:
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as e:
        raise ConfigurationInvalid(at, f"not a URL: {e}") from e
    if url.scheme not in ("http", "https") or not url.hostname or port is None:
        raise ConfigurationInvalid(at, "an http(s) URL naming its host and port")


def _text(doc: Mapping[str, Any], key: str, at: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigurationInvalid(f"{at}.{key}", "required, a non-empty string")
    return value


def _mapping(doc: Mapping[str, Any], key: str, at: str) -> Mapping[str, Any]:
    value = doc.get(key)
    if not isinstance(value, Mapping):
        raise ConfigurationInvalid(f"{at}.{key}", "required, a mapping")
    return value


# --- reading a stored record ---


def parse_configuration(doc: Mapping[str, Any]) -> DevelopmentConfiguration:
    """A stored Development Configuration, as Outcome Evaluation's runner and the inherited
    baseline read it. An unknown major version is refused before anything else is read."""
    version = doc.get("api_version")
    match = _API_MAJOR.match(version) if isinstance(version, str) else None
    if match is None:
        raise ConfigurationInvalid("api_version", f"{version!r} is not a Development Configuration")
    if match.group(1) != "1":
        raise UnknownConfigurationVersion("api_version", f"{version} is not a version this reads")
    configuration = _mapping(doc, "configuration", "")
    revision = configuration.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ConfigurationInvalid("configuration.revision", "required, a positive integer")
    commit = _text(configuration, "validated_at_commit", "configuration")
    if not _COMMIT.match(commit):
        raise ConfigurationInvalid("configuration.validated_at_commit", "a Git commit")
    project_type, target, stack, commands = parse_technical(
        _mapping(configuration, "technical", "configuration")
    )
    sources = configuration.get("instruction_sources", [])
    if not isinstance(sources, list):
        raise ConfigurationInvalid("configuration.instruction_sources", "a list")
    quality = configuration.get("quality") or {}
    workspace = configuration.get("workspace") or {}
    return DevelopmentConfiguration(
        project_id=_text(configuration, "project_id", "configuration"),
        revision=revision,
        validated_at_commit=commit,
        project_type=project_type,
        target=target,
        stack=stack,
        commands=commands,
        instruction_sources=tuple(
            InstructionSource(s["path"], s["digest"], s["at_commit"]) for s in sources
        ),
        workspace_mode=workspace.get("mode", "managed_clone"),
        quality_contract_ref=quality.get("contract_ref"),
        benchmark_profile_ref=configuration.get("benchmark_profile_ref"),
    )


def discover_instruction_sources(
    files: Mapping[str, bytes], commit: str
) -> tuple[InstructionSource, ...]:
    """The repository's own instruction sources at ``commit``, by name, each with its digest."""
    return tuple(
        InstructionSource(path, f"sha256:{hashlib.sha256(files[path]).hexdigest()}", commit)
        for path in INSTRUCTION_FILES
        if path in files
    )


def submission_digest(payload: Mapping[str, Any]) -> str:
    """What a submission's idempotency key stands for."""
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _commands_document(commands: Commands) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "working_directory": commands.working_directory,
        **({"install": [list(a) for a in commands.install]} if commands.install else {}),
        **({"build": [list(a) for a in commands.build]} if commands.build else {}),
        "checks": [
            {
                "id": c.id,
                "argv": list(c.argv),
                **(
                    {"requires_environment": list(c.requires_environment)}
                    if c.requires_environment
                    else {}
                ),
                **({"findings": c.findings} if c.findings else {}),
            }
            for c in commands.checks
        ],
    }
    if commands.start is not None:
        s = commands.start
        doc["start"] = {
            "working_directory": s.working_directory,
            **({"install": [list(a) for a in s.install]} if s.install else {}),
            **({"build": [list(a) for a in s.build]} if s.build else {}),
            "start": list(s.start),
            "readiness": {
                "kind": s.readiness.kind,
                "target": s.readiness.target,
                "timeout_seconds": _number(s.readiness.timeout_seconds),
            },
            "entry_points": [{"kind": e.kind, "url": e.url} for e in s.entry_points],
            **(
                {"evaluation_environment": dict(s.evaluation_environment)}
                if s.evaluation_environment
                else {}
            ),
        }
    return doc


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def checks_needing(environment: Iterable[str], commands: Commands) -> list[str]:
    """The checks whose declared environment isn't all present: UNVERIFIED by declaration,
    never by an exit status (a skipped test exits 0)."""
    present = set(environment)
    return [c.id for c in commands.checks if not set(c.requires_environment) <= present]

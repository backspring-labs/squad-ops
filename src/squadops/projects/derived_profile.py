"""The derived development profile: contract 8 (SIP-0112 H.4, H.6).

What the squad's roles depend on in a repository-backed product, read from its tree at the commit a
Development Configuration revision was validated against, from that revision, and from the
inherited baseline captured there:
- its languages and package managers;
- its test runners: what each covers, where its tests live, its whole-suite command, how it is
  scoped to one file, and the reader that names its tests one by one (#2609);
- its lint tools and their findings readers;
- the toolchains its checks need, read from the baseline's own evidence;
- whether it declares how it starts (contract 7), and the public surfaces a criterion may assert on;
- the blueprint it follows, if any, and that blueprint's client routes;
- which files are tests, and which support them;
- each gap: what the squad can't serve, what it stops and what would close it.

The MacBook lane writes it. SIP-0109 §24bv reads it for a Campaign's calibration record, an
increment's acceptance on the product's own runner and the proposal's input, and SIP-0113 §10l reads
whether the product can be started for evaluation. A profile is never edited. A new configuration
revision or a new baseline capture derives a new one, and a unit reads the one at the commit and
revision it pinned.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from squadops.sandbox.findings import READERS

PROFILE_SCHEMA = "derived-profile/v1"
_SCHEMA_MAJOR = re.compile(r"^derived-profile/v(\d+)$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")

BLOCKING, DISCLOSED = "blocking", "disclosed"
#: Each gap contract 8 names, with the kinds it may take and what it stops as each (H.6's table).
#: Every blocking gap refuses a Campaign's start (SIP-0109 §24bv point 1). One that stops ``work``
#: also refuses, before dispatch, a Cycle whose footprint meets its paths; one that stops
#: ``campaigns`` leaves a standalone Cycle alone. A disclosed gap refuses nothing: it is reported,
#: and recorded with each run whose work it applies to.
GAPS: Mapping[str, Mapping[str, str]] = {
    "no_check_ran": {BLOCKING: "work"},
    "missing_toolchain": {BLOCKING: "work", DISCLOSED: "verification"},
    "test_files_unclassed": {BLOCKING: "campaigns"},
    "missing_environment": {DISCLOSED: "verification"},
    "no_start_declaration": {DISCLOSED: "outcome_evaluation"},
    "no_test_runner": {DISCLOSED: "squad_tests"},
    "runner_not_authored": {DISCLOSED: "squad_tests"},
    "runner_not_scopable": {DISCLOSED: "criterion_scoping"},
    "no_test_id_reader": {DISCLOSED: "per_test_reading"},
    "lint_without_reader": {DISCLOSED: "per_finding_comparison"},
}
RUNNERS = ("pytest", "unittest", "vitest", "jest", "other")
#: A public surface a criterion may assert on (§24bv point 5): a base URL the start declaration
#: serves, a command-line entry point, or a package's public interface.
SURFACES: Mapping[str, str] = {
    "http_base": "url",
    "ui_base": "url",
    "command": "argv",
    "package": "name",
}
#: What a one-file argv names its file by: its repository-relative path, or its file name.
FILE_PLACEHOLDERS = ("{path}", "{name}")


class ProfileInvalid(ValueError):
    """A derived profile that can't be read, naming its field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


class UnknownProfileVersion(ProfileInvalid):
    """A major version this reader doesn't know: refused, reading none of it (§8.2.1)."""


class StaleProfile(ProfileInvalid):
    """A profile derived at another commit or revision than the one a unit pinned."""


@dataclass(frozen=True)
class Language:
    name: str
    package_manager: str | None
    manifests: tuple[str, ...]


@dataclass(frozen=True)
class Runner:
    runner: str
    #: The Development Configuration's checks that run it.
    checks: tuple[str, ...]
    #: The product paths its tests exercise.
    covers: tuple[str, ...]
    #: Where it discovers tests, and the file names it takes as tests.
    roots: tuple[str, ...]
    file_pattern: str
    suite_argv: tuple[str, ...]
    #: Scoped to one test file through a placeholder (``FILE_PLACEHOLDERS``); ``None`` when it
    #: can't be, which is a ``runner_not_scopable`` gap.
    single_file_argv: tuple[str, ...] | None
    #: The findings reader that names its tests one by one; ``None`` reads a file's result whole.
    test_ids: str | None
    support_files: tuple[str, ...]


@dataclass(frozen=True)
class Lint:
    check: str
    tool: str
    findings: str | None


@dataclass(frozen=True)
class Toolchain:
    name: str
    required_by: tuple[str, ...]
    available: bool


@dataclass(frozen=True)
class Surface:
    kind: str
    url: str | None = None
    argv: tuple[str, ...] | None = None
    name: str | None = None

    def to_document(self) -> dict[str, Any]:
        key = SURFACES[self.kind]
        value = getattr(self, key)
        return {"kind": self.kind, key: list(value) if key == "argv" else value}


@dataclass(frozen=True)
class Gap:
    id: str
    kind: str
    #: The check, runner or tool it is about, when it is about one.
    subject: str | None
    #: The product paths whose work it applies to: ``("**",)`` when it isn't confined.
    paths: tuple[str, ...]
    reason: str
    closes_by: str

    @property
    def stops(self) -> str:
        """What it stops, by its id and kind (``GAPS``): never stored, so never contradicted."""
        return GAPS[self.id][self.kind]


@dataclass(frozen=True)
class DerivedProfile:
    project_id: str
    commit: str
    development_configuration_revision: int
    #: The image the baseline's checks ran on, which the toolchains were read from.
    environment_image: str
    languages: tuple[Language, ...]
    runners: tuple[Runner, ...]
    lint: tuple[Lint, ...]
    toolchains: tuple[Toolchain, ...]
    start_declared: bool
    public_surfaces: tuple[Surface, ...]
    blueprint_stack: str | None
    #: The blueprint's client routes, from the approved manifest; ``None`` with no blueprint.
    client_routes: tuple[str, ...] | None
    test_files: tuple[str, ...]
    test_support_files: tuple[str, ...]
    gaps: tuple[Gap, ...]

    @property
    def blocking(self) -> tuple[Gap, ...]:
        return tuple(g for g in self.gaps if g.kind == BLOCKING)

    def require_current(self, *, commit: str, development_configuration_revision: int) -> None:
        """Refuse this profile for a unit that pinned another commit or revision."""
        if self.commit != commit:
            raise StaleProfile("commit", f"derived at {self.commit}, and the unit pinned {commit}")
        if self.development_configuration_revision != development_configuration_revision:
            raise StaleProfile(
                "development_configuration_revision",
                f"derived at revision {self.development_configuration_revision}, and the unit "
                f"pinned revision {development_configuration_revision}",
            )

    def to_document(self) -> dict[str, Any]:
        """The record as it is stored and read (the shape the shared fixture records)."""
        return {
            "schema": PROFILE_SCHEMA,
            "project_id": self.project_id,
            "commit": self.commit,
            "development_configuration_revision": self.development_configuration_revision,
            "environment": {"image": self.environment_image},
            "languages": [
                {"name": x.name, "package_manager": x.package_manager, "manifests": [*x.manifests]}
                for x in self.languages
            ],
            "test_runners": [
                {
                    "runner": r.runner,
                    "checks": [*r.checks],
                    "covers": [*r.covers],
                    "roots": [*r.roots],
                    "file_pattern": r.file_pattern,
                    "suite_argv": [*r.suite_argv],
                    "single_file_argv": None
                    if r.single_file_argv is None
                    else [*r.single_file_argv],
                    "test_ids": r.test_ids,
                    "support_files": [*r.support_files],
                }
                for r in self.runners
            ],
            "lint": [{"check": x.check, "tool": x.tool, "findings": x.findings} for x in self.lint],
            "toolchains": [
                {"name": t.name, "required_by": [*t.required_by], "available": t.available}
                for t in self.toolchains
            ],
            "start_declared": self.start_declared,
            "public_surfaces": [s.to_document() for s in self.public_surfaces],
            "blueprint": None if self.blueprint_stack is None else {"stack": self.blueprint_stack},
            "client_routes": None if self.client_routes is None else [*self.client_routes],
            "files": {"test": [*self.test_files], "test_support": [*self.test_support_files]},
            "gaps": [
                {
                    "id": g.id,
                    "kind": g.kind,
                    "subject": g.subject,
                    "paths": [*g.paths],
                    "reason": g.reason,
                    "closes_by": g.closes_by,
                }
                for g in self.gaps
            ],
        }


# --- reading a stored record ---


def parse_profile(doc: Mapping[str, Any]) -> DerivedProfile:
    """A stored profile. An unknown major version is refused before anything else is read, and a
    field this reader doesn't know is left unread: v1 only adds fields (§8.2)."""
    schema = doc.get("schema")
    match = _SCHEMA_MAJOR.match(schema) if isinstance(schema, str) else None
    if match is None:
        raise ProfileInvalid("schema", f"{schema!r} is not a derived profile")
    if match.group(1) != "1":
        raise UnknownProfileVersion("schema", f"{schema} is not a version this reads")
    commit = _text(doc, "commit", "")
    if not _COMMIT.match(commit):
        raise ProfileInvalid("commit", "a Git commit")
    revision = doc.get("development_configuration_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ProfileInvalid("development_configuration_revision", "required, a positive integer")
    blueprint = _present(doc, "blueprint", "")
    files = _mapping(doc, "files", "")
    return DerivedProfile(
        project_id=_text(doc, "project_id", ""),
        commit=commit,
        development_configuration_revision=revision,
        environment_image=_text(_mapping(doc, "environment", ""), "image", "environment"),
        languages=tuple(_language(x, at) for at, x in _items(doc, "languages")),
        runners=tuple(_runner(x, at) for at, x in _items(doc, "test_runners")),
        lint=tuple(_lint(x, at) for at, x in _items(doc, "lint")),
        toolchains=tuple(_toolchain(x, at) for at, x in _items(doc, "toolchains")),
        start_declared=_bool(doc, "start_declared", ""),
        public_surfaces=tuple(_surface(x, at) for at, x in _items(doc, "public_surfaces")),
        blueprint_stack=None
        if blueprint is None
        else _text(_as_mapping(blueprint, "blueprint"), "stack", "blueprint"),
        client_routes=_optional_texts(doc, "client_routes", ""),
        test_files=_paths(files, "test", "files", allow_empty=True),
        test_support_files=_paths(files, "test_support", "files", allow_empty=True),
        gaps=tuple(_gap(x, at) for at, x in _items(doc, "gaps")),
    )


def _language(doc: Mapping[str, Any], at: str) -> Language:
    return Language(
        name=_text(doc, "name", at),
        package_manager=_optional_text(doc, "package_manager", at),
        manifests=_paths(doc, "manifests", at, allow_empty=True),
    )


def _runner(doc: Mapping[str, Any], at: str) -> Runner:
    runner = _vocabulary(doc, "runner", at, RUNNERS)
    single = _present(doc, "single_file_argv", at)
    single_argv = None if single is None else _argv(single, f"{at}.single_file_argv")
    if single_argv is not None and not any(p in a for a in single_argv for p in FILE_PLACEHOLDERS):
        raise ProfileInvalid(
            f"{at}.single_file_argv", f"names its file through one of {FILE_PLACEHOLDERS}"
        )
    test_ids = _optional_text(doc, "test_ids", at)
    if test_ids is not None and test_ids not in READERS:
        raise ProfileInvalid(f"{at}.test_ids", f"a findings reader ({', '.join(READERS)}) or null")
    return Runner(
        runner=runner,
        checks=_texts(doc, "checks", at),
        covers=_paths(doc, "covers", at),
        roots=_paths(doc, "roots", at),
        file_pattern=_text(doc, "file_pattern", at),
        suite_argv=_argv(_present(doc, "suite_argv", at), f"{at}.suite_argv"),
        single_file_argv=single_argv,
        test_ids=test_ids,
        support_files=_paths(doc, "support_files", at, allow_empty=True),
    )


def _lint(doc: Mapping[str, Any], at: str) -> Lint:
    findings = _optional_text(doc, "findings", at)
    if findings is not None and findings not in READERS:
        raise ProfileInvalid(f"{at}.findings", f"a findings reader ({', '.join(READERS)}) or null")
    return Lint(check=_text(doc, "check", at), tool=_text(doc, "tool", at), findings=findings)


def _toolchain(doc: Mapping[str, Any], at: str) -> Toolchain:
    return Toolchain(
        name=_text(doc, "name", at),
        required_by=_texts(doc, "required_by", at),
        available=_bool(doc, "available", at),
    )


def _surface(doc: Mapping[str, Any], at: str) -> Surface:
    kind = _vocabulary(doc, "kind", at, tuple(SURFACES))
    key = SURFACES[kind]
    if key == "argv":
        return Surface(kind, argv=_argv(_present(doc, "argv", at), f"{at}.argv"))
    if key == "url":
        return Surface(kind, url=_text(doc, "url", at))
    return Surface(kind, name=_text(doc, "name", at))


def _gap(doc: Mapping[str, Any], at: str) -> Gap:
    gap_id = _vocabulary(doc, "id", at, tuple(GAPS))
    kind = _vocabulary(doc, "kind", at, tuple(GAPS[gap_id]))
    return Gap(
        id=gap_id,
        kind=kind,
        subject=_optional_text(doc, "subject", at),
        paths=_paths(doc, "paths", at),
        reason=_text(doc, "reason", at),
        closes_by=_text(doc, "closes_by", at),
    )


# --- fields ---


def _field(at: str, key: str) -> str:
    return f"{at}.{key}" if at else key


def _present(doc: Mapping[str, Any], key: str, at: str) -> Any:
    """A required key, whose value may be null."""
    if key not in doc:
        raise ProfileInvalid(_field(at, key), "required")
    return doc[key]


def _as_mapping(value: Any, at: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProfileInvalid(at, "a mapping")
    return value


def _mapping(doc: Mapping[str, Any], key: str, at: str) -> Mapping[str, Any]:
    return _as_mapping(_present(doc, key, at), _field(at, key))


def _items(doc: Mapping[str, Any], key: str) -> list[tuple[str, Mapping[str, Any]]]:
    value = _present(doc, key, "")
    if not isinstance(value, list):
        raise ProfileInvalid(key, "a list")
    return [(f"{key}[{i}]", _as_mapping(v, f"{key}[{i}]")) for i, v in enumerate(value)]


def _text(doc: Mapping[str, Any], key: str, at: str) -> str:
    value = _present(doc, key, at)
    if not isinstance(value, str) or not value:
        raise ProfileInvalid(_field(at, key), "a non-empty string")
    return value


def _optional_text(doc: Mapping[str, Any], key: str, at: str) -> str | None:
    value = _present(doc, key, at)
    if value is None:
        return None
    return _text(doc, key, at)


def _bool(doc: Mapping[str, Any], key: str, at: str) -> bool:
    value = _present(doc, key, at)
    if not isinstance(value, bool):
        raise ProfileInvalid(_field(at, key), "true or false")
    return value


def _vocabulary(doc: Mapping[str, Any], key: str, at: str, allowed: tuple[str, ...]) -> str:
    value = _present(doc, key, at)
    if value not in allowed:
        raise ProfileInvalid(_field(at, key), f"{value!r} is not one of {', '.join(allowed)}")
    return value


def _texts(
    doc: Mapping[str, Any], key: str, at: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    value = _present(doc, key, at)
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ProfileInvalid(_field(at, key), "a list of non-empty strings")
    if not value and not allow_empty:
        raise ProfileInvalid(_field(at, key), "at least one")
    return tuple(value)


def _optional_texts(doc: Mapping[str, Any], key: str, at: str) -> tuple[str, ...] | None:
    if _present(doc, key, at) is None:
        return None
    return _texts(doc, key, at, allow_empty=True)


def _paths(
    doc: Mapping[str, Any], key: str, at: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    """Repository-relative paths or globs, none leaving the repository."""
    paths = _texts(doc, key, at, allow_empty=allow_empty)
    for path in paths:
        parts = PurePosixPath(path)
        if parts.is_absolute() or ".." in parts.parts:
            raise ProfileInvalid(_field(at, key), f"{path!r} leaves the repository")
    return paths


def _argv(value: Any, at: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(a, str) and a for a in value):
        raise ProfileInvalid(at, "an argv: a non-empty list of non-empty strings")
    return tuple(value)

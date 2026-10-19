"""Scenarios, suites and a campaign's pin (SIP-0113 §4.1, §4.7; #2413).

A scenario's version and a suite's digest are their content's hashes, as a verifier bundle's
address is (SIP-0109 §8.1). A result names the exact scenario it ran, and the same scenarios
always make the same suite. Pure: nothing here reads a store or a clock.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.scenarios.fields import CONCEPT, references


class ScenarioInvalid(ValueError):
    """A scenario or a suite whose content can't be stored as given."""


class SurfaceKind(StrEnum):
    """A surface a scenario needs, by kind (§4.1). The scenario names it; a Project's interface
    manifest, where there is one, only checks it exists."""

    HTTP_ENDPOINT = "http_endpoint"  # a method and a path from the product's declared HTTP base
    PAGE = "page"  # a path from its declared UI base


class SuiteState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class Surface:
    kind: SurfaceKind
    path: str
    method: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "path": self.path, "method": self.method}


@dataclass(frozen=True)
class Scenario:
    """A job: its goal (the only part the squad may ever see, and only in phase 2), its held-out
    steps and checks, and the surfaces it needs. Steps and checks are the runner's vocabulary
    (#2414). Here each is a mapping that names its ``action`` or its ``check``."""

    scenario_id: str
    goal: str
    surfaces: tuple[Surface, ...]
    steps: tuple[Mapping[str, Any], ...]
    checks: tuple[Mapping[str, Any], ...]
    #: Each ``Entity:concept`` the steps and checks refer to, with the names a delivery may give
    #: it (#2464; ``squadops.scenarios.fields``). In the content, so in the version: approving
    #: a suite approves its names too.
    fields: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def content(self) -> dict[str, Any]:
        content: dict[str, Any] = {
            "scenario_id": self.scenario_id,
            "goal": self.goal,
            "surfaces": [s.as_dict() for s in self.surfaces],
            "steps": [dict(s) for s in self.steps],
            "checks": [dict(c) for c in self.checks],
        }
        if self.fields:  # absent, a scenario's content and version are what they were
            content["fields"] = {concept: list(names) for concept, names in self.fields}
        return content

    @property
    def version(self) -> str:
        return _sha(self.content())


@dataclass(frozen=True)
class ScenarioSuite:
    """A content-addressed set of scenarios. Its digest is the hash of its scenarios' ids and
    versions, so it names their content and nothing else: the name is a label."""

    name: str
    scenarios: tuple[Scenario, ...]

    @property
    def digest(self) -> str:
        return _sha(sorted([s.scenario_id, s.version] for s in self.scenarios))

    def content(self) -> dict[str, Any]:
        return {"name": self.name, "scenarios": [s.content() for s in self.scenarios]}


@dataclass(frozen=True)
class SuiteRecord:
    """A stored suite: its content, and who drafted and approved it, when."""

    suite: ScenarioSuite
    state: SuiteState
    drafted_by: str
    drafted_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None

    @property
    def digest(self) -> str:
        return self.suite.digest


@dataclass(frozen=True)
class CampaignSuitePin:
    """The suite a campaign was created with (§4.7, phase 1), kept in this SIP's own record and
    keyed by the campaign. No SIP-0109 decision reads it."""

    campaign_id: str
    suite_digest: str
    pinned_by: str
    pinned_at: datetime


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioInvalid(f"{what} must be non-empty text, got {value!r}")
    return value


def _named_mappings(value: Any, key: str, what: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise ScenarioInvalid(f"{what} must be a non-empty list")
    for item in value:
        if not isinstance(item, Mapping):
            raise ScenarioInvalid(f"each of {what} is a mapping, got {item!r}")
        _text(item.get(key), f"each of {what}'s {key!r}")
    return tuple(dict(item) for item in value)


def parse_scenario(doc: Mapping[str, Any]) -> Scenario:
    scenario_id = _text(doc.get("scenario_id"), "scenario_id")
    where = f"scenario {scenario_id!r}"
    raw_surfaces = doc.get("surfaces")
    if not isinstance(raw_surfaces, Sequence) or isinstance(raw_surfaces, str) or not raw_surfaces:
        raise ScenarioInvalid(f"{where}: surfaces must be a non-empty list")
    surfaces = []
    for raw in raw_surfaces:
        if not isinstance(raw, Mapping):
            raise ScenarioInvalid(f"{where}: each surface is a mapping, got {raw!r}")
        try:
            kind = SurfaceKind(str(raw.get("kind")))
        except ValueError:
            raise ScenarioInvalid(
                f"{where}: a surface's kind is one of {[k.value for k in SurfaceKind]}, "
                f"got {raw.get('kind')!r}"
            ) from None
        path = _text(raw.get("path"), f"{where}: a surface's path")
        if not path.startswith("/"):
            raise ScenarioInvalid(f"{where}: a surface's path starts with '/', got {path!r}")
        method = raw.get("method")
        if kind is SurfaceKind.HTTP_ENDPOINT:
            method = _text(method, f"{where}: an http_endpoint surface's method").upper()
        elif method is not None:
            raise ScenarioInvalid(f"{where}: a page surface has no method")
        surfaces.append(Surface(kind, path, method))
    steps = _named_mappings(doc.get("steps"), "action", f"{where}: steps")
    checks = _named_mappings(doc.get("checks"), "check", f"{where}: checks")
    return Scenario(
        scenario_id=scenario_id,
        goal=_text(doc.get("goal"), f"{where}: goal"),
        surfaces=tuple(surfaces),
        steps=steps,
        checks=checks,
        fields=_fields(doc.get("fields"), (*steps, *checks), where),
    )


def _fields(
    raw: Any, content: tuple[Mapping[str, Any], ...], where: str
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """A scenario's concept fields (#2464): every concept its steps and checks refer to is
    declared with the names a delivery may give it, and every declared concept is used."""
    raw = raw or {}
    if not isinstance(raw, Mapping):
        raise ScenarioInvalid(f"{where}: fields is a mapping of Entity:concept to names")
    declared = []
    for concept, names in raw.items():
        if not isinstance(concept, str) or not CONCEPT.match(concept):
            raise ScenarioInvalid(f"{where}: a field is named Entity:concept, got {concept!r}")
        if (
            not isinstance(names, Sequence)
            or isinstance(names, str)
            or not names
            or not all(isinstance(n, str) and n for n in names)
        ):
            raise ScenarioInvalid(f"{where}: {concept} lists the names a delivery may give it")
        declared.append((concept, tuple(names)))
    used = references(list(content))
    if used - {c for c, _ in declared}:
        raise ScenarioInvalid(f"{where}: undeclared fields {sorted(used - set(dict(declared)))}")
    if {c for c, _ in declared} - used:
        raise ScenarioInvalid(f"{where}: unused fields {sorted(set(dict(declared)) - used)}")
    return tuple(sorted(declared))


def parse_suite(doc: Mapping[str, Any]) -> ScenarioSuite:
    """A suite from its document, as the supervisor drafts it: a name and its scenarios."""
    name = _text(doc.get("name"), "the suite's name")
    raw = doc.get("scenarios")
    if not isinstance(raw, Sequence) or isinstance(raw, str) or not raw:
        raise ScenarioInvalid("a suite holds a non-empty list of scenarios")
    scenarios = tuple(parse_scenario(s) for s in raw)
    ids = [s.scenario_id for s in scenarios]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise ScenarioInvalid(f"scenario ids are unique within a suite: {repeated} repeat")
    return ScenarioSuite(name=name, scenarios=scenarios)

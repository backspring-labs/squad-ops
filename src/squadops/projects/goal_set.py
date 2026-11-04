"""A Project's goal set (SIP-0115 §4, slice 1, #2884): what the Project should come to do.

A versioned record beside the Project Record, keyed by the Project's id:
- the goal: one statement;
- expected results: what the owner will accept as the goal met, each with the surface it can be
  observed at, or ``none`` with the reason;
- constraints and out of scope: plain statements;
- the backlog: ordered items, each naming the expected results it serves. The order is the
  list's, so a reorder is a revision like any other edit;
- candidates: what was found along the way, which nobody has ordered yet.

A revision is never edited. Any change, a reorder included, is the next revision, with its
author and reason (as a Development Configuration revision is, SIP-0112 §B.5). A Project has one
active goal set: its latest revision (Q44).

Ids are the author's, never minted or renumbered here, so an item keeps its id, and its history,
when it moves. Each list's ids are unique, and a backlog item and a candidate never share one, so a
candidate can keep its id when it is promoted (slice 3) and no id names two things (SIP-0115
§10a).

Nothing derived is stored: an item's status is read from each Campaign's control log (§4,
slice 2), and no field here holds one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from squadops.projects.development_configuration import submission_digest

if TYPE_CHECKING:
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.goal_sets import GoalSetRegistryPort

API_VERSION = "squadops.project-goal-set/v1"
_API_MAJOR = re.compile(r"^squadops\.project-goal-set/v(\d+)$")

#: Where an expected result can be observed (§4). ``none`` carries the reason it can't be.
SURFACE_KINDS = ("http_endpoint", "page", "command", "package_interface", "none")
_NO_SURFACE = "none"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_GOAL_SET_KEYS = frozenset(
    {
        "api_version",
        "goal",
        "expected_results",
        "constraints",
        "out_of_scope",
        "backlog",
        "candidates",
    }
)


class GoalSetInvalid(ValueError):
    """A goal set that can't be recorded or read, naming its field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


@dataclass(frozen=True)
class Surface:
    kind: str
    #: What is observed there: the endpoint, the page's route, the command, the interface.
    ref: str | None = None
    #: Why an expected result has no surface (``kind == "none"`` only).
    reason: str | None = None


@dataclass(frozen=True)
class ExpectedResult:
    id: str
    statement: str
    surface: Surface


@dataclass(frozen=True)
class BacklogItem:
    id: str
    title: str
    serves: tuple[str, ...]
    description: str = ""
    size: str | None = None


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    found_by: str
    found_at: datetime
    description: str = ""
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoalSet:
    """One revision's content. The backlog's order is its tuple's."""

    goal: str
    expected_results: tuple[ExpectedResult, ...] = ()
    constraints: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    backlog: tuple[BacklogItem, ...] = ()
    candidates: tuple[Candidate, ...] = ()

    def to_document(self) -> dict[str, Any]:
        """The goal set as it is stored and read, and as ``parse_goal_set`` takes it back: a
        revision read with ``goals show`` can be edited and submitted as the next one."""
        return {
            "api_version": API_VERSION,
            "goal": self.goal,
            "expected_results": [
                {"id": r.id, "statement": r.statement, "surface": _surface_document(r.surface)}
                for r in self.expected_results
            ],
            "constraints": list(self.constraints),
            "out_of_scope": list(self.out_of_scope),
            "backlog": [
                {
                    "id": i.id,
                    "title": i.title,
                    "description": i.description,
                    "serves": list(i.serves),
                    **({"size": i.size} if i.size is not None else {}),
                }
                for i in self.backlog
            ],
            "candidates": [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "found_by": c.found_by,
                    "found_at": c.found_at.isoformat(),
                    "evidence": list(c.evidence),
                }
                for c in self.candidates
            ],
        }


@dataclass(frozen=True)
class GoalSetRevision:
    """One immutable revision of a Project's goal set, with who wrote it and why."""

    project_id: str
    revision: int
    goal_set: GoalSet
    author: str
    reason: str
    created_at: datetime
    #: Where the change came from, when it came from a conversation (§6): a Buzz statement's
    #: link, an issue, a review.
    source_ref: str | None = None


# --- reading a submitted or stored goal set ---


def parse_goal_set(doc: Any) -> GoalSet:
    """A goal set, submitted or stored. Everything is refused naming its field rather than
    dropped: an unknown key is a misspelt one, and a silently dropped list reads as emptied."""
    if not isinstance(doc, Mapping):
        raise GoalSetInvalid("goal_set", "a mapping")
    _known_keys(doc, _GOAL_SET_KEYS, "goal_set")
    version = doc.get("api_version", API_VERSION)
    match = _API_MAJOR.match(version) if isinstance(version, str) else None
    if match is None or match.group(1) != "1":
        raise GoalSetInvalid("api_version", f"{version!r} is not a goal set version this reads")
    expected_results = tuple(
        _expected_result(r, f"expected_results[{i}]")
        for i, r in enumerate(_list(doc, "expected_results"))
    )
    _unique([r.id for r in expected_results], "expected_results")
    backlog = tuple(_backlog_item(b, f"backlog[{i}]") for i, b in enumerate(_list(doc, "backlog")))
    _unique([b.id for b in backlog], "backlog")
    known = {r.id for r in expected_results}
    for i, item in enumerate(backlog):
        unknown = [s for s in item.serves if s not in known]
        if unknown:
            raise GoalSetInvalid(
                f"backlog[{i}].serves", f"{unknown} name no expected result in this goal set"
            )
    candidates = tuple(
        _candidate(c, f"candidates[{i}]") for i, c in enumerate(_list(doc, "candidates"))
    )
    _unique([c.id for c in candidates], "candidates")
    shared = sorted({b.id for b in backlog} & {c.id for c in candidates})
    if shared:
        raise GoalSetInvalid(
            "candidates", f"{shared} name a backlog item too: a candidate's id is its own"
        )
    return GoalSet(
        goal=_text(doc, "goal", ""),
        expected_results=expected_results,
        constraints=_statements(doc, "constraints"),
        out_of_scope=_statements(doc, "out_of_scope"),
        backlog=backlog,
        candidates=candidates,
    )


def _expected_result(doc: Any, at: str) -> ExpectedResult:
    _require_mapping(doc, at, {"id", "statement", "surface"})
    surface = doc.get("surface")
    where = f"{at}.surface"
    if not isinstance(surface, Mapping):
        raise GoalSetInvalid(where, "required: its kind, and what is observed there or why not")
    _known_keys(surface, frozenset({"kind", "ref", "reason"}), where)
    kind = surface.get("kind")
    if kind not in SURFACE_KINDS:
        raise GoalSetInvalid(f"{where}.kind", f"one of {SURFACE_KINDS}, not {kind!r}")
    if kind == _NO_SURFACE:
        if surface.get("ref") is not None:
            raise GoalSetInvalid(f"{where}.ref", "a result with no surface names nothing there")
        parsed = Surface(kind, reason=_text(surface, "reason", where))
    else:
        if surface.get("reason") is not None:
            raise GoalSetInvalid(f"{where}.reason", "only a result with no surface gives a reason")
        parsed = Surface(kind, ref=_text(surface, "ref", where))
    return ExpectedResult(id=_id(doc, at), statement=_text(doc, "statement", at), surface=parsed)


def _backlog_item(doc: Any, at: str) -> BacklogItem:
    _require_mapping(doc, at, {"id", "title", "description", "serves", "size"})
    serves = doc.get("serves")
    if not isinstance(serves, list) or not serves or not all(isinstance(s, str) for s in serves):
        raise GoalSetInvalid(
            f"{at}.serves", "the ids of the expected results it serves, at least one"
        )
    if len(set(serves)) != len(serves):
        raise GoalSetInvalid(f"{at}.serves", f"each expected result once: {serves}")
    size = doc.get("size")
    if size is not None and (not isinstance(size, str) or not size.strip()):
        raise GoalSetInvalid(f"{at}.size", "a note, or absent")
    return BacklogItem(
        id=_id(doc, at),
        title=_text(doc, "title", at),
        serves=tuple(serves),
        description=_optional_text(doc, "description", at),
        size=size,
    )


def _candidate(doc: Any, at: str) -> Candidate:
    _require_mapping(doc, at, {"id", "title", "description", "found_by", "found_at", "evidence"})
    found_at = doc.get("found_at")
    try:
        when = (
            found_at
            if isinstance(found_at, datetime)
            else datetime.fromisoformat(found_at)
            if isinstance(found_at, str)
            else None
        )
    except ValueError:
        when = None
    if when is None or when.tzinfo is None:
        raise GoalSetInvalid(f"{at}.found_at", "an ISO 8601 time with its offset")
    evidence = doc.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(e, str) and e for e in evidence):
        raise GoalSetInvalid(f"{at}.evidence", "a list of what it cites, each a non-empty string")
    return Candidate(
        id=_id(doc, at),
        title=_text(doc, "title", at),
        found_by=_text(doc, "found_by", at),
        found_at=when,
        description=_optional_text(doc, "description", at),
        evidence=tuple(evidence),
    )


def _surface_document(surface: Surface) -> dict[str, str]:
    if surface.kind == _NO_SURFACE:
        return {"kind": surface.kind, "reason": surface.reason or ""}
    return {"kind": surface.kind, "ref": surface.ref or ""}


def _require_mapping(doc: Any, at: str, keys: set[str]) -> None:
    if not isinstance(doc, Mapping):
        raise GoalSetInvalid(at, "a mapping")
    _known_keys(doc, frozenset(keys), at)


def _known_keys(doc: Mapping[str, Any], keys: frozenset[str], at: str) -> None:
    unknown = sorted(str(k) for k in doc if k not in keys)
    if unknown:
        raise GoalSetInvalid(at, f"unknown field(s) {unknown}; it holds {sorted(keys)}")


def _id(doc: Mapping[str, Any], at: str) -> str:
    value = _text(doc, "id", at)
    if not _ID.match(value):
        raise GoalSetInvalid(
            f"{at}.id", f"{value!r} is not an id: letters, digits, '.', '_' or '-', up to 64"
        )
    return value


def _unique(ids: list[str], at: str) -> None:
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise GoalSetInvalid(at, f"each id is unique in its list: {repeated} repeat")


def _list(doc: Mapping[str, Any], key: str) -> list[Any]:
    value = doc.get(key, [])
    if not isinstance(value, list):
        raise GoalSetInvalid(key, "a list")
    return value


def _statements(doc: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = _list(doc, key)
    for i, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise GoalSetInvalid(f"{key}[{i}]", "a statement, a non-empty string")
    return tuple(values)


def _text(doc: Mapping[str, Any], key: str, at: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GoalSetInvalid(f"{at}.{key}" if at else key, "required, a non-empty string")
    return value


def _optional_text(doc: Mapping[str, Any], key: str, at: str) -> str:
    value = doc.get(key, "")
    if not isinstance(value, str):
        raise GoalSetInvalid(f"{at}.{key}", "a string")
    return value


# --- writing the next revision ---


async def revise_goal_set(
    project_id: str,
    submission: Mapping[str, Any],
    *,
    expected_revision: int,
    reason: str,
    source_ref: str | None,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
    author: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> tuple[GoalSetRevision, bool]:
    """Validate ``submission`` and record it as the Project's next goal-set revision, which must
    follow ``expected_revision`` (0 for the first). Returns it and whether this replayed an
    earlier write under the same key.

    Raises:
        ProjectNotFoundError: no such Project.
        GoalSetInvalid: the submission, naming its field.
        StaleGoalSetRevisionError: another revision was written first.
        RegistrationKeyConflictError: the key wrote different content.
    """
    await projects.get_project(project_id)
    if not reason.strip():
        raise GoalSetInvalid("reason", "required: why this revision is written")
    goal_set = parse_goal_set(submission)
    revision = GoalSetRevision(
        project_id=project_id,
        revision=expected_revision + 1,
        goal_set=goal_set,
        author=author,
        reason=reason,
        created_at=now or datetime.now(UTC),
        source_ref=source_ref,
    )
    return await goal_sets.record_revision(
        revision,
        idempotency_key=idempotency_key,
        request_hash=submission_digest(
            {
                "project_id": project_id,
                "expected_revision": expected_revision,
                "reason": reason,
                "source_ref": source_ref,
                "goal_set": goal_set.to_document(),
            }
        ),
    )

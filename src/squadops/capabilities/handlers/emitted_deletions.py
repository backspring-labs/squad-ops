"""A step's removals, judged against its view and its grant before anything is handed on (#2612,
SIP-0112 H.23).

A removal is taken only as the removal of a path the task's bounded view holds: the product's tree
at the pinned commit, as its ``source_repository`` input lists it. Each is refused by name, and the
emission with it, when:
- the step may remove nothing (``TaskType.deletion_grant``), or the run changes no product;
- the fence is malformed (a body inside it, an unsafe path);
- the path isn't in the product's tree at the commit, or an earlier task already removed it;
- it is a file no task changes (a binary file, a generated lockfile);
- the step's grant is the suite alone and none of the product's runners holds the path as a test;
- the same emission writes the path too.

All or nothing, as an anchored edit's transaction is (SIP-0107 §14): a removal refused is a defect
in the emission, and the step's correction is told which and why. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.handlers.fenced_parser import extract_fenced_deletions
from squadops.capabilities.handlers.source_repository import source_backed
from squadops.cycles.deletions import DELETIONS_KEY, DELETIONS_REFUSED_KEY
from squadops.cycles.emission_integrity import EMISSION_FAILURE_DELETION_REFUSED
from squadops.projects.derived_profile import runner_holds
from squadops.tasks.task_types import DeletionGrant, deletion_grant

REFUSED_NOT_GRANTED = "not_granted"
REFUSED_NO_PRODUCT = "no_product"
REFUSED_NOT_IN_VIEW = "not_in_view"
REFUSED_ALREADY_REMOVED = "already_removed"
REFUSED_HELD_BACK = "held_back"
REFUSED_OUTSIDE_GRANT = "outside_grant"
REFUSED_WRITTEN_TOO = "written_too"


@dataclass(frozen=True)
class DeletionRefusal:
    path: str
    reason: str
    detail: str

    def line(self) -> str:
        return f"`{self.path}`: {self.detail} ({self.reason})"

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class DeletionReading:
    """A response's removals as its step may take them: every one accepted, or the refusals."""

    accepted: tuple[str, ...] = ()
    refused: tuple[DeletionRefusal, ...] = ()

    @property
    def found(self) -> bool:
        return bool(self.accepted or self.refused)

    def outputs(self) -> dict[str, Any]:
        """What the step's outputs carry: the accepted removals, or the refusals as its emission
        failure. Empty when the response removes nothing."""
        if self.refused:
            return {
                DELETIONS_REFUSED_KEY: [r.as_dict() for r in self.refused],
                "emission_failure": {
                    "reason": EMISSION_FAILURE_DELETION_REFUSED,
                    "refusals": [r.line() for r in self.refused],
                },
            }
        return {DELETIONS_KEY: list(self.accepted)} if self.accepted else {}

    def error(self) -> str:
        return "the emission's removals were refused: " + "; ".join(r.line() for r in self.refused)


def read_deletions(
    content: str, inputs: Mapping[str, Any], task_type: object, written: Iterable[str]
) -> DeletionReading:
    """The response's deletion fences, judged for ``task_type`` against ``inputs``' view.
    ``written`` is every path the same emission writes."""
    fenced = extract_fenced_deletions(content)
    if not fenced.found:
        return DeletionReading()
    refused = [DeletionRefusal(p, reason, detail) for p, reason, detail in fenced.malformed]
    grant = deletion_grant(task_type)
    if grant is None:
        why = (REFUSED_NOT_GRANTED, f"a {task_type} step removes no file")
        return DeletionReading(
            refused=(*refused, *(DeletionRefusal(p, *why) for p in fenced.paths))
        )
    if not source_backed(inputs):
        why = (
            REFUSED_NO_PRODUCT,
            "a removal is of a file of a product's repository, and this run changes none",
        )
        return DeletionReading(
            refused=(*refused, *(DeletionRefusal(p, *why) for p in fenced.paths))
        )
    view = inputs["source_repository"]
    emitted = frozenset(written)
    for path in fenced.paths:
        refusal = _refusal(path, view, grant, emitted)
        if refusal is not None:
            refused.append(refusal)
    if refused:
        return DeletionReading(refused=tuple(refused))
    return DeletionReading(accepted=fenced.paths)


def _refusal(
    path: str, view: Mapping[str, Any], grant: DeletionGrant, written: frozenset[str]
) -> DeletionRefusal | None:
    commit = str(view.get("commit", ""))[:12]
    if path in written:
        return DeletionRefusal(
            path, REFUSED_WRITTEN_TOO, "the same emission writes this path, so it can't remove it"
        )
    if path in (view.get("deleted") or ()):
        return DeletionRefusal(path, REFUSED_ALREADY_REMOVED, "an earlier task already removed it")
    if path not in (view.get("paths") or ()):
        return DeletionRefusal(
            path, REFUSED_NOT_IN_VIEW, f"the product's tree at {commit} has no such file"
        )
    if path in (view.get("held_back") or ()):
        return DeletionRefusal(
            path,
            REFUSED_HELD_BACK,
            "a binary file or a generated lockfile, which no task changes",
        )
    if grant is DeletionGrant.TESTS and not _a_runner_holds(view, path):
        return DeletionRefusal(
            path,
            REFUSED_OUTSIDE_GRANT,
            "a test step removes only a test one of the product's runners holds "
            f"({_runners(view) or 'it has none'})",
        )
    return None


def _a_runner_holds(view: Mapping[str, Any], path: str) -> bool:
    return any(
        runner_holds(r.get("roots") or (), str(r.get("file_pattern") or ""), path)
        for r in view.get("runners") or ()
        if isinstance(r, Mapping) and r.get("file_pattern")
    )


def _runners(view: Mapping[str, Any]) -> str:
    return ", ".join(
        f"`{r.get('file_pattern')}` under {', '.join(f'`{root}`' for root in r.get('roots') or ())}"
        for r in view.get("runners") or ()
        if isinstance(r, Mapping)
    )


def without_removed(inputs: dict[str, Any], removed: Iterable[str]) -> dict[str, Any]:
    """``inputs`` with the paths the emission removes taken out of its expected artifacts: the
    task named the file to be shown it, and removing it is what it did with it. Unchanged when
    the emission removes nothing."""
    gone = set(removed)
    if not gone or not inputs.get("expected_artifacts"):
        return inputs
    return {
        **inputs,
        "expected_artifacts": [e for e in inputs["expected_artifacts"] if e not in gone],
    }

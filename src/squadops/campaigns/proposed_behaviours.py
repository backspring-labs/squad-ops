"""The qa author's proposal outlet (#1884, the owner's rule; the 2.1 plan §7 item 4).

"Unsupported desirable behavior must be returned as a proposal, not encoded in a test that gates or
repairs the current run." A ``qa.test`` author in an increment may emit one fenced
``proposed_behaviours.yaml`` block: behaviour it judged desirable that nothing accepted requires.
The block is stored as an artifact of its own type, never written to a workspace and never run,
and the campaign's next proposal is shown its entries (SIP-0109 §24ay).

Only ``qa.test`` may emit it. A ``qa.test_repair`` re-authors a broken suite; a block in its
emission is kept out of its artifacts and named in its evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import yaml

PROPOSED_BEHAVIOURS_FILENAME = "proposed_behaviours.yaml"
#: Never a workspace type: ``delivered_tree.WORKSPACE_ARTIFACT_TYPES`` excludes it, and the
#: correction runner's retest deny-list and ``failed_task_artifacts`` name it.
QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE = "qa_proposed_behaviours"
#: The validation row a malformed block raises, so a self-evaluation pass returns it.
OUTLET_CHECK = "proposed_behaviours"
MAX_ENTRIES = 10
_FIELDS = ("behaviour", "why", "surface_kind", "surface")
_SURFACE_KINDS = ("endpoint", "client_route")


class ProposedBehavioursError(ValueError):
    """A block that does not have the outlet's shape."""


@dataclass(frozen=True)
class ProposedBehaviour:
    behaviour: str
    why: str
    surface_kind: str
    surface: str


def is_outlet_file(name: str) -> bool:
    """Whether an emitted file is the outlet's block, wherever the author put it."""
    return name.rsplit("/", 1)[-1] == PROPOSED_BEHAVIOURS_FILENAME


def parse_proposed_behaviours(text: str) -> tuple[ProposedBehaviour, ...]:
    """The entries the block proposes.

    Raises:
        ProposedBehavioursError: on anything but a top-level ``proposed_behaviours`` list of 1 to
            10 entries, each with exactly the four fields, non-blank, and a known surface kind.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ProposedBehavioursError(
            f"{PROPOSED_BEHAVIOURS_FILENAME} is not valid YAML: {e}"
        ) from e
    if not isinstance(doc, dict) or set(doc) != {"proposed_behaviours"}:
        raise ProposedBehavioursError(
            f"{PROPOSED_BEHAVIOURS_FILENAME} has one top-level key, proposed_behaviours"
        )
    entries = doc["proposed_behaviours"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ProposedBehavioursError(
            f"proposed_behaviours is a list of 1 to {MAX_ENTRIES} entries"
        )
    out: list[ProposedBehaviour] = []
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != set(_FIELDS):
            raise ProposedBehavioursError(f"entry {i} has exactly the fields {', '.join(_FIELDS)}")
        values = {k: str(entry[k]).strip() if entry[k] is not None else "" for k in _FIELDS}
        blank = [k for k in _FIELDS if not values[k]]
        if blank:
            raise ProposedBehavioursError(f"entry {i} leaves {', '.join(blank)} blank")
        if values["surface_kind"] not in _SURFACE_KINDS:
            raise ProposedBehavioursError(
                f"entry {i}'s surface_kind is one of {', '.join(_SURFACE_KINDS)}"
            )
        out.append(ProposedBehaviour(**values))
    return tuple(out)


def stored_form(entries: Iterable[ProposedBehaviour]) -> str:
    """The artifact's content: the parsed entries, normalized."""
    return yaml.safe_dump(
        {"proposed_behaviours": [dict(vars(e)) for e in entries]}, sort_keys=False
    )


def merged_entries(contents: Iterable[str]) -> list[dict[str, str]]:
    """The entries of stored artifacts, in order, the first of each ``behaviour`` kept and at
    most ``MAX_ENTRIES``: what a proposal is shown. A stored artifact is the parser's own
    output, so one that no longer parses is a defect and raises."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for content in contents:
        for entry in parse_proposed_behaviours(content):
            if entry.behaviour not in seen and len(out) < MAX_ENTRIES:
                seen.add(entry.behaviour)
                out.append(dict(vars(entry)))
    return out


def proposal_lines(entries: Iterable[Mapping[str, Any]]) -> str:
    """The entries as the proposal section's index: data only, the prose the asset's (#448)."""
    return "\n".join(
        f"- {e['behaviour']} ({e['surface_kind']} `{e['surface']}`): {e['why']}" for e in entries
    )

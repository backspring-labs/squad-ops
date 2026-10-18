"""A scenario's fields, named by concept and resolved per delivery (SIP-0113 §10c; #2464).

The PRD leaves the data model to each delivery's interface manifest (its §8), and deliveries name
the same field differently: ``meeting_location`` in most of the canonical stack's, ``location`` in
some, ``meetingLocation`` in some of Next.js's. So a scenario that sends or reads a field names its
concept (``@Run:location``) and lists the names a delivery may give it. The evaluation service
resolves each concept against the evaluated delivery's own manifest before anything runs. A
delivery that declares none of the names can't be evaluated on that scenario: it is
``blocked_unverified``, ``surface_absent``, never ``failed``.

A reference is a JSON key or a string value that is exactly ``@Entity:concept``, or one segment of
a dotted JSON path (``participants.0.@Participant:name``).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from typing import Any

#: ``Entity:concept``: the manifest's entity name, and the PRD's word for the field.
CONCEPT = re.compile(r"^[A-Z][A-Za-z0-9]*:[a-z][a-z0-9_]*$")
_PREFIX = "@"


class FieldAbsent(Exception):
    """The evaluated delivery declares none of a concept's names."""

    def __init__(self, concept: str, names: Sequence[str]) -> None:
        super().__init__(f"the delivery declares no field for {concept} (one of {list(names)})")
        self.concept = concept


def references(value: Any) -> set[str]:
    """Every ``Entity:concept`` a step's or check's content refers to."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            found |= references(key) | references(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= references(item)
    elif isinstance(value, str):
        for segment in value.split("."):
            if segment.startswith(_PREFIX) and CONCEPT.match(segment[1:]):
                found.add(segment[1:])
    return found


def resolve(
    content: Any, fields: Mapping[str, Sequence[str]], declared: Mapping[str, Collection[str]]
) -> Any:
    """``content`` with each concept replaced by the name the delivery declares for it: the first
    of the scenario's names that the entity has. ``declared`` maps each entity to its field
    names. Raises ``FieldAbsent`` for a concept the delivery doesn't declare."""
    chosen: dict[str, str] = {}
    for concept, names in fields.items():
        entity = concept.split(":", 1)[0]
        name = next((n for n in names if n in declared.get(entity, ())), None)
        if name is None:
            raise FieldAbsent(concept, names)
        chosen[concept] = name

    def segment(text: str) -> str:
        return chosen.get(text[1:], text) if text.startswith(_PREFIX) else text

    def walk(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {walk(k): walk(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [walk(v) for v in value]
        if isinstance(value, str):
            return ".".join(segment(part) for part in value.split("."))
        return value

    return walk(content)

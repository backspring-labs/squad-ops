"""A scenario's fields, named by concept and resolved per delivery (SIP-0113 §10c; #2464).

The PRD leaves the data model to each delivery's interface manifest (its §8), and deliveries name
the same field differently: ``meeting_location`` in most of the canonical stack's, ``location`` in
some, ``meetingLocation`` in some of Next.js's. So a scenario that sends or reads a field names its
concept (``@Run:location``) and lists the names a delivery may give it. The evaluation service
resolves each concept against the evaluated delivery's own manifest before anything runs: the first
of the scenario's names that the delivery declares, or else the scenario's first name.

A manifest's fields are a hint, not a list of what the app holds. Read live (2026-10-18): an
increment that implemented capacity stored no manifest of its own, so the one it built on, without
``capacity``, was all there was to read; and one delivery's manifest left ``participants`` off a run
its responses carry. So an undeclared concept is sent under its first name and the scenario runs: a
delivery without the feature then fails it, which is what the reading needs.

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
    of the scenario's names that the entity has, or else the scenario's first name. ``declared``
    maps each entity to its field names."""
    chosen: dict[str, str] = {}
    for concept, names in fields.items():
        entity = concept.split(":", 1)[0]
        chosen[concept] = next((n for n in names if n in declared.get(entity, ())), names[0])

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

"""The status an error code's name commits it to: the one home of the convention (#1031).

The 1.6.1 shakedown (``cyc_6b2de19a868e``) mapped ``participant_not_found`` to 400, which the
owner ruled a clear misuse: the error is a failed lookup, and its name says so. The recorded
decision weighed 400 against a silent no-op, so 404 never entered the author's frame.

A name that says what kind of failure it is says which status answers it. Only names whose
convention is unambiguous are classified. Any other name is the author's call, and is not
checked: a rule that guessed would trade one dice-roll for another.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Convention:
    statuses: frozenset[int]
    #: What the name says the failure is, for the finding's message.
    kind: str


_CONVENTIONS: tuple[tuple[re.Pattern[str], Convention], ...] = (
    (
        re.compile(r"(^|_)(not_found|does_not_exist|no_such)(_|$)"),
        Convention(frozenset({404}), "a lookup that found nothing"),
    ),
    (
        re.compile(r"(^|_)(conflict|already|duplicate)(_|$)"),
        Convention(frozenset({409}), "a request that conflicts with the resource's state"),
    ),
    (
        re.compile(r"(^|_)(invalid|validation|malformed)(_|$)"),
        Convention(frozenset({400, 422}), "a malformed request"),
    ),
)


def error_convention(code: str) -> Convention | None:
    """The convention an error code's name commits it to, or ``None`` when it commits to none."""
    name = code.strip().lower()
    for pattern, convention in _CONVENTIONS:
        if pattern.search(name):
            return convention
    return None

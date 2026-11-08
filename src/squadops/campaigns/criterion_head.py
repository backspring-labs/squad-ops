"""A criterion's test run on the campaign branch's head as soon as it exists (SIP-0109 §24cz,
#2890): the record the check writes, its vocabulary, and what the next proposal reads of it.

At the ruling only a criterion's statement and observable exist; its executable test is written
by the increment cycle's qa task. Today the first reading of that test against the accepted tree
is acceptance's, at the run's delivery (``no_baseline_failure``, §8.2), on a cycle already spent.
The check runs the criterion's file on the product's own runner against the head the cycle was
pinned at, with no development emission on the tree, and records each criterion's reading here.
Until §24do (#2933) a criterion whose file passed there read as **already met**: the run ended
(``CycleEnding.CRITERIA_NOT_CHECKABLE``) and the campaign proposed anew, told which criteria the head
already met, as row 16's abandonment tells it (#2315). The owner's ruling of 2026-11-07 reads such a
pass as a test that proved nothing about the work, never as the behaviour existing, so the executor
refuses it to the suite's author and no new record holds one (``store_head_check``).

The record is the run's ``criterion_head_check`` artifact. Its ``criteria`` rows carry the same
word acceptance's ``discriminations`` carry for the same finding (``no_baseline_failure``), so
``already_met_on_head`` and ``progress.already_met`` read one vocabulary. ``already_met_on_head``
still reads that word, for a record a run stored before §24do and a cycle re-heard after it.

The sandbox run itself is ``execution.criterion_head_check``; this module is the record alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.campaigns.acceptance import DiscriminationReason

#: The artifact the check writes on the implementation run, which the campaign's hearing reads
#: for the next proposal's brief (``CampaignProgress._already_met_stated``).
CRITERION_HEAD_CHECK_ARTIFACT_TYPE = "criterion_head_check"
CRITERION_HEAD_CHECK_FILENAME = "criterion_head_check.json"
#: What ``checked_on`` names: the same runner acceptance judges on (``product_acceptance``).
CHECKED_ON = "product_runner"


class HeadReading(StrEnum):
    """One criterion's reading on the head."""

    #: Its file's tests all ran and passed on the head: already met. Acceptance would read the
    #: same file ``no_baseline_failure`` on the accepted tree, so the word is that one.
    ALREADY_MET = str(DiscriminationReason.NO_BASELINE_FAILURE)
    #: At least one of its tests failed on the head. Whether it discriminates is acceptance's to
    #: read, with the candidate beside it.
    FAILS_ON_HEAD = "fails_on_head"
    #: Nothing readable ran: the command never exited, the reader read nothing, or the file ran
    #: no test it could name. Not already met; acceptance reads it.
    NOT_RUN = str(DiscriminationReason.NOT_RUN)


@dataclass(frozen=True)
class CriterionHeadReading:
    criterion_id: str
    path: str
    reading: HeadReading

    @property
    def already_met(self) -> bool:
        return self.reading is HeadReading.ALREADY_MET

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "path": self.path,
            "reading": str(self.reading),
        }


def head_check_document(
    *,
    increment_id: str,
    head_commit: str,
    readings: Iterable[CriterionHeadReading],
    runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """The record as plain data: the increment, the head it was read on, each criterion's reading
    and each file's run (``product_suite.SuiteRun.as_dict``)."""
    return {
        "increment_id": increment_id,
        "head_commit": head_commit,
        "checked_on": CHECKED_ON,
        "criteria": [r.as_dict() for r in readings],
        "runs": [dict(r) for r in runs],
    }


def already_met_on_head(document: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The criteria the check found the head already meets, from the record, in its order. Empty
    without a record."""
    return tuple(
        str(row.get("criterion_id"))
        for row in (document or {}).get("criteria") or ()
        if isinstance(row, Mapping) and row.get("reading") == str(HeadReading.ALREADY_MET)
    )

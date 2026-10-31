"""An exposure's withdrawn instructions, read beside it (SIP-0110 Appendix A §3.8; #2179).

What bugs would these catch? A withdrawn task instruction left unmarked because only the project
section is read, though §3.8 states the rule for both; an active instruction marked; a held task,
which reached no model, marked as having used the instruction its bundle couldn't complete.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from squadops.memory.record_uses import handed_instructions, withdrawn_uses
from squadops.memory.records import withdrawn
from tests.unit.memory.test_indicators import _exposure
from tests.unit.memory.test_project_instructions import T0, _instruction

pytestmark = [pytest.mark.domain_memory]


def _records():
    gone = withdrawn(_instruction("mrec_gone", "qa.test"), by="ada", at=T0, why="harmful")
    kept = _instruction("mrec_kept", "qa.test")
    return {r.record_id: r for r in (gone, kept)}


def _section(*record_ids: str, disposition: str = "supplied") -> dict:
    return {
        "disposition": disposition,
        "supplied": [{"record_id": r, "revision": "1"} for r in record_ids],
        "unresolved": [],
    }


@pytest.mark.parametrize("section", ["task_instructions", "project_instructions"])
def test_a_withdrawn_instruction_is_marked_in_either_section_and_an_active_one_is_not(section):
    exposure = replace(_exposure("run_1", "t_qa"), **{section: _section("mrec_kept", "mrec_gone")})

    [mark] = withdrawn_uses(exposure, _records())

    assert (mark.record_id, mark.revision, mark.section, mark.withdrawn_by, mark.why) == (
        "mrec_gone", "1", section, "ada", "harmful",
    )  # fmt: skip
    assert handed_instructions(exposure) is True


def test_a_held_task_is_marked_with_nothing_it_never_received():
    exposure = replace(
        _exposure("run_1", "t_qa"),
        project_instructions=_section("mrec_gone"),
        task_instructions=_section(disposition="incomplete"),
    )

    assert withdrawn_uses(exposure, _records()) == []
    assert handed_instructions(exposure) is False

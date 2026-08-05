"""SIP-0101 Slice 1 — `cycles show` renders the replay disclosure.

The CLI reads the detail response's ``cycle_outcome.replay`` block; a dropped
or mis-keyed read is a replayed cycle presented as earned on the operator's
primary surface.
"""

from __future__ import annotations

import pytest

from squadops.cli.commands.cycles import _replay_marker_lines_from_detail

pytestmark = [pytest.mark.domain_cli]


def test_marker_lines_rendered_from_replay_block():
    data = {
        "cycle_id": "cyc_001",
        "cycle_outcome": {
            "verdict": "accepted",
            "replay": {
                "source_run_id": "run_src",
                "boundary_index": 3,
                "compatibility_set": ["contract_ref"],
            },
        },
    }
    lines = _replay_marker_lines_from_detail(data)
    assert len(lines) == 2
    assert "run_src" in lines[0]
    assert "boundary 3" in lines[0]
    assert "inherited" in lines[1]


@pytest.mark.parametrize(
    "data",
    [
        {"cycle_id": "cyc_001"},  # no outcome at all (list/legacy shape)
        {"cycle_id": "cyc_001", "cycle_outcome": None},
        {"cycle_id": "cyc_001", "cycle_outcome": {"verdict": "accepted"}},
        {"cycle_id": "cyc_001", "cycle_outcome": {"verdict": "accepted", "replay": None}},
    ],
)
def test_no_marker_for_normal_cycles(data):
    # the symmetric §4 half: a normal cycle must never render the disclosure
    assert _replay_marker_lines_from_detail(data) == []

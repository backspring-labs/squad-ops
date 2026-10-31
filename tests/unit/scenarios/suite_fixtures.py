"""A suite document as the supervisor drafts one, for the scenario store's tests (#2413).

Its steps and checks carry ``HELD_OUT``, so a test can show that marker never leaves the store
by any route but the owner's review.
"""

from __future__ import annotations

import copy

HELD_OUT = "HELD-OUT-7f3a"

SUITE = {
    "name": "group_run: joining and leaving",
    "scenarios": [
        {
            "scenario_id": "join-and-leave",
            "goal": "A participant joins a run and leaves it, and the run's list is right.",
            "surfaces": [
                {"kind": "http_endpoint", "method": "post", "path": "/runs/{run_id}/participants"},
                {"kind": "page", "path": "/runs"},
            ],
            "steps": [{"action": "http", "method": "POST", "path": "/runs", "note": HELD_OUT}],
            "checks": [{"check": "status", "equals": 201, "note": HELD_OUT}],
        },
        {
            "scenario_id": "capacity",
            "goal": "A full run refuses one more participant.",
            "surfaces": [{"kind": "http_endpoint", "method": "POST", "path": "/runs"}],
            "steps": [{"action": "http", "method": "POST", "path": "/runs", "note": HELD_OUT}],
            "checks": [{"check": "status", "equals": 409}],
        },
    ],
}


def suite_doc(**changes) -> dict:
    doc = copy.deepcopy(SUITE)
    doc.update(changes)
    return doc

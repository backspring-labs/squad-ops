"""#999: the qa task's fill-merge evidence is persisted as an artifact.

#982 computed assertion strength at the merge seam and put it in ``execution_evidence``
— which nothing persists — so the instrument added because a 7x drop had been visible in
data nobody read evaporated at runtime. ``fill_merge_evidence.json`` beside
``test_report.md`` is where the closing-claim reader reaches it without container logs.
"""

from __future__ import annotations

import json

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

pytestmark = [pytest.mark.domain_capabilities]


def test_no_fill_mode_means_no_artifact():
    """A qa task outside fill mode has no merge evidence; the handler must not bank an
    empty file that reads as measured."""
    assert QATestHandler._fill_merge_evidence_artifact({}) is None
    assert QATestHandler._fill_merge_evidence_artifact({"fill_merge": {}}) is None


def test_the_artifact_carries_the_evidence_and_is_typed_so_the_runner_skips_it():
    evidence_extra = {
        "fill_merge": {
            "counts": {"merged": 3},
            "assertion_strength": {"store_touching": 2},
            "additive_containment": ["finding"],
        },
        "self_eval_fills": [{"pass": 1}],
        "self_eval_passes": 1,
    }
    art = QATestHandler._fill_merge_evidence_artifact(evidence_extra)
    assert art["name"] == QATestHandler.FILL_MERGE_EVIDENCE_FILENAME == "fill_merge_evidence.json"
    assert art["type"] == "evidence" and art["media_type"] == "application/json"
    payload = json.loads(art["content"])
    assert payload["fill_merge"]["assertion_strength"] == {"store_touching": 2}
    assert payload["self_eval_fills"] == [{"pass": 1}] and payload["self_eval_passes"] == 1
    # The suite runner selects type == "test"; this is not a suite.
    assert QATestHandler._suite_files([art]) == []

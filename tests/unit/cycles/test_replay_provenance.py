"""SIP-0101 Slice 1 — replay evidence rails.

The rails land before the mechanism exists (plan sequencing rule), so what
these tests protect is the §4 invariant itself: a replayed outcome can never
render unmarked, and a normal outcome can never render marked.
"""

from __future__ import annotations

import pytest

from squadops.cycles.models import Run
from squadops.cycles.replay import ReplayProvenance, replay_marker_lines
from squadops.cycles.run_report_builder import build_run_report

pytestmark = [pytest.mark.domain_cycles]


def _run() -> Run:
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="completed",
        initiated_by="api",
        resolved_config_hash="hash",
    )


class TestReplayProvenanceModel:
    def test_empty_source_run_id_rejected(self):
        # a provenance record that can't name its source is exactly the
        # unlabelled-replay state §4 forbids — fail at construction
        with pytest.raises(ValueError, match="source_run_id"):
            ReplayProvenance(source_run_id="", boundary_index=2)

    def test_negative_boundary_rejected(self):
        with pytest.raises(ValueError, match="boundary_index"):
            ReplayProvenance(source_run_id="run_a", boundary_index=-1)

    def test_dict_roundtrip_preserves_all_fields(self):
        # persistence/DTO layers serialize this — a dropped or coerced field
        # is a replay that later renders unmarked
        original = ReplayProvenance(
            source_run_id="run_abc",
            boundary_index=3,
            compatibility_set=("contract_ref", "prd_ref"),
        )
        assert ReplayProvenance.from_dict(original.to_dict()) == original

    def test_from_dict_defaults_missing_compatibility_set(self):
        p = ReplayProvenance.from_dict({"source_run_id": "run_a", "boundary_index": 0})
        assert p.compatibility_set == ()


class TestReportMarker:
    def test_replayed_report_leads_with_the_disclosure(self):
        report = build_run_report(
            "cyc_001",
            "run_001",
            _run(),
            "COMPLETED",
            replay=ReplayProvenance(source_run_id="run_src", boundary_index=2),
        )
        first_line = report.splitlines()[0]
        assert "REPLAYED" in first_line
        assert "run_src" in first_line
        assert "boundary 2" in first_line
        assert "inherited from the source run" in report

    def test_normal_report_carries_no_replay_marker(self):
        # the symmetric half of §4: a normal run must never render as a replay
        report = build_run_report("cyc_001", "run_001", _run(), "COMPLETED")
        assert "REPLAYED" not in report

    def test_marker_wording_is_single_sourced(self):
        # every surface renders through replay_marker_lines — if a surface
        # re-words the disclosure this fails at the source
        p = ReplayProvenance(source_run_id="run_src", boundary_index=2)
        marker, caveat = replay_marker_lines(p)
        report = build_run_report("cyc_001", "run_001", _run(), "COMPLETED", replay=p)
        assert marker in report
        assert caveat in report

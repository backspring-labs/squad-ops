"""The campaign log archive's window and its once-only rule (#1710)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "campaign_log_archive",
    Path(__file__).resolve().parents[3] / "scripts" / "dev" / "campaign_log_archive.py",
)
archive = importlib.util.module_from_spec(_SPEC)
sys.modules["campaign_log_archive"] = archive  # dataclasses resolve annotations via it
_SPEC.loader.exec_module(archive)

T0 = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
M = archive.MARGIN


@pytest.mark.parametrize(
    ("runs", "since", "until", "ended"),
    [
        (
            [
                ("completed", T0, T0 + timedelta(minutes=20)),
                ("completed", T0 + timedelta(minutes=30), T0 + timedelta(minutes=55)),
            ],
            T0 - M,
            T0 + timedelta(minutes=55) + M,
            True,
        ),
        (
            [
                ("completed", T0, T0 + timedelta(minutes=20)),
                ("running", T0 + timedelta(minutes=30), None),
            ],
            T0 - M,
            None,
            False,
        ),
        ([("queued", None, None)], None, None, None),
    ],
    ids=["ended", "running", "not-started"],
)
def test_a_cycles_window_spans_its_runs_with_a_margin(runs, since, until, ended):
    """Bugs caught: a window that starts at the run's stamp and misses the dispatch logged before
    it, or one closed while a run still writes (its tail lost), or a window invented for a cycle
    that has not started."""
    window = archive.cycle_window("cyc_1", runs)
    if since is None:
        assert window is None
        return
    assert (window.since, window.until, window.ended) == (since, until, ended)


def test_an_ended_cycle_is_archived_once_and_a_running_one_again(tmp_path):
    """Bugs caught: an ended cycle re-read on every pass (churn and a moving sha256), or a running
    cycle frozen at its first pass, its later lines never kept."""
    reads: list[str] = []

    def read_logs(container, since, until):
        reads.append(container)
        return f"{container} {since.isoformat()} {until}".encode()

    ended = archive.cycle_window("cyc_1", [("completed", T0, T0 + timedelta(minutes=5))])
    running = archive.cycle_window("cyc_2", [("running", T0, None)])

    def born(_container):
        return T0 - timedelta(days=1)

    manifest = archive.archive_cycle(tmp_path, ended, read_logs, born)
    stored = json.loads((tmp_path / "cyc_1" / "manifest.json").read_text())
    live = archive.archive_cycle(tmp_path, running, read_logs, born)

    assert stored == manifest and set(stored["files"]) == set(archive.CONTAINERS)
    assert (tmp_path / "cyc_1" / "squadops-neo.log").read_bytes().startswith(b"squadops-neo ")
    assert archive.already_archived(stored, ended) is True
    assert archive.already_archived(live, running) is False
    assert len(reads) == 2 * len(archive.CONTAINERS)


def test_a_window_a_rebuild_destroyed_is_marked_lost_never_read_as_quiet(tmp_path):
    """The shape of shakeout 5's cycles, archived after rebuild 16 recreated every container.
    Bug caught: empty files kept as if the cycle had logged nothing."""
    window = archive.cycle_window("cyc_1", [("completed", T0, T0 + timedelta(minutes=5))])

    manifest = archive.archive_cycle(
        tmp_path, window, lambda *_: b"", lambda c: T0 + timedelta(hours=3)
    )

    assert manifest["lost"] == sorted(archive.CONTAINERS)
    assert all(f["bytes"] == 0 and f["lost"] for f in manifest["files"].values())


def test_a_container_recreated_inside_the_margin_before_the_first_run_lost_nothing(tmp_path):
    """The #1802 proof campaign's shape: the rebuild finished seconds before its calibration
    started. Bug caught: every cycle right after a rebuild reported lost, so a real loss reads
    like noise."""
    window = archive.cycle_window("cyc_1", [("completed", T0, T0 + timedelta(minutes=5))])

    manifest = archive.archive_cycle(
        tmp_path, window, lambda *_: b"x", lambda c: T0 - timedelta(seconds=30)
    )

    assert manifest["lost"] == []

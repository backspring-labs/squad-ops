"""The files a run delivered: one rule for every reader (#1832).

The records are shaped as the vault stores them (``metadata.json``: top-level fields and a nested
``metadata``), with the timestamps it writes.
"""

from __future__ import annotations

import pytest

from squadops.cycles.delivered_tree import StoredArtifact, delivered_files


def _rec(art_id, filename, created_at, *, kind="source", **meta) -> StoredArtifact:
    return StoredArtifact.from_record(
        {
            "artifact_id": art_id,
            "filename": filename,
            "artifact_type": kind,
            "created_at": created_at,
            "metadata": meta,
        }
    )


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        # #881, the roll-14 resume shape: the re-seeded stub is NEWEST but must lose.
        (
            [
                _rec("art_fill", "app/api/runs/route.ts", "2026-08-12 18:43:01+00:00"),
                _rec(
                    "art_stub2",
                    "app/api/runs/route.ts",
                    "2026-08-13 00:07:25+00:00",
                    scaffold_seeded=True,
                ),
            ],
            "art_fill",
        ),
        # Among produced versions, the latest.
        (
            [
                _rec("art_b", "lib/store.ts", "2026-08-12 19:10:00+00:00"),
                _rec("art_a", "lib/store.ts", "2026-08-12 18:40:00+00:00"),
            ],
            "art_b",
        ),
        # A frozen file exists only as seeds: the newest seed set is delivered.
        (
            [
                _rec("art_s1", "lib/errors.ts", "2026-08-12 18:34:13+00:00", scaffold_seeded=True),
                _rec("art_s2", "lib/errors.ts", "2026-08-13 00:07:25+00:00", scaffold_seeded=True),
            ],
            "art_s2",
        ),
        # pf-54: a rejected repair candidate is newer and boots; it was never accepted.
        (
            [
                _rec(
                    "art_dev",
                    "backend/routes.py",
                    "2026-09-01 10:00:00+00:00",
                    producing_task_type="development.develop",
                ),
                _rec(
                    "art_cand",
                    "backend/routes.py",
                    "2026-09-01 10:30:00+00:00",
                    producing_task_type="development.correction_repair",
                ),
            ],
            "art_dev",
        ),
        # #971: a failed emission is never delivered, even when it is the newest.
        (
            [
                _rec("art_ok", "backend/main.py", "2026-09-01 10:00:00+00:00"),
                _rec(
                    "art_bad",
                    "backend/main.py",
                    "2026-09-01 10:30:00+00:00",
                    emission_status="failed",
                ),
            ],
            "art_ok",
        ),
    ],
    ids=[
        "produced-beats-newer-stub",
        "latest-produced",
        "latest-seed",
        "repair-candidate",
        "failed-emission",
    ],
)
def test_one_file_is_delivered_by_the_rule(records, expected):
    """Bugs caught: a resumed run delivering its skeleton (#881), a rejected repair delivered
    because it is newer (pf-54), or bytes already proven not to work delivered (#971)."""
    [delivered] = delivered_files(records).values()
    assert delivered == expected


@pytest.mark.parametrize(
    "record",
    [
        _rec(
            "art_only_bad", "backend/main.py", "2026-09-01 10:30:00+00:00", emission_status="failed"
        ),
        _rec("art_plan", "implementation_plan.yaml", "2026-09-01 10:00:00+00:00", kind="document"),
    ],
    ids=["only-copy-failed", "a-document"],
)
def test_a_file_with_nothing_deliverable_is_absent_not_its_last_copy(record):
    """#971's narrower trap: the failed emission is often the only copy of its file."""
    assert delivered_files([record]) == {}


def test_a_record_without_the_seeded_marker_is_produced():
    """Records predating the marker (or with no metadata at all) are never shadowed by a stub."""
    legacy = StoredArtifact.from_record(
        {
            "artifact_id": "art_x",
            "filename": "main.py",
            "artifact_type": "source",
            "created_at": "2026-08-12 18:00:00+00:00",
        }
    )
    stub = _rec("art_s", "main.py", "2026-08-13 00:00:00+00:00", scaffold_seeded=True)

    assert delivered_files([legacy, stub]) == {"main.py": "art_x"}

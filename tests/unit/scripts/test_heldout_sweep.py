"""Prediction 2's sweep (the 2.4 window's pre-registration §4): its markers, its matchers, and what it
reports. Every suite here is made up for the test; the held-out suite is never read.

What bugs would these catch?
- a marker taken from a goal (visible by design), a key, a path, a number or a word too short to
  mean anything, so the sweep "finds" what isn't a leak;
- a step or check value left out, so a leak of it goes unseen;
- a hit attributed to the wrong table, or a dump's later rows read as an earlier table's;
- the matcher printing a value it found, which would itself carry the held-out step out;
- the suite's own store or the evaluator's records read as a leak, or an unsearched place read as
  clean;
- the wrong revision swept, its digest unchecked.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "heldout_sweep.py"
_spec = importlib.util.spec_from_file_location("heldout_sweep", _SCRIPT)
sweep = importlib.util.module_from_spec(_spec)
sys.modules["heldout_sweep"] = sweep
_spec.loader.exec_module(sweep)

from squadops.scenarios.models import parse_suite  # noqa: E402

SECRET_TITLE = "Zephyr Ridge Loop 7731"
SECRET_NAME = "Quillon Varga"
SECRET_WHERE = "Harbor Steps North"


def _suite_doc() -> dict:
    return {
        "name": "made-up",
        "scenarios": [
            {
                "scenario_id": "s-create",
                "goal": "A created run reads back with its whole title",
                "surfaces": [{"kind": "http_endpoint", "path": "/runs", "method": "POST"}],
                "steps": [
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/runs",
                        "json": {"@Run:title": SECRET_TITLE, "capacity": 3, "tag": "abc"},
                        "save": {"run_id": "id"},
                        "expect_status": 201,
                    },
                    {
                        "action": "http",
                        "method": "POST",
                        "path": "/runs/{run_id}/join",
                        "json": {"@Participant:name": SECRET_NAME},
                        "headers": {"X-Note": "123456"},
                    },
                ],
                "checks": [
                    {"check": "json", "step": 1, "path": "title", "equals": SECRET_TITLE},
                    {
                        "check": "json",
                        "step": 2,
                        "path": "",
                        "where": {"@Run:location": SECRET_WHERE},
                    },
                ],
                "fields": {
                    "Run:title": ["title"],
                    "Participant:name": ["name"],
                    "Run:location": ["location", "meeting_location"],
                },
            }
        ],
    }


def _values() -> dict[str, str]:
    return {mid: m["value"] for mid, m in sweep.markers(parse_suite(_suite_doc())).items()}


def test_the_markers_are_the_step_and_check_values_and_nothing_else():
    found = sweep.markers(parse_suite(_suite_doc()))

    assert sorted(m["value"] for m in found.values()) == sorted(
        [SECRET_TITLE, SECRET_NAME, SECRET_WHERE]
    )
    by_value = {m["value"]: m for m in found.values()}
    assert (by_value[SECRET_NAME]["scenario"], by_value[SECRET_NAME]["where"]) == (
        "s-create",
        "step 2",
    )
    assert by_value[SECRET_WHERE]["where"] == "check 2"
    # Not a goal, a key, a path, a method, a number, a short word, a digit string, or a field name.
    every = {m["value"] for m in found.values()}
    for absent in ("A created run reads back with its whole title", "@Run:title", "/runs", "POST",
                   "abc", "123456", "meeting_location"):  # fmt: skip
        assert absent not in every


def test_a_dump_is_matched_by_table_and_its_counts_are_exact():
    values = _values()
    title, name = sweep.marker_id(SECRET_TITLE), sweep.marker_id(SECRET_NAME)
    lines = [
        "SET statement_timeout = 0;\n",
        "COPY public.authoring_envelopes (id, body) FROM stdin;\n",
        f"1\tasked to make {SECRET_TITLE} and {SECRET_TITLE}\n",
        "2\tnothing here\n",
        "\\.\n",
        'COPY public."observations" (id, input) FROM stdin;\n',
        f"9\t{SECRET_NAME}\n",
        "\\.\n",
        f"a stray line naming {SECRET_NAME}\n",
    ]

    hits = sweep.match_dump(lines, values)

    assert {t: dict(c) for t, c in hits.items()} == {
        "authoring_envelopes": {title: 2},
        "observations": {name: 1},
        "-": {name: 1},
    }


def test_the_walker_reports_paths_and_ids_and_never_a_value(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "suite_leak.txt").write_text(f"the step said {SECRET_WHERE}")
    (tmp_path / "work" / "clean.txt").write_text("nothing held out")
    (tmp_path / "link.txt").symlink_to(tmp_path / "work" / "suite_leak.txt")

    done = subprocess.run(
        [sys.executable, "-", str(tmp_path)],
        input=sweep._walker_program(_values()),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["hits"] == {
        str(tmp_path / "work" / "suite_leak.txt"): [sweep.marker_id(SECRET_WHERE)]
    }
    assert report["files"] == 2  # the symlink isn't followed or read
    for value in (SECRET_TITLE, SECRET_NAME, SECRET_WHERE):
        assert value not in done.stdout and value not in done.stderr


def test_only_a_place_the_squad_or_product_can_see_counts_as_found_and_unsearched_is_not_clean():
    mid = sweep.marker_id(SECRET_TITLE)
    report = {
        "databases": {
            "squadops": {"tables": {"scenario_evaluations": {mid: 3}, "authoring_envelopes": {}}},
            "langfuse": {"tables": {"observations": {mid: 1}}},
            "postgres": {"error": "pg_dump exited 1: permission denied"},
        },
        "containers": {
            "squadops-neo": {"files": 10, "skipped": 0, "hits": {"/tmp/x.py": [mid]}},
            "squadops-eve": {"error": "the walker exited 126: no python3"},
            "squadops-max": {"files": 4, "skipped": 0, "hits": {}},
        },
    }

    assert sweep.found_outside(report) == [
        f"database langfuse, table observations: ['{mid}']",
        "database postgres: not searched (pg_dump exited 1: permission denied)",
        f"container squadops-neo: /tmp/x.py ['{mid}']",
        "container squadops-eve: not searched (the walker exited 126: no python3)",
    ]


@pytest.fixture
def no_box(monkeypatch):
    """Every way the sweep reaches the deploy, refused: on the Spark a test that got that far would
    dump the live databases and walk the live containers (2026-10-21, a mutant of this file did)."""

    def refused(*args, **kwargs):
        raise AssertionError("the sweep reached the box")

    for name in ("sweep_databases", "walk", "window_cycles", "agent_containers"):
        monkeypatch.setattr(sweep, name, refused)
    monkeypatch.setattr(sweep.subprocess, "run", refused)
    monkeypatch.setattr(sweep.subprocess, "Popen", refused)


def test_a_suite_whose_digest_isnt_the_pinned_one_is_refused_before_any_search(
    tmp_path, capsys, no_box
):
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(_suite_doc()))

    assert sweep.main(["--suite", str(path), "--digest", "0000000"]) == 2
    assert "not the pinned 0000000" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["Pier", "12:30:00", "      ", "a1"])
def test_a_value_too_short_or_without_a_letter_is_no_marker(value):
    assert not sweep._distinctive(value)

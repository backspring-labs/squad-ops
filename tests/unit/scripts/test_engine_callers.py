"""``scripts/dev/engine_callers.py``: the engine's request counter by key label, and its gauges, for
the 2.5 cut's "another caller's load" rule (a roll is inconclusive for it only on this evidence).

What bugs would these catch?
- a key written where a label belongs printed into a record (the reader's one rule: no key leaves);
- a missing gauge read as zero, so a crew's load reads as no load;
- a counter line mis-parsed, so one caller's requests are counted under another's label;
- the reading taken outside the deploy, or its output read from the wrong line.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "engine_callers.py"
_spec = importlib.util.spec_from_file_location("engine_callers", _PATH)
callers = importlib.util.module_from_spec(_spec)
sys.modules["engine_callers"] = callers
_spec.loader.exec_module(callers)

_METRICS = """\
# HELP tensorfold:requests_total Replies by key label and status.
# TYPE tensorfold:requests_total counter
tensorfold:requests_total{key="squadops",status="200"} 1352
tensorfold:requests_total{key="orbit-crew",status="200"} 120
tensorfold:requests_total{key="orbit-crew",status="503"} 3
tensorfold:requests_total{status="401"} 2
tensorfold:requests_running 1
tensorfold:requests_waiting 2
"""


def test_the_counter_is_read_by_label_and_status_and_the_gauges_exactly():
    assert callers.parse_metrics(_METRICS) == {
        "requests_total": {
            "squadops": {"200": 1352},
            "orbit-crew": {"200": 120, "503": 3},
            "(none)": {"401": 2},
        },
        "running": 1,
        "waiting": 2,
    }


@pytest.mark.parametrize(
    "label",
    ["sk-tf-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "squad ops", "a" * 33, ""],
    ids=["a-key-shaped-value", "a-space", "too-long", "empty"],
)
def test_a_label_that_isnt_a_short_name_is_hashed_never_printed(label):
    metrics = _METRICS.replace('key="orbit-crew"', f'key="{label}"')

    parsed = callers.parse_metrics(metrics)
    printed = json.dumps(parsed)

    assert label not in printed or label == ""
    hashed = [k for k in parsed["requests_total"] if k.startswith("sha256:")]
    assert len(hashed) == 1 and len(hashed[0]) == len("sha256:") + 12


@pytest.mark.parametrize("missing", ["requests_running", "requests_waiting"])
def test_a_missing_gauge_is_refused_never_read_as_zero(missing):
    metrics = "\n".join(line for line in _METRICS.splitlines() if missing not in line)

    with pytest.raises(ValueError, match="no request gauges"):
        callers.parse_metrics(metrics)


def test_a_reading_is_taken_inside_the_runtime_and_its_last_line_read(monkeypatch):
    """Entered at ``read_once``, as ``read`` and ``watch`` call it: the file is sent to the
    runtime container's Python with ``--inside``, and the reading is its last stdout line."""
    seen = {}

    def run(argv, **kwargs):
        seen["argv"], seen["input"] = argv, kwargs["input"]
        line = json.dumps({"requests_total": {"squadops": {"200": 7}}, "running": 0, "waiting": 0})
        return SimpleNamespace(returncode=0, stdout=f"a warning\n{line}\n", stderr="")

    monkeypatch.setattr(callers.subprocess, "run", run)

    reading = callers.read_once()

    assert seen["argv"][:7] == [
        "docker",
        "exec",
        "-i",
        "-w",
        "/app",
        "squadops-runtime-api",
        "python",
    ]
    assert seen["argv"][-2:] == ["-", "--inside"]
    assert "def _inside" in seen["input"]
    assert reading["requests_total"] == {"squadops": {"200": 7}}
    assert reading["running"] == 0 and "at" in reading


def test_a_failed_reading_stops_rather_than_printing_nothing(monkeypatch):
    monkeypatch.setattr(
        callers.subprocess,
        "run",
        lambda argv, **_: SimpleNamespace(
            returncode=1, stdout="", stderr="boom\n/metrics answered 401"
        ),
    )

    with pytest.raises(SystemExit, match="401"):
        callers.read_once()

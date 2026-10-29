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


def test_a_failed_reading_stops_and_never_forwards_the_containers_words(monkeypatch):
    """Bug caught: the container's last stderr line forwarded, which an error there could fill
    with a configured value. The reader says only where it failed and the exit code."""
    monkeypatch.setattr(
        callers.subprocess,
        "run",
        lambda argv, **_: SimpleNamespace(
            returncode=1, stdout="", stderr="boom\nBearer sk-would-be-a-key-here"
        ),
    )

    with pytest.raises(SystemExit) as stopped:
        callers.read_once()

    assert str(stopped.value) == "the reading failed inside squadops-runtime-api (exit 1)"


def test_series_that_differ_in_another_label_are_summed_never_overwritten():
    """Bug caught: a key's series split by another label (a model) read as its last line alone,
    which undercounts another caller's load, the evidence the cut's rule reads."""
    metrics = (
        'tensorfold:requests_total{key="orbit-crew",status="200",model="x"} 5\n'
        'tensorfold:requests_total{key="orbit-crew",status="200",model="y"} 7 1700000000000\n'
        "tensorfold:requests_running 0\ntensorfold:requests_waiting 0\n"
    )

    assert callers.parse_metrics(metrics)["requests_total"] == {"orbit-crew": {"200": 12}}


@pytest.mark.parametrize(
    "line",
    [
        'tensorfold:requests_total{key="orbit-crew",status="200"} +Inf',
        'tensorfold:requests_total{key="orbit-crew",status="200"} NaN',
        "tensorfold:requests_total 5",
    ],
    ids=["inf", "nan", "no-labels"],
)
def test_a_counter_line_the_reader_cant_parse_is_refused_never_dropped(line):
    """Bug caught: an unparsed line vanished, so a reading with no counter line read as no
    caller at all."""
    metrics = f"{line}\ntensorfold:requests_running 0\ntensorfold:requests_waiting 0\n"

    with pytest.raises(ValueError, match="1 of 1 tensorfold:requests_total lines"):
        callers.parse_metrics(metrics)


def test_a_label_with_a_trailing_newline_is_hashed():
    """Bug caught: ``match`` with ``$`` accepted a trailing newline, so such a label printed as is."""
    assert callers.safe_label("abc\n").startswith("sha256:")
    assert callers.safe_label("squadops") == "squadops"


def test_a_watch_records_a_failed_reading_as_a_gap_and_carries_on(monkeypatch, tmp_path):
    """Entered at ``main(["watch", ...])``. Bug caught: one failed reading ended a one-hour
    window with no marker, which reads as "no other caller" for the rest of it."""
    readings = iter(
        [
            {"at": "t1", "requests_total": {}, "running": 0, "waiting": 0},
            SystemExit("the reading failed inside squadops-runtime-api (exit 1)"),
            {"at": "t3", "requests_total": {}, "running": 0, "waiting": 0},
        ]
    )

    def read_once():
        item = next(readings)
        if isinstance(item, BaseException):
            raise item
        return item

    clock = iter([0.0, 1.0, 2.0, 3.0, 99.0])
    monkeypatch.setattr(callers, "read_once", read_once)
    monkeypatch.setattr(callers.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(callers.time, "sleep", lambda s: None)
    out = tmp_path / "callers.jsonl"

    code = callers.main(["watch", "--seconds", "10", "--interval", "0", "--out", str(out)])

    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert [line.get("at") for line in lines][0::2] == ["t1", "t3"]
    assert lines[1]["error"] == "SystemExit"
    assert code == 1

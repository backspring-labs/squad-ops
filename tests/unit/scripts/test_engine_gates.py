"""SIP-0111's speed and validity gates, read as the 27B's pre-registration fixes them (#2199).

What bugs would these catch? A failed TensorFold call dropped instead of entering at its deadline, which flatters
the median; an overall pass that hides one seam's regression; a prompt-cache hit timed as a cold call; a small
seam reported as passed rather than unbounded; a drift panel or draft check read as clean when it is not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("engine_gates", ROOT / "scripts/dev/engine_gates.py")
eg = importlib.util.module_from_spec(_spec)
sys.modules["engine_gates"] = eg
_spec.loader.exec_module(eg)


def _plan(cells: dict[str, int]) -> dict:
    held = [
        {"envelope_id": f"{seam}-{i}", "task_type": "t", "seam": seam, "stack": "react"}
        for seam, n in cells.items()
        for i in range(n)
    ]
    return {
        "sha256": "p",
        "seeds": {"1": 1001, "2": 1002},
        "held_out": held,
        "order": [[m["envelope_id"], g] for m in held for g in (1, 2)],
    }


def _row(eid, seed, wall, **kw):
    return {
        "envelope_id": eid,
        "seed": seed,
        "wall_s": wall,
        "finish": "stop",
        "prompt_tokens": 100,
    } | kw


def _arms(plan, ollama_wall=100.0, tf_wall=40.0, tf_override=None):
    ollama, tf = {}, {}
    for eid, g in plan["order"]:
        seed = plan["seeds"][str(g)]
        ollama[(eid, seed)] = _row(eid, seed, ollama_wall)
        tf[(eid, seed)] = _row(eid, seed, tf_wall)
    for key, change in (tf_override or {}).items():
        tf[key] = tf[key] | change
    return ollama, tf


def _all_pass(plan, fail_tf=()):
    v = {}
    for eid, g in plan["order"]:
        seed = plan["seeds"][str(g)]
        v[("ollama", eid, seed)] = "pass"
        v[("tensorfold", eid, seed)] = "asked_again" if eid in fail_tf else "pass"
    return v


def test_a_failed_tensorfold_call_enters_at_its_deadline():
    plan = _plan({"build_authoring": 1})
    ollama, tf = _arms(plan, tf_override={("build_authoring-0", 1001): {"error": "HTTP 500"}})
    ps = eg.pairs(plan, ollama, tf, _all_pass(plan))
    assert sorted(p["ratio"] for p in ps) == [0.4, 18.0]


def test_a_prompt_cache_hit_is_left_out_of_the_median():
    plan = _plan({"plan_writing": 1})
    ollama, tf = _arms(
        plan, tf_override={("plan_writing-0", 1002): {"cached_tokens": 64, "wall_s": 5.0}}
    )
    reading = eg.gate(eg.pairs(plan, ollama, tf, _all_pass(plan)))
    assert (reading["cache_hits"], reading["median_ratio"]) == (1, 0.4)


def test_one_seam_below_ollama_fails_validity_though_the_overall_rate_passes(tmp_path):
    """Entered at ``read``, from the arms' folders as the run writes them."""
    plan = _plan({"plan_writing": 6, "repair": 6})
    ollama, tf = _arms(plan)
    for arm, data in (("ollama", ollama), ("tf", tf)):
        folder = tmp_path / arm / "held-out"
        folder.mkdir(parents=True)
        (folder / "summary.jsonl").write_text("\n".join(json.dumps(r) for r in data.values()))
    scores = [
        {"arm": arm, "part": "held-out", "envelope_id": eid, "seed": seed, "verdict": v}
        for (side, eid, seed), v in _all_pass(plan, fail_tf={"repair-0"}).items()
        for arm in (["ollama"] if side == "ollama" else ["tensorfold-x"])
    ]
    for s in scores:  # Ollama fails two plan-writing answers, so TensorFold leads overall
        if s["arm"] == "ollama" and s["envelope_id"] == "plan_writing-0":
            s["verdict"] = "failed"

    reading = eg.read(plan, tmp_path / "ollama", tmp_path / "tf", scores, resamples=200)

    assert reading["overall"]["pass_diff"] == 0.0
    assert reading["by_seam"]["repair"]["validity_observed"] is False
    assert reading["validity_gate"] is False
    assert reading["speed_gate"] is True


def test_a_seam_too_small_to_bound_is_named_unbounded_and_a_bounded_one_carries_its_interval():
    small = _plan({"repair": 2})
    ollama, tf = _arms(small)
    assert eg.gate(eg.pairs(small, ollama, tf, _all_pass(small)))["bounded"] is False
    big = _plan({"plan_writing": 8})
    ollama, tf = _arms(big)
    reading = eg.gate(eg.pairs(big, ollama, tf, _all_pass(big)), resamples=200)
    assert reading["interval"]["median_ratio"] == [0.4, 0.4]
    assert reading["speed_bounded"] is True


@pytest.mark.parametrize(
    "changed, slower, within",
    [(1, 1.0, True), (2, 1.0, False), (0, 1.2, False)],
)
def test_the_drift_panel_allows_one_changed_reply_and_ten_percent(changed, slower, within):
    start = {(f"e{i}", 1001): {"text_sha": "a", "wall_s": 100.0} for i in range(14)}
    end = {
        k: {"text_sha": "b" if i < changed else "a", "wall_s": 100.0 * slower}
        for i, k in enumerate(sorted(start))
    }
    assert eg.drift(start, end)["within_guide"] is within


def test_one_drafted_reply_that_differs_fails_the_draft_check():
    on = {(f"e{i}", 1001): {"text_sha": "a"} for i in range(5)}
    off = dict(on) | {("e3", 1001): {"text_sha": "z"}}
    assert eg.draft_check(on, off) == {"calls": 5, "identical": 4, "exact": False}
    assert eg.draft_check({}, {})["exact"] is False

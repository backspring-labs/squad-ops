#!/usr/bin/env python3
"""Read the held-out run against SIP-0111's speed and validity gates (§4; the 2.3 plan's §5; #2199).

    engine_gates.py PLAN.json --ollama ARM_DIR --tensorfold ARM_DIR --scores SCORES.jsonl --out READING.json

The rules are the pre-registration's (``docs/plans/verification-sets/2-3-0-tensorfold-27b-preregistration.md``
§5), written before the run:
- **The denominator is every planned call.** A call that failed, timed out or never ran enters at its deadline
  for speed and fails for validity.
- **Speed:** the median paired wall-clock ratio, TensorFold over Ollama, at most 0.75, read on pairs where neither
  call had a prompt-cache hit; the truncation rate (calls that ended at their cap) no higher than Ollama's.
- **Validity:** the first-answer pass rate at least Ollama's, overall and in each seam.
- **Uncertainty:** a 95% interval from resampling envelopes, each with all its generations. A bar met by the
  point estimate is an observed pass; it is evidence of non-regression only where the interval's unfavourable
  bound meets it too. A seam with fewer than ``MIN_ENVELOPES`` envelopes is unbounded.
- **Drift:** each arm's panel, start against end: all but one identical, and the median wall-clock change within
  10%.
- **The draft check:** every drafted reply byte-identical to its plain one.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

DEADLINE_S = 1800.0  # engine_replay.CALL_TIMEOUT: a failed call enters here
SPEED_BAR = 0.75
DRIFT_SPEED = 0.10
RESAMPLES = 10_000
BOOT_SEED = 2199
MIN_ENVELOPES = 5


def rows(folder: Path) -> dict[tuple[str, int], dict]:
    path = folder / "summary.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        out[(row["envelope_id"], row["seed"])] = row
    return out


def _wall(row: dict | None) -> float:
    return DEADLINE_S if row is None or row.get("error") else float(row["wall_s"])


def _cache_hit(ollama: dict | None, tf: dict | None) -> bool:
    """TensorFold reports cached tokens; Ollama's prompt evaluation runs short of the same prompt's count."""
    if not ollama or not tf or ollama.get("error") or tf.get("error"):
        return False
    short = (ollama.get("prompt_tokens") or 0) < (tf.get("prompt_tokens") or 0)
    return bool(tf.get("cached_tokens")) or short


def pairs(plan: dict, ollama: dict, tf: dict, verdicts: dict[tuple, str]) -> list[dict]:
    """One record per planned (envelope, generation): both arms' wall-clock, finish and verdict."""
    meta = {m["envelope_id"]: m for m in plan["held_out"]}
    seeds = {int(g): s for g, s in plan["seeds"].items()}
    out = []
    for eid, g in plan["order"]:
        key = (eid, seeds[g])
        o, t = ollama.get(key), tf.get(key)
        out.append(
            {
                **{k: meta[eid][k] for k in ("envelope_id", "task_type", "seam", "stack")},
                "generation": g,
                "ratio": _wall(t) / _wall(o),
                "cache_hit": _cache_hit(o, t),
                "ollama_truncated": bool(o) and o.get("finish") == "length",
                "tf_truncated": bool(t) and t.get("finish") == "length",
                "ollama_pass": verdicts.get(("ollama", *key)) == "pass",
                "tf_pass": verdicts.get(("tensorfold", *key)) == "pass",
            }
        )
    return out


def _rate(ps: list[dict], field: str) -> float:
    return sum(p[field] for p in ps) / len(ps) if ps else float("nan")


def _readings(ps: list[dict]) -> dict[str, float]:
    primary = [p["ratio"] for p in ps if not p["cache_hit"]]
    return {
        "median_ratio": statistics.median(primary) if primary else float("nan"),
        "truncation_diff": _rate(ps, "tf_truncated") - _rate(ps, "ollama_truncated"),
        "pass_diff": _rate(ps, "tf_pass") - _rate(ps, "ollama_pass"),
    }


def interval(ps: list[dict], resamples: int = RESAMPLES, seed: int = BOOT_SEED) -> dict[str, list]:
    """95% intervals of each reading, resampling envelopes with all their generations."""
    by_env: dict[str, list[dict]] = defaultdict(list)
    for p in ps:
        by_env[p["envelope_id"]].append(p)
    envs = sorted(by_env)
    rng = random.Random(seed)
    draws: dict[str, list[float]] = defaultdict(list)
    for _ in range(resamples):
        sample = [p for e in rng.choices(envs, k=len(envs)) for p in by_env[e]]
        for k, v in _readings(sample).items():
            if v == v:  # a resample with no cache-free pair has no median
                draws[k].append(v)
    out = {}
    for k, vs in draws.items():
        vs.sort()
        out[k] = [vs[int(0.025 * (len(vs) - 1))], vs[int(0.975 * (len(vs) - 1))]]
    return out


def gate(ps: list[dict], resamples: int = RESAMPLES) -> dict[str, Any]:
    """One group's readings, intervals and verdicts: observed, and bounded where the interval allows."""
    point = _readings(ps)
    envelopes = len({p["envelope_id"] for p in ps})
    reading: dict[str, Any] = {
        "envelopes": envelopes,
        "calls": len(ps),
        "cache_hits": sum(p["cache_hit"] for p in ps),
        **point,
        "ollama_pass_rate": _rate(ps, "ollama_pass"),
        "tf_pass_rate": _rate(ps, "tf_pass"),
        "ollama_truncation_rate": _rate(ps, "ollama_truncated"),
        "tf_truncation_rate": _rate(ps, "tf_truncated"),
        "speed_observed": point["median_ratio"] <= SPEED_BAR and point["truncation_diff"] <= 0,
        "validity_observed": point["pass_diff"] >= 0,
    }
    if envelopes < MIN_ENVELOPES:
        return reading | {"bounded": False}
    ci = interval(ps, resamples)
    return reading | {
        "bounded": True,
        "interval": ci,
        "speed_bounded": ci["median_ratio"][1] <= SPEED_BAR and ci["truncation_diff"][1] <= 0,
        "validity_bounded": ci["pass_diff"][0] >= 0,
    }


def drift(start: dict, end: dict) -> dict[str, Any]:
    keys = sorted(set(start) & set(end))
    same = sum(start[k].get("text_sha") == end[k].get("text_sha") for k in keys)
    change = statistics.median(_wall(end[k]) / _wall(start[k]) - 1 for k in keys) if keys else None
    return {
        "calls": len(keys),
        "identical": same,
        "median_wall_change": change,
        "within_guide": bool(keys) and same >= len(keys) - 1 and abs(change) <= DRIFT_SPEED,
    }


def draft_check(on: dict, off: dict) -> dict[str, Any]:
    keys = sorted(set(on) & set(off))
    same = [k[0] for k in keys if on[k].get("text_sha") == off[k].get("text_sha")]
    return {
        "calls": len(keys),
        "identical": len(same),
        "exact": bool(keys) and len(same) == len(keys),
    }


def read(
    plan: dict, ollama_dir: Path, tf_dir: Path, scores: list[dict], resamples: int = RESAMPLES
) -> dict:
    verdicts = {
        ("ollama" if r["arm"] == "ollama" else "tensorfold", r["envelope_id"], r["seed"]): r[
            "verdict"
        ]
        for r in scores
        if r.get("part") == "held-out"
    }
    ps = pairs(plan, rows(ollama_dir / "held-out"), rows(tf_dir / "held-out"), verdicts)
    seams = sorted({p["seam"] for p in ps})
    cells = sorted({(p["seam"], p["stack"]) for p in ps})
    by_seam = {s: gate([p for p in ps if p["seam"] == s], resamples) for s in seams}
    overall = gate(ps, resamples)
    draft = {}
    for side in ("on", "off"):
        draft[side] = rows(tf_dir.parent / f"{tf_dir.name}-draft-{side}" / "draft-check")
    return {
        "plan_sha256": plan["sha256"],
        "overall": overall,
        "by_seam": by_seam,
        "by_seam_and_stack": {
            f"{s}|{k}": gate([p for p in ps if (p["seam"], p["stack"]) == (s, k)], resamples)
            for s, k in cells
        },
        "seams_slower_than_ollama": [s for s, g in by_seam.items() if g["median_ratio"] > 1.0],
        "speed_gate": overall["speed_observed"],
        "validity_gate": overall["validity_observed"]
        and all(g["validity_observed"] for g in by_seam.values()),
        "drift": {
            arm: drift(rows(d / "panel-start"), rows(d / "panel-end"))
            for arm, d in (("ollama", ollama_dir), ("tensorfold", tf_dir))
        },
        "draft_check": draft_check(draft["on"], draft["off"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plan", type=Path)
    ap.add_argument("--ollama", type=Path, required=True)
    ap.add_argument("--tensorfold", type=Path, required=True)
    ap.add_argument("--scores", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    scores = [json.loads(line) for line in args.scores.read_text().splitlines()]
    reading = read(json.loads(args.plan.read_text()), args.ollama, args.tensorfold, scores)
    args.out.write_text(json.dumps(reading, indent=2))
    o = reading["overall"]
    print(
        f"speed: median ratio {o['median_ratio']:.3f}, truncation {o['tf_truncation_rate']:.3f} against "
        f"{o['ollama_truncation_rate']:.3f}: {'observed pass' if reading['speed_gate'] else 'fail'}"
    )
    print(
        f"validity: {o['tf_pass_rate']:.3f} against {o['ollama_pass_rate']:.3f}, every seam: "
        f"{'observed pass' if reading['validity_gate'] else 'fail'}"
    )
    print(f"drift: {reading['drift']}\ndraft check: {reading['draft_check']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

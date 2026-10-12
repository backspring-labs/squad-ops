#!/usr/bin/env python3
"""Replay captured authoring envelopes against an inference engine, paired and seeded (SIP-0111 §4, #2199).

Each envelope (SIP-0110's capture: the messages and the call's own settings) is sent as production sends
it, streaming, and every stream event is kept beside a summary row: time to first token, prefill, decode
rate, tokens, the finish reason, and a hash of the text. Rows are written as they finish, so a restart
skips what is done.

    engine_replay.py select --out SELECTION.json [--seed 2199]
    engine_replay.py run SELECTION.json --round 1 --engine ollama --out DIR
    engine_replay.py run SELECTION.json --round 1 --engine tensorfold --recipe RECIPE.yaml --out DIR

Settings: the envelope's ``max_tokens`` (production's registry default, 8,192, where the capture has
none) and its reasoning level. Sampling is production's: Ollama's model defaults (temperature 1, top_p
0.95, top_k 20, min_p 0), which TensorFold is sent explicitly. Each call carries the round's seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
import yaml

OLLAMA_URL = "http://127.0.0.1:11434"
TF_URL = "http://127.0.0.1:8090"
KEY_FILE = Path("/home/jladd/tensorfold/secrets/api_key")
DEFAULT_MAX_TOKENS = 8192  # qwen3.8:27b's default_max_completion in the model registry
SEEDS = {1: 1001, 2: 1002, 3: 1003}
CALL_TIMEOUT = 1800.0
TUNING_PER_STRATUM = 2
HELD_OUT_PER_STRATUM = 8


def psql(sql: str) -> str:
    return subprocess.run(
        ["docker", "exec", "squadops-postgres", "psql", "-U", "squadops", "-d", "squadops", "-At", "-c", sql],
        capture_output=True, text=True, check=True,
    ).stdout


# --- the split ------------------------------------------------------------------------------------


def select(out: Path, seed: int) -> None:
    """A seeded split stratified by task type and stack: tuning first, then held-out, the rest unused."""
    rows = [
        line.split("|")
        for line in psql(
            "select envelope_id, task_type, seam, "
            "coalesce(envelope->'inputs'->'resolved_config'->>'build_profile','none'), messages_sha256 "
            "from authoring_envelopes order by envelope_id"
        ).splitlines()
        if line
    ]
    strata: dict[str, list[dict]] = defaultdict(list)
    for eid, task_type, seam, stack, sha in rows:
        strata[f"{task_type}|{stack}"].append({"envelope_id": eid, "task_type": task_type, "seam": seam,
                                               "stack": stack, "messages_sha256": sha})
    rng = random.Random(seed)
    split: dict[str, Any] = {"seed": seed, "strata": {}, "tuning_per_stratum": TUNING_PER_STRATUM,
                             "held_out_per_stratum": HELD_OUT_PER_STRATUM}
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda r: r["envelope_id"])
        rng.shuffle(members)
        tuning = members[:TUNING_PER_STRATUM]
        held = members[TUNING_PER_STRATUM:TUNING_PER_STRATUM + HELD_OUT_PER_STRATUM]
        split["strata"][key] = {
            "tuning": [dict(m, round=i + 1) for i, m in enumerate(tuning)],
            "held_out": [m["envelope_id"] for m in held],
            "population": len(members),
        }
    ids = json.dumps(split, sort_keys=True).encode()
    split["sha256"] = hashlib.sha256(ids).hexdigest()
    out.write_text(json.dumps(split, indent=2))
    tuning = sum(len(s["tuning"]) for s in split["strata"].values())
    held = sum(len(s["held_out"]) for s in split["strata"].values())
    print(f"{len(split['strata'])} strata, {tuning} tuning, {held} held-out, sha256 {split['sha256'][:16]}")


def envelope(eid: str) -> dict[str, Any]:
    return json.loads(psql(f"select envelope::text from authoring_envelopes where envelope_id = '{eid}'"))


# --- the calls ------------------------------------------------------------------------------------


def api_key() -> str:
    line = KEY_FILE.read_text().strip()
    return line.split(":", 1)[1].strip() if ":" in line else line


def settings(env: dict[str, Any]) -> tuple[int, str]:
    kwargs = env.get("chat_kwargs") or {}
    return int(kwargs.get("max_tokens") or DEFAULT_MAX_TOKENS), (kwargs.get("reasoning") or "none")


def ollama_request(env: dict[str, Any], seed: int) -> tuple[str, dict]:
    max_tokens, reasoning = settings(env)
    return f"{OLLAMA_URL}/api/chat", {
        "model": (env.get("chat_kwargs") or {}).get("model") or "qwen3.8:27b",
        "messages": env["messages"],
        "stream": True,
        "think": reasoning != "none",
        "options": {"num_predict": max_tokens, "seed": seed},
    }


def tensorfold_request(env: dict[str, Any], seed: int, served_id: str, draft: bool | None = None) -> tuple[str, dict]:
    max_tokens, reasoning = settings(env)
    body: dict[str, Any] = {
        "model": served_id,
        "messages": env["messages"],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": max_tokens,
        "seed": seed,
        "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
    }
    if reasoning == "none":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    else:
        body["reasoning_effort"] = reasoning
    if draft is not None:
        body["draft"] = draft
    return f"{TF_URL}/v1/chat/completions", body


def stream_call(url: str, body: dict, headers: dict, raw_path: Path, engine: str) -> dict[str, Any]:
    """One streamed call: every event kept, the timings read from the client's own clock."""
    t0 = time.monotonic()
    first = last = None
    text, thinking = [], []
    final: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    finish = None
    with raw_path.open("w") as raw, httpx.stream("POST", url, json=body, headers=headers,
                                                 timeout=httpx.Timeout(CALL_TIMEOUT, connect=30)) as resp:
        raw.write(json.dumps({"request": body | {"messages": f"<{len(body['messages'])} messages>"}}) + "\n")
        if resp.status_code != 200:
            err = resp.read().decode(errors="replace")[:2000]
            raw.write(json.dumps({"status": resp.status_code, "error": err}) + "\n")
            return {"error": f"HTTP {resp.status_code}: {err[:300]}", "wall_s": round(time.monotonic() - t0, 2)}
        for line in resp.iter_lines():
            if not line:
                continue
            now = time.monotonic()
            raw.write(json.dumps({"t": round(now - t0, 4), "line": line}) + "\n")
            if engine == "ollama":
                event = json.loads(line)
                msg = event.get("message") or {}
                piece, think = msg.get("content") or "", msg.get("thinking") or ""
                if event.get("done"):
                    final = event
                    finish = event.get("done_reason")
            else:
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                if event.get("error"):
                    return {"error": f"stream error: {str(event['error'])[:300]}",
                            "wall_s": round(now - t0, 2)}
                choice = (event.get("choices") or [{}])[0] if event.get("choices") else {}
                delta = choice.get("delta") or {}
                piece, think = delta.get("content") or "", delta.get("reasoning_content") or ""
                finish = choice.get("finish_reason") or finish
            if piece or think:
                first = first if first is not None else now
                last = now
                text.append(piece)
                thinking.append(think)
    wall = time.monotonic() - t0
    row: dict[str, Any] = {
        "wall_s": round(wall, 2),
        "ttft_s": round(first - t0, 3) if first is not None else None,
        "finish": finish,
        "text_chars": len("".join(text)),
        "thinking_chars": len("".join(thinking)),
        "text_sha": hashlib.sha256(("".join(thinking) + "\x00" + "".join(text)).encode()).hexdigest()[:16],
    }
    if engine == "ollama":
        row |= {
            "prompt_tokens": final.get("prompt_eval_count"),
            "completion_tokens": final.get("eval_count"),
            "load_s": round(final.get("load_duration", 0) / 1e9, 2),
            "prefill_s": round(final.get("prompt_eval_duration", 0) / 1e9, 2),
            "engine_decode_tps": round(final["eval_count"] / (final["eval_duration"] / 1e9), 2)
            if final.get("eval_duration") else None,
        }
    else:
        details = usage.get("completion_tokens_details") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        row |= {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": details.get("reasoning_tokens"),
            "cached_tokens": prompt_details.get("cached_tokens"),
            "usage_extra": {k: v for k, v in usage.items()
                            if k not in {"prompt_tokens", "completion_tokens", "total_tokens",
                                         "prompt_tokens_details", "completion_tokens_details"}},
        }
    if first is not None and last is not None and row.get("completion_tokens"):
        span = last - first
        row["client_decode_tps"] = round(row["completion_tokens"] / span, 2) if span > 0 else None
    return row


def run(selection: Path, round_no: int, engine: str, recipe: Path | None, out: Path,
        only: list[str] | None, draft: bool | None, max_tokens_cap: int | None) -> int:
    split = json.loads(selection.read_text())
    seed = SEEDS[round_no]
    served_id = None
    label = engine
    if engine == "tensorfold":
        rec = yaml.safe_load(recipe.read_text())
        served_id, label = rec["served_id"], f"tensorfold-{rec['name']}"
    if draft is not None:
        label += f"-draft-{'on' if draft else 'off'}"
    arm = out / label / f"round{round_no}"
    arm.mkdir(parents=True, exist_ok=True)
    summary = arm / "summary.jsonl"
    done = {json.loads(l)["envelope_id"] for l in summary.read_text().splitlines()} if summary.exists() else set()
    picks = [m for s in split["strata"].values() for m in s["tuning"] if m["round"] == round_no]
    if only:
        picks = [m for m in picks if m["envelope_id"] in only]
    failures = 0
    for m in picks:
        if m["envelope_id"] in done:
            continue
        env = envelope(m["envelope_id"])
        if engine == "ollama":
            url, body = ollama_request(env, seed)
            headers: dict[str, str] = {}
        else:
            url, body = tensorfold_request(env, seed, served_id, draft)
            headers = {"Authorization": f"Bearer {api_key()}"}
        if max_tokens_cap:
            if engine == "ollama":
                body["options"]["num_predict"] = min(body["options"]["num_predict"], max_tokens_cap)
            else:
                body["max_tokens"] = min(body["max_tokens"], max_tokens_cap)
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            row = stream_call(url, body, headers, arm / f"{m['envelope_id']}.jsonl", engine)
        except (httpx.HTTPError, OSError, ValueError) as exc:
            row = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        max_tokens, reasoning = settings(env)
        row = {"envelope_id": m["envelope_id"], "task_type": m["task_type"], "seam": m["seam"],
               "stack": m["stack"], "engine": label, "round": round_no, "seed": seed, "started_at": started,
               "max_tokens": body.get("max_tokens") or body.get("options", {}).get("num_predict"),
               "captured_max_tokens": max_tokens, "reasoning": reasoning,
               "messages_sha256": env.get("messages_sha256"), **row}
        with summary.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps({k: row.get(k) for k in ("engine", "task_type", "stack", "wall_s", "ttft_s",
                                                  "completion_tokens", "client_decode_tps", "finish", "error")}),
              flush=True)
        if row.get("error"):
            failures += 1
            if engine == "tensorfold" and failures >= 3:
                print("THREE_FAILURES: stopping the arm", flush=True)
                return 4
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("select")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--seed", type=int, default=2199)
    r = sub.add_parser("run")
    r.add_argument("selection", type=Path)
    r.add_argument("--round", type=int, required=True, choices=sorted(SEEDS))
    r.add_argument("--engine", choices=("ollama", "tensorfold"), required=True)
    r.add_argument("--recipe", type=Path)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--only", nargs="*")
    r.add_argument("--draft", choices=("on", "off"))
    r.add_argument("--max-tokens-cap", type=int)
    args = parser.parse_args()
    if args.command == "select":
        select(args.out, args.seed)
        return 0
    if args.engine == "tensorfold" and not args.recipe:
        parser.error("--recipe is required for tensorfold")
    draft = None if args.draft is None else args.draft == "on"
    return run(args.selection, args.round, args.engine, args.recipe, args.out, args.only, draft,
               args.max_tokens_cap)


if __name__ == "__main__":
    sys.exit(main())

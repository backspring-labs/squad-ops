#!/usr/bin/env python3
"""Replay captured authoring envelopes against an inference engine, paired and seeded (SIP-0111 §4, #2199).

Each envelope (SIP-0110's capture: the messages and the call's own settings) is sent as production sends
it, streaming, and every stream event is kept beside a summary row: time to first token, prefill, decode
rate, tokens, the finish reason, and a hash of the text. Rows are written as they finish, so a restart
skips what is done.

    engine_replay.py select --out SELECTION.json [--seed 2199]
    engine_replay.py run SELECTION.json --round 1 --engine ollama --out DIR
    engine_replay.py run SELECTION.json --round 1 --engine tensorfold --recipe RECIPE.yaml --out DIR
    engine_replay.py plan SELECTION.json --out PLAN.json [--seed 2199]
    engine_replay.py run PLAN.json --part panel-start|held-out|panel-end --engine … --out DIR
    engine_replay.py score ARM_DIR [ARM_DIR ...] --out SCORES.jsonl
    engine_replay.py run PLAN.json --part held-out --engine tensorfold --recipe RECIPE.yaml --out DIR \
        [--max-tokens N] [--first-call-note ASSET [--note-quote TEXT]]

Settings: the envelope's ``max_tokens`` (production's registry default, 8,192, where the capture has
none) and its reasoning level. Sampling is production's: Ollama's model defaults (temperature 1, top_p
0.95, top_k 20, min_p 0), which TensorFold is sent explicitly. Each call carries the round's seed.

Reasoning is sent as Ollama hears it: thinking on or off, never a level. Ollama's qwen3.8 template has no
effort line; the checkpoints' own template writes one for xhigh (its default when thinking is on) and for
low, and none for medium. So a thinking-on call to TensorFold carries the recipe's ``parity_effort``, the
level whose rendered prompt is Ollama's to the token (checked on every round-1 prompt with ``/tokenize``),
and each row records the effort it sent.

``plan`` fixes the held-out run before any call (SIP-0111 §4; the 2.3 plan's §5 and D2): the held-out
envelopes, one generation each (seed 1001; ``GENERATIONS``), their order (one seeded shuffle, the same for both
arms, with no envelope following itself), and the drift panel, two envelopes per seam and stack where the
stratum allows, called identically at the start and end of each arm. Its sha256 is posted before the
first held-out call. ``run PLAN.json --part`` runs one part of it, resumably.

``score`` puts each recorded answer through its task type's own handler, in the agent container of the
envelope's role (``authoring_score.py``), and records whether the first answer passed: G1's validator.

Two overrides change the call itself, for a budget measurement (#2253), and each is named in the arm's
folder and in its ``manifest.json``:
- ``--max-tokens N`` sends every call at N, above the envelope's cap or below it. ``--max-tokens-cap``
  only lowers it, for the draft check.
- ``--first-call-note ASSET [--note-quote TEXT]`` appends one user message after the envelope's own,
  as the cut-off re-ask delivers its fact (#2149). The note is the asset's text, or the quoted part of
  it, word for word. A quote the asset does not hold is refused, so the note can't drift from it.

An arm's settings are written to its ``manifest.json`` on its first call. A restart with different
settings is refused: the summary would mix two arms, and the restart would skip the calls the first
settings already made.
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

sys.path.insert(0, str(Path(__file__).resolve().parent / "ops"))
from engine_switch import OLLAMA_URL, TF_URL, api_key  # noqa: E402

DEFAULT_MAX_TOKENS = 8192  # qwen3.8:27b's default_max_completion in the model registry
SEEDS = {1: 1001, 2: 1002, 3: 1003}
# The 2.3 plan's D2 asked for two generations per arm; the owner ruled one on 2026-10-12 ("once per prompt"),
# its leanest option, since the tuning run left speed far inside its bar.
GENERATIONS = (1,)
PANEL_PER_CELL = 2  # the drift panel: two envelopes per seam and stack, about 16
PARTS = ("tuning", "panel-start", "held-out", "panel-end", "draft-check")
DRAFT_CHECK = 5  # SIP-0111 §4: drafted against serial on 5 held-out envelopes, greedy and seeded
CALL_TIMEOUT = 1800.0
TUNING_PER_STRATUM = 2
HELD_OUT_PER_STRATUM = 8


def psql(sql: str) -> str:
    return subprocess.run(
        [
            "docker",
            "exec",
            "squadops-postgres",
            "psql",
            "-U",
            "squadops",
            "-d",
            "squadops",
            "-At",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
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
        strata[f"{task_type}|{stack}"].append(
            {
                "envelope_id": eid,
                "task_type": task_type,
                "seam": seam,
                "stack": stack,
                "messages_sha256": sha,
            }
        )
    rng = random.Random(seed)
    split: dict[str, Any] = {
        "seed": seed,
        "strata": {},
        "tuning_per_stratum": TUNING_PER_STRATUM,
        "held_out_per_stratum": HELD_OUT_PER_STRATUM,
    }
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda r: r["envelope_id"])
        rng.shuffle(members)
        tuning = members[:TUNING_PER_STRATUM]
        held = members[TUNING_PER_STRATUM : TUNING_PER_STRATUM + HELD_OUT_PER_STRATUM]
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
    print(
        f"{len(split['strata'])} strata, {tuning} tuning, {held} held-out, sha256 {split['sha256'][:16]}"
    )


def envelope(eid: str) -> dict[str, Any]:
    return json.loads(
        psql(f"select envelope::text from authoring_envelopes where envelope_id = '{eid}'")
    )


def _no_repeats(pairs: list[list], rng: random.Random) -> list[list]:
    """A seeded shuffle in which no envelope follows itself, so neither engine's prompt cache serves a
    generation from the one before it."""
    for _ in range(10_000):
        rng.shuffle(pairs)
        if all(a[0] != b[0] for a, b in zip(pairs, pairs[1:], strict=False)):
            return pairs
    raise SystemExit("no order without a repeat was found")


def plan(selection: Path, out: Path, seed: int) -> None:
    """The held-out run, fixed before any call: its envelopes, order and drift panel."""
    split = json.loads(selection.read_text())
    ids = [eid for key in sorted(split["strata"]) for eid in split["strata"][key]["held_out"]]
    quoted = ", ".join(f"'{eid}'" for eid in ids)
    meta = {
        eid: {"envelope_id": eid, "task_type": task_type, "seam": seam, "stack": stack}
        for eid, task_type, seam, stack in (
            line.split("|")
            for line in psql(
                "select envelope_id, task_type, seam, "
                "coalesce(envelope->'inputs'->'resolved_config'->>'build_profile','none') "
                f"from authoring_envelopes where envelope_id in ({quoted})"
            ).splitlines()
            if line
        )
    }
    missing = sorted(set(ids) - set(meta))
    if missing:
        raise SystemExit(f"held-out envelopes the store does not hold: {missing}")
    rng = random.Random(seed)
    order = _no_repeats([[eid, g] for eid in ids for g in GENERATIONS], rng)
    cells: dict[tuple[str, str], list[str]] = defaultdict(list)
    for eid in ids:
        cells[(meta[eid]["seam"], meta[eid]["stack"])].append(eid)
    panel = [
        eid
        for cell in sorted(cells)
        for eid in rng.sample(sorted(cells[cell]), min(PANEL_PER_CELL, len(cells[cell])))
    ]
    doc: dict[str, Any] = {
        "selection_sha256": split["sha256"],
        "seed": seed,
        "seeds": {str(g): SEEDS[g] for g in GENERATIONS},
        "held_out": [meta[eid] for eid in ids],
        "order": order,
        "panel": panel,
        "panel_seed": SEEDS[1],
    }
    doc["sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    out.write_text(json.dumps(doc, indent=2))
    print(
        f"{len(ids)} held-out envelopes, {len(order)} calls an arm, a panel of {len(panel)}, "
        f"sha256 {doc['sha256'][:16]}"
    )


def calls(doc: dict[str, Any], part: str, round_no: int | None) -> tuple[list[dict], str]:
    """The calls of one part, in order, and the folder its records go to."""
    if part == "tuning":
        seed = SEEDS[round_no]
        picks = [m for s in doc["strata"].values() for m in s["tuning"] if m["round"] == round_no]
        return [dict(m, seed=seed, raw=f"{m['envelope_id']}.jsonl") for m in picks], (
            f"round{round_no}"
        )
    meta = {m["envelope_id"]: m for m in doc["held_out"]}
    if part == "held-out":
        return [
            dict(meta[eid], seed=SEEDS[g], generation=g, raw=f"{eid}-g{g}.jsonl")
            for eid, g in doc["order"]
        ], part
    # The draft check reads the first panel envelopes: fixed in the plan, and already called identically.
    panel = doc["panel"][:DRAFT_CHECK] if part == "draft-check" else doc["panel"]
    return [dict(meta[eid], seed=doc["panel_seed"], raw=f"{eid}.jsonl") for eid in panel], part


# --- the calls ------------------------------------------------------------------------------------


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


def tensorfold_request(
    env: dict[str, Any], seed: int, served_id: str, parity_effort: str, draft: bool | None = None
) -> tuple[str, dict]:
    max_tokens, reasoning = settings(env)
    body: dict[str, Any] = {
        "model": served_id,
        "messages": env["messages"],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": max_tokens,
        "seed": seed,
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
    }
    if reasoning == "none":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    else:
        body["chat_template_kwargs"] = {"enable_thinking": True}
        body["reasoning_effort"] = parity_effort
    if draft is not None:
        body["draft"] = draft
    return f"{TF_URL}/v1/chat/completions", body


def read_event(engine: str, line: str) -> dict[str, Any] | None:
    """One streamed line, read the same way for both engines: the answer and thinking it adds, the finish
    reason, and Ollama's closing event or the OpenAI usage block when it carries one. ``{"end": True}`` is
    the OpenAI stream's ``[DONE]``; an ``error`` is a failure the engine reported mid-stream; ``None`` is a
    line that carries no event."""
    if engine == "ollama":
        event = json.loads(line)
        msg = event.get("message") or {}
        out: dict[str, Any] = {
            "piece": msg.get("content") or "",
            "think": msg.get("thinking") or "",
        }
        if event.get("done"):
            out |= {"final": event, "finish": event.get("done_reason")}
        return out
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if data == "[DONE]":
        return {"end": True}
    event = json.loads(data)
    if event.get("error"):
        return {"error": str(event["error"])[:300]}
    choice = (event.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    return {
        "piece": delta.get("content") or "",
        "think": delta.get("reasoning_content") or "",
        "finish": choice.get("finish_reason"),
        "usage": event.get("usage"),
    }


def engine_counts(engine: str, final: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    """The engine's own token counts and timings: Ollama's closing event, or TensorFold's usage block."""
    if engine == "ollama":
        return {
            "prompt_tokens": final.get("prompt_eval_count"),
            "completion_tokens": final.get("eval_count"),
            "load_s": round(final.get("load_duration", 0) / 1e9, 2),
            "prefill_s": round(final.get("prompt_eval_duration", 0) / 1e9, 2),
            "engine_decode_tps": round(final["eval_count"] / (final["eval_duration"] / 1e9), 2)
            if final.get("eval_duration")
            else None,
        }
    details = usage.get("completion_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
        "usage_extra": {
            k: v
            for k, v in usage.items()
            if k
            not in {
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "prompt_tokens_details",
                "completion_tokens_details",
            }
        },
    }


def stream_call(url: str, body: dict, headers: dict, raw_path: Path, engine: str) -> dict[str, Any]:
    """One streamed call: every event kept, the timings read from the client's own clock."""
    t0 = time.monotonic()
    first = last = None
    text, thinking = [], []
    final: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    finish = None
    with (
        raw_path.open("w") as raw,
        httpx.stream(
            "POST", url, json=body, headers=headers, timeout=httpx.Timeout(CALL_TIMEOUT, connect=30)
        ) as resp,
    ):
        raw.write(
            json.dumps({"request": body | {"messages": f"<{len(body['messages'])} messages>"}})
            + "\n"
        )
        if resp.status_code != 200:
            err = resp.read().decode(errors="replace")[:2000]
            raw.write(json.dumps({"status": resp.status_code, "error": err}) + "\n")
            return {
                "error": f"HTTP {resp.status_code}: {err[:300]}",
                "wall_s": round(time.monotonic() - t0, 2),
            }
        for line in resp.iter_lines():
            if not line:
                continue
            now = time.monotonic()
            raw.write(json.dumps({"t": round(now - t0, 4), "line": line}) + "\n")
            event = read_event(engine, line)
            if event is None:
                continue
            if event.get("end"):
                break
            if "error" in event:
                return {"error": f"stream error: {event['error']}", "wall_s": round(now - t0, 2)}
            usage = event.get("usage") or usage
            final = event.get("final") or final
            finish = event.get("finish") or finish
            if event["piece"] or event["think"]:
                first = first if first is not None else now
                last = now
                text.append(event["piece"])
                thinking.append(event["think"])
    wall = time.monotonic() - t0
    row: dict[str, Any] = {
        "wall_s": round(wall, 2),
        "ttft_s": round(first - t0, 3) if first is not None else None,
        "finish": finish,
        "text_chars": len("".join(text)),
        "thinking_chars": len("".join(thinking)),
        "text_sha": hashlib.sha256(
            ("".join(thinking) + "\x00" + "".join(text)).encode()
        ).hexdigest()[:16],
    } | engine_counts(engine, final, usage)
    if first is not None and last is not None and row.get("completion_tokens"):
        span = last - first
        row["client_decode_tps"] = round(row["completion_tokens"] / span, 2) if span > 0 else None
    return row


def first_call_note(asset: Path, quote: str | None = None) -> dict[str, Any]:
    """The note ``--first-call-note`` appends: the asset's body (its front matter dropped), or the
    quoted part of it, word for word. A quote the asset does not hold is refused, and so is a body with
    a template variable left in it, which no call in production is sent."""
    raw = asset.read_text()
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end < 0:
            raise SystemExit(f"{asset}: its front matter has no closing '---'")
        body = raw[end + len("\n---\n") :]
    if quote is not None:
        if not quote or quote not in body:
            raise SystemExit(f"{asset} does not hold the quoted note, word for word: {quote!r}")
        text = quote
    else:
        text = body.strip()
        if "{{" in text:
            raise SystemExit(
                f"{asset} has a template variable in it; quote the part to send with --note-quote"
            )
    return {
        "asset": str(asset),
        "asset_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "quote": quote,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _request(
    env: dict[str, Any],
    engine: str,
    seed: int,
    served: tuple[str | None, str | None],
    draft: bool | None,
    greedy: bool,
    max_tokens_cap: int | None,
    max_tokens: int | None = None,
    note: str | None = None,
) -> tuple[str, dict, dict[str, str]]:
    """One call's URL, body and headers, with the run's overrides: greedy sampling and a lower cap, for the
    draft check; a cap of its own (``max_tokens``, above the envelope's or below it) and a note appended
    as a last user message, for a budget measurement (#2253)."""
    if engine == "ollama":
        url, body = ollama_request(env, seed)
        headers: dict[str, str] = {}
    else:
        url, body = tensorfold_request(env, seed, served[0], served[1], draft)
        headers = {"Authorization": f"Bearer {api_key()}"}
    options = body["options"] if engine == "ollama" else body
    key = "num_predict" if engine == "ollama" else "max_tokens"
    if greedy:  # one reply per prompt, whatever the sampler
        options["temperature"] = 0.0
    if max_tokens:
        options[key] = max_tokens
    if max_tokens_cap:
        options[key] = min(options[key], max_tokens_cap)
    if note is not None:
        # After the envelope's own messages, as the cut-off re-ask sends its fact (#2149): a new list,
        # so the envelope is left as it was captured.
        body["messages"] = [*body["messages"], {"role": "user", "content": note}]
    return url, body, headers


def _file_sha(path: Path | None) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path else None


def _settled(arm: Path, settings: dict[str, Any]) -> None:
    """Write the arm's manifest on its first run; refuse a restart whose settings differ from it."""
    manifest = arm / "manifest.json"
    if manifest.exists():
        recorded = json.loads(manifest.read_text())["settings"]
        changed = sorted(
            k for k in set(recorded) | set(settings) if recorded.get(k) != settings.get(k)
        )
        if changed:
            raise SystemExit(
                f"{arm} was recorded with other settings ({', '.join(changed)}): a restart would mix "
                "two arms in one summary. Use another --out, or the recorded settings"
            )
        return
    manifest.write_text(
        json.dumps(
            {
                "settings": settings,
                "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "script_sha256": _file_sha(Path(__file__).resolve()),
            },
            indent=2,
        )
    )


def run(
    selection: Path,
    part: str,
    round_no: int | None,
    engine: str,
    recipe: Path | None,
    out: Path,
    only: list[str] | None,
    draft: bool | None,
    max_tokens_cap: int | None,
    greedy: bool = False,
    max_tokens: int | None = None,
    note: dict[str, Any] | None = None,
) -> int:
    doc = json.loads(selection.read_text())
    served_id = parity_effort = None
    label = engine
    if engine == "tensorfold":
        rec = yaml.safe_load(recipe.read_text())
        served_id, label = rec["served_id"], f"tensorfold-{rec['name']}"
        parity_effort = rec["parity_effort"]  # required: the level that renders Ollama's prompt
    if draft is not None:
        label += f"-draft-{'on' if draft else 'off'}"
    # Named in the folder, so two arms written to one --out stay apart, and ``score`` keys them apart.
    if max_tokens:
        label += f"-max{max_tokens}"
    if note is not None:
        label += f"-note-{note['text_sha256'][:8]}"
    picks, folder = calls(doc, part, round_no)
    arm = out / label / folder
    arm.mkdir(parents=True, exist_ok=True)
    _settled(
        arm,
        {
            "engine": label,
            "recipe": str(recipe) if recipe else None,
            "recipe_sha256": _file_sha(recipe),
            "served_id": served_id,
            "parity_effort": parity_effort,
            "selection": str(selection),
            "selection_sha256": _file_sha(selection),
            "part": part,
            "round": round_no,
            "draft": draft,
            "greedy": greedy,
            "max_tokens_cap": max_tokens_cap,
            "max_tokens": max_tokens,
            "first_call_note": note,
        },
    )
    summary = arm / "summary.jsonl"
    done = (
        {
            (json.loads(row)["envelope_id"], json.loads(row)["seed"])
            for row in summary.read_text().splitlines()
        }
        if summary.exists()
        else set()
    )
    if only:
        picks = [m for m in picks if m["envelope_id"] in only]
    failures = 0
    for m in picks:
        seed = m["seed"]
        if (m["envelope_id"], seed) in done:
            continue
        env = envelope(m["envelope_id"])
        url, body, headers = _request(
            env,
            engine,
            seed,
            (served_id, parity_effort),
            draft,
            greedy,
            max_tokens_cap,
            max_tokens,
            note["text"] if note else None,
        )
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            row = stream_call(url, body, headers, arm / m["raw"], engine)
        except (httpx.HTTPError, OSError, ValueError) as exc:
            row = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        captured_max, reasoning = settings(env)
        row = {
            "envelope_id": m["envelope_id"],
            "task_type": m["task_type"],
            "seam": m["seam"],
            "stack": m["stack"],
            "engine": label,
            "part": part,
            "round": round_no,
            "generation": m.get("generation"),
            "seed": seed,
            "raw": m["raw"],
            "started_at": started,
            "max_tokens": body.get("max_tokens") or body.get("options", {}).get("num_predict"),
            "captured_max_tokens": captured_max,
            # Production's deadline for the call (the handler's ``generation_timeout``), which the
            # replay does not enforce: a reading compares the call's wall time with it.
            "captured_timeout_seconds": (env.get("chat_kwargs") or {}).get("timeout_seconds"),
            "reasoning": reasoning,
            "reasoning_effort_sent": body.get("reasoning_effort"),
            "messages_sha256": env.get("messages_sha256"),
            "messages_sent": len(body["messages"]),
            "first_call_note_sha256": note["text_sha256"] if note else None,
            **row,
        }
        with summary.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(
            json.dumps(
                {
                    k: row.get(k)
                    for k in (
                        "engine",
                        "task_type",
                        "stack",
                        "wall_s",
                        "ttft_s",
                        "completion_tokens",
                        "client_decode_tps",
                        "finish",
                        "error",
                    )
                }
            ),
            flush=True,
        )
        if row.get("error"):
            failures += 1
            if engine == "tensorfold" and failures >= 3:
                print("THREE_FAILURES: stopping the arm", flush=True)
                return 4
    return 0


# --- the answers, scored by their own handlers (G1) -------------------------------------------------

SCORER = ("authoring_reconstruct.py", "authoring_replay.py", "authoring_score.py")


def recorded_answer(path: Path, engine: str) -> dict[str, Any]:
    """An answer as the model port hands it to the handler, rebuilt from the call's stream events: the
    text, the thinking, and the counts the cap check reads."""
    text, think, final, usage, finish = [], [], {}, {}, None
    for raw in path.read_text().splitlines()[1:]:  # the first line is the request
        event = read_event(engine, json.loads(raw)["line"])
        if not event or event.get("end") or event.get("error"):
            continue
        text.append(event.get("piece") or "")
        think.append(event.get("think") or "")
        finish = event.get("finish") or finish
        final = event.get("final") or final
        usage = event.get("usage") or usage
    counts = engine_counts(engine, final, usage)
    return {
        "content": "".join(text),
        "reasoning_text": "".join(think) or None,
        "finish": finish,
        # As each adapter hands it on: TensorFold's reports how the call ended (``stop`` or ``length``),
        # Ollama's reports none (SIP-0111 §5.2). With it, the handler reads the cap from the finish, as
        # in production; without it, from the token count against the envelope's own cap, so an answer
        # that finished past that cap under ``--max-tokens`` would be read as cut.
        "termination": {"stop": "stop", "length": "length"}.get(finish)
        if engine == "tensorfold"
        else None,
        "prompt_tokens": counts["prompt_tokens"],
        "completion_tokens": counts["completion_tokens"],
    }


def _in_container(container: str, cases: list[dict], answers: list[dict]) -> list[dict]:
    here = Path(__file__).resolve().parent
    for script in SCORER:
        subprocess.run(
            ["docker", "cp", str(here / script), f"{container}:/tmp/{script}"], check=True
        )
    done = subprocess.run(
        ["docker", "exec", "-i", container, "python", "/tmp/authoring_score.py"],
        input=json.dumps({"cases": cases, "answers": answers}),
        capture_output=True,
        text=True,
    )
    records = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    if len(records) != len(answers):
        raise SystemExit(
            f"{container}: {len(records)} of {len(answers)} answers scored:\n{done.stderr[-3000:]}"
        )
    return records


def _one_key_each(answers: list[dict]) -> None:
    """Refuse answers that share a key: two arms recorded under one name, which the scorer's table
    would hand one arm's answers to both."""
    keys = [a["key"] for a in answers]
    twice = sorted({k for k in keys if keys.count(k) > 1})
    if twice:
        raise SystemExit(f"answers share a key, so their arms can't be told apart: {twice[:3]}")


def score(arms: list[Path], out: Path) -> int:
    """Score every recorded answer under each arm directory (its ``round*/`` folders)."""
    from run_authoring_replay import _framework_sha
    from verify_authoring_envelopes import _container_for

    answers, cases = [], {}
    for arm in arms:
        for summary in sorted(arm.glob("*/summary.jsonl")):
            for line in summary.read_text().splitlines():
                row = json.loads(line)
                eid = row["envelope_id"]
                meta = {
                    "key": f"{arm.name}|{summary.parent.name}|{eid}|{row['seed']}",
                    "envelope_id": eid,
                    "arm": arm.name,
                    "part": summary.parent.name,
                    "seed": row["seed"],
                    "task_type": row["task_type"],
                    "seam": row["seam"],
                    "stack": row["stack"],
                    "finish": row.get("finish"),
                }
                if row.get("error"):  # a failed call is a failed answer, never skipped (§4)
                    answers.append({**meta, "verdict": "error", "error": row["error"]})
                    continue
                # The label carries the arm's overrides after the engine's name.
                engine = "ollama" if row["engine"].startswith("ollama") else "tensorfold"
                raw = summary.parent / row.get("raw", f"{eid}.jsonl")
                answers.append({**meta, **recorded_answer(raw, engine)})
                if eid not in cases:
                    cases[eid] = {**envelope(eid), "envelope_id": eid}
    _one_key_each(answers)
    records = [a for a in answers if a.get("verdict") == "error"]
    by_role: dict[str, list[dict]] = defaultdict(list)
    for a in answers:
        if a.get("verdict") != "error":
            by_role[cases[a["envelope_id"]]["role"]].append(a)
    for role, mine in sorted(by_role.items()):
        container = _container_for(role)
        sha = _framework_sha(container)
        meta = {a["key"]: a for a in mine}
        scored = _in_container(
            container, [cases[i] for i in {a["envelope_id"] for a in mine}], mine
        )
        for record in scored:
            answer = meta[record["key"]]
            records.append(
                {
                    **{k: v for k, v in answer.items() if k not in ("content", "reasoning_text")},
                    **record,
                    "container": container,
                    "framework_git_sha": sha,
                }
            )
    with out.open("w") as f:
        for record in sorted(records, key=lambda r: r["key"]):
            f.write(json.dumps(record) + "\n")
    for arm in arms:
        mine = [r for r in records if r["arm"] == arm.name]
        passed = sum(r["verdict"] == "pass" for r in mine)
        print(f"{arm.name}: {passed} of {len(mine)} first answers passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("select")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--seed", type=int, default=2199)
    pl = sub.add_parser("plan")
    pl.add_argument("selection", type=Path)
    pl.add_argument("--out", type=Path, required=True)
    pl.add_argument("--seed", type=int, default=2199)
    r = sub.add_parser("run")
    r.add_argument("selection", type=Path, help="the split (tuning) or the plan (held-out)")
    r.add_argument("--part", choices=PARTS, default="tuning")
    r.add_argument("--round", type=int, choices=sorted(SEEDS))
    r.add_argument("--engine", choices=("ollama", "tensorfold"), required=True)
    r.add_argument("--recipe", type=Path)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--only", nargs="*")
    r.add_argument("--draft", choices=("on", "off"))
    r.add_argument("--max-tokens-cap", type=int, help="lower each call's cap to this (draft check)")
    r.add_argument(
        "--max-tokens",
        type=int,
        help="send each call at this cap, above the envelope's or below it",
    )
    r.add_argument(
        "--first-call-note",
        type=Path,
        help="an asset whose text is appended as a last user message, as the cut-off re-ask is",
    )
    r.add_argument("--note-quote", help="send only this part of the asset, word for word")
    r.add_argument("--greedy", action="store_true")
    c = sub.add_parser("score")
    c.add_argument("arms", type=Path, nargs="+")
    c.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score":
        return score(args.arms, args.out)
    if args.command == "select":
        select(args.out, args.seed)
        return 0
    if args.command == "plan":
        plan(args.selection, args.out, args.seed)
        return 0
    if (args.part == "tuning") != (args.round is not None):
        parser.error("--round goes with the tuning part, and only with it")
    if args.engine == "tensorfold" and not args.recipe:
        parser.error("--recipe is required for tensorfold")
    if args.max_tokens and args.max_tokens_cap:
        parser.error("--max-tokens and --max-tokens-cap set the same field: name one")
    if args.note_quote is not None and args.first_call_note is None:
        parser.error("--note-quote quotes the --first-call-note asset, so it needs one")
    draft = None if args.draft is None else args.draft == "on"
    note = first_call_note(args.first_call_note, args.note_quote) if args.first_call_note else None
    return run(
        args.selection,
        args.part,
        args.round,
        args.engine,
        args.recipe,
        args.out,
        args.only,
        draft,
        args.max_tokens_cap,
        args.greedy,
        args.max_tokens,
        note,
    )


if __name__ == "__main__":
    sys.exit(main())

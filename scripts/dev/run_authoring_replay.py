#!/usr/bin/env python3
"""Run an authoring replay experiment (SIP-0110 §0.11–§0.12; slice 2, #2106).

Reads the captured envelopes and the lessons' cited observations from the deploy's Postgres, keeps
for each case only the lessons whose every cited observation predates its cutoff (by evidence time),
freezes the experiment manifest, and runs each case in the agent container of its role
(``authoring_replay.py``). Records go to ``var/replays/<experiment>/``, never to the store.

    python scripts/dev/run_authoring_replay.py --experiment proposals-v1 \\
        --envelope env_… [--envelope …] | --run run_… [--task-type strategy.propose_increment] \\
        --rubric lesson.criterion_already_satisfied@1 \\
        [--lessons lessons.yaml] [--static-guidance guidance.md] \\
        [--generations 3] [--seed 7] [--validity-only]

``lessons.yaml`` is a list of ``{revision_id, text, cited_observations: [source ids]}``. A manifest is
frozen: rerunning a named experiment with anything changed is refused; name a new one.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_POSTGRES = "squadops-postgres"
sys.path.insert(0, str(_HERE))
from verify_authoring_envelopes import _container_for  # noqa: E402


def _psql_json(sql: str) -> list:
    out = subprocess.run(
        ["docker", "exec", _POSTGRES, "psql", "-U", "squadops", "-d", "squadops", "-Atc", sql],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out or "[]")


def _quoted(ids: list[str]) -> str:
    if any("'" in i for i in ids):
        raise SystemExit("ids carry no quotes")
    return ", ".join(f"'{i}'" for i in ids)


def _envelopes(args) -> list[dict]:
    if args.envelope:
        where = f"envelope_id IN ({_quoted(args.envelope)})"
    else:
        where = f"run_id = '{args.run}'" + (
            f" AND task_type = '{args.task_type}'" if args.task_type else ""
        )
        if "'" in args.run or (args.task_type and "'" in args.task_type):
            raise SystemExit("ids carry no quotes")
    from squadops.memory.authoring_envelope import envelope_id

    # The body as stored (json, never jsonb: jsonb reorders the inputs' keys, #2123), and its id
    # computed as the store computed it.
    envelopes = _psql_json(
        "SELECT coalesce(json_agg(envelope ORDER BY captured_at, envelope_id), '[]') "
        f"FROM authoring_envelopes WHERE {where}"
    )
    for envelope in envelopes:
        envelope["envelope_id"] = envelope_id(envelope)
    return envelopes


def _lessons(path: Path | None):
    import yaml

    from squadops.memory.replay import CitedEvidence, ReplayLesson

    if path is None:
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cited_ids = sorted({o for lesson in raw for o in lesson.get("cited_observations") or ()})
    found = (
        {
            row["source_id"]: row
            for row in _psql_json(
                "SELECT coalesce(json_agg(json_build_object('source_id', source_id, "
                "'observed_at', observed_at, 'cycle_id', cycle_id)), '[]') "
                f"FROM memory_observations WHERE source_id IN ({_quoted(cited_ids)})"
            )
        }
        if cited_ids
        else {}
    )
    missing = sorted(set(cited_ids) - set(found))
    if missing:
        raise SystemExit(f"cited observations the store does not hold: {missing}")
    return [
        ReplayLesson(
            revision_id=str(lesson["revision_id"]),
            text=str(lesson["text"]),
            cited=tuple(
                CitedEvidence(
                    o,
                    datetime.fromisoformat(str(found[o]["observed_at"])),
                    found[o]["cycle_id"],
                )
                for o in lesson.get("cited_observations") or ()
            ),
        )
        for lesson in raw
    ]


def _framework_sha(container: str) -> str:
    return subprocess.run(
        [
            "docker",
            "exec",
            container,
            "python",
            "-c",
            "from squadops._version import resolve_git_sha; print(resolve_git_sha())",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_in(container: str, payload: dict) -> list[dict]:
    for script in ("authoring_reconstruct.py", "authoring_replay.py"):
        subprocess.run(
            ["docker", "cp", str(_HERE / script), f"{container}:/tmp/{script}"], check=True
        )
    with tempfile.TemporaryFile("w+") as stdin:
        json.dump(payload, stdin)
        stdin.seek(0)
        done = subprocess.run(
            ["docker", "exec", "-i", container, "python", "/tmp/authoring_replay.py"],
            stdin=stdin,
            capture_output=True,
            text=True,
        )
    if done.returncode != 0 and not done.stdout.strip():
        raise SystemExit(f"{container}: the replay failed:\n{done.stderr[-3000:]}")
    return [json.loads(line) for line in done.stdout.splitlines() if line.strip()]


def plan(args, envelopes: list[dict], lessons: list) -> tuple[dict, dict]:
    """The frozen manifest and each case's eligible lessons, by evidence time."""
    from squadops.memory.replay import Arm, manifest, temporal_validity

    arms = [Arm.BASELINE]
    if lessons:
        arms.append(Arm.SCOPED_MEMORY)
    static = args.static_guidance.read_text(encoding="utf-8") if args.static_guidance else ""
    if static:
        arms.append(Arm.STATIC_GUIDANCE)
    case_lessons, excluded = {}, []
    for envelope in envelopes:
        cutoff = datetime.fromisoformat(envelope["captured_at"])
        eligible = []
        for lesson in lessons:
            verdict = temporal_validity(lesson, cutoff=cutoff, target_cycle_id=envelope["cycle_id"])
            if verdict.valid:
                eligible.append({"revision_id": lesson.revision_id, "claim": verdict.claim.value})
            else:
                excluded.append(
                    {
                        "envelope_id": envelope["envelope_id"],
                        "revision_id": lesson.revision_id,
                        "reason": verdict.reason,
                    }
                )
        case_lessons[envelope["envelope_id"]] = eligible
    frozen = manifest(
        experiment_id=args.experiment,
        created_at=datetime.now(UTC),
        envelopes=envelopes,
        arms=arms,
        generations=args.generations,
        seed=args.seed,
        lessons=lessons,
        static_guidance=static,
        rubric=args.rubric,
        framework_git_sha=args.framework_git_sha,
        excluded=excluded,
    )
    return frozen.to_dict(), case_lessons


def _freeze(directory: Path, frozen: dict) -> None:
    """Write the manifest, or refuse a named experiment whose inputs changed (§0.12)."""
    path = directory / "manifest.json"
    if path.exists():
        held = json.loads(path.read_text())
        mine = {k: v for k, v in frozen.items() if k != "created_at"}
        if {k: v for k, v in held.items() if k != "created_at"} != mine:
            raise SystemExit(
                f"{path}: this experiment's manifest is frozen and differs; name a new experiment"
            )
        return
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--envelope", action="append", default=[])
    ap.add_argument("--run")
    ap.add_argument("--task-type")
    ap.add_argument("--lessons", type=Path)
    ap.add_argument("--static-guidance", type=Path)
    ap.add_argument("--generations", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--validity-only", action="store_true")
    args = ap.parse_args()
    if not args.envelope and not args.run:
        ap.error("name the cases: --envelope, or --run")

    from squadops.memory.replay import Arm, schedule

    envelopes = _envelopes(args)
    if not envelopes:
        print("no envelopes match")
        return 1
    containers = {role: _container_for(role) for role in {e["role"] for e in envelopes}}
    args.framework_git_sha = _framework_sha(next(iter(containers.values())))
    lessons = _lessons(args.lessons)
    frozen, case_lessons = plan(args, envelopes, lessons)
    directory = _REPO / "var" / "replays" / args.experiment
    _freeze(directory, frozen)
    order = schedule(
        [e["envelope_id"] for e in envelopes],
        [Arm(a) for a in frozen["arms"]],
        args.generations,
        args.seed,
    )
    records = []
    for role, container in sorted(containers.items()):
        cases = [e for e in envelopes if e["role"] == role]
        ids = {e["envelope_id"] for e in cases}
        records.extend(
            _run_in(
                container,
                {
                    "experiment_id": args.experiment,
                    "cases": cases,
                    "lessons": [{"revision_id": r.revision_id, "text": r.text} for r in lessons],
                    "case_lessons": {
                        k: [x["revision_id"] for x in v]
                        for k, v in case_lessons.items()
                        if k in ids
                    },
                    "static_guidance": (
                        args.static_guidance.read_text(encoding="utf-8")
                        if args.static_guidance
                        else ""
                    ),
                    "arms": frozen["arms"],
                    "schedule": [[c, a.value, g] for c, a, g in order if c in ids],
                    "validity_only": args.validity_only,
                },
            )
        )
    name = "validity.jsonl" if args.validity_only else "results.jsonl"
    with (directory / name).open("w") as out:
        for record in records:
            out.write(json.dumps(record) + "\n")
    checks = [r for r in records if r["record"] == "validity"]
    authored = [r for r in records if r["record"] == "authoring"]
    print(f"{args.experiment}: {sum(r['valid'] for r in checks)} of {len(checks)} cases valid")
    for r in checks:
        print(
            f"  {r['envelope_id']}: reproduction exact={r['baseline_exact']}, "
            f"memory arm differs only by its section={r['memory_differs_only_by_its_section']}"
        )
    for arm in frozen["arms"]:
        print(f"  {arm}: {sum(1 for r in authored if r['arm'] == arm)} authorings")
    print(f"records: {directory}")
    return 0 if all(r["valid"] for r in checks) else 1


if __name__ == "__main__":
    sys.exit(main())

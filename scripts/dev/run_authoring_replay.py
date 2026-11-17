#!/usr/bin/env python3
"""Run an authoring replay experiment (SIP-0110 §0.11–§0.12; slice 2, #2106).

Reads the captured envelopes and the lessons' cited observations from the deploy's Postgres, keeps
for each case only the lessons whose every cited observation predates its cutoff (by evidence time),
freezes the experiment manifest, and runs each case in the agent container of its role
(``authoring_replay.py``). Records go to ``var/replays/<experiment>/``, never to the store.

    python scripts/dev/run_authoring_replay.py --experiment proposals-v1 \\
        --envelope env_… [--envelope …] | --run run_… [--task-type strategy.propose_increment] \\
        --rubric lesson.criterion_already_satisfied@3 \\
        [--lessons lessons.yaml] [--static-guidance guidance.md] \\
        [--generations 3] [--seed 7] [--validity-only]

``lessons.yaml`` is a list of ``{revision_id, text, cited_observations: [source ids]}``. A manifest is
frozen: rerunning a named experiment with anything changed is refused; name a new one. A rubric the
repository holds (``replay_rubrics/``, each file headed by its id and version) is pinned by its text:
the manifest records the named version's hash, and a version no file holds is refused (#2313).

**A skills replay** (SIP-0116 §17p; Q47) tests a skillset's skills on the deploy's own models before
any development profile requires them:

    python scripts/dev/run_authoring_replay.py --experiment roblox-skills-v1 \
        --envelope env_… --envelope env_… --envelope env_… --skill-cases roblox-skills@1 \
        [--generations 3] [--seed 7] [--validity-only] \
        [--product-checkout DIR [--spec-argv .tools/lune run tests/run.luau]]

The envelopes are the capture: a cycle with no skills loaded, holding one envelope of each task
type the cases name. A Campaign's cycle holds them in two runs (the proposal's and the build's),
so they are named one by one; ``--run`` names a single run's. Each case (``skill_replay_cases/``, a file headed by its id and version and pinned by
its text) is authored under the baseline and under the skills its cycle would hand it, and each
skills-arm authoring is judged by its case's expectation (``judged.jsonl``). A case that expects its
emitted specs to pass is judged only when ``--product-checkout`` names a checkout of the product at
the capture's commit, with its test runtime installed: the specs are run there, on a copy, by the
product's own runner, and read by the framework's ``luau`` reader, over the files the test task
was written against (``under_test``). A case that expects its spec to discriminate has each spec
run alone there twice, without those files and with them, and the two readings judged by the
Campaign's own rule (``spec_discrimination``). Without a checkout those expectations read
``not_judged``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_POSTGRES = "squadops-postgres"
_RUBRICS = _HERE / "replay_rubrics"
_SKILL_CASES = _HERE / "skill_replay_cases"
_SPEC_ARGV = (".tools/lune", "run", "tests/run.luau")
_SPEC_TIMEOUT_SECONDS = 300
_RUBRIC_HEADER = re.compile(r"# Rubric `(?P<name>[^`@]+)@(?P<version>[^`]+)`")
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


def rubric_text(rubric_id: str) -> str | None:
    """The text a rubric id's version names, or None for a label no rubric file holds (#2313).

    Each file's first line names the rubric and the version it holds, so an id names a text, not a
    label: a held rubric named at a version no file holds is refused, since its outputs would be
    read by another version's text."""
    name, _, version = rubric_id.rpartition("@")
    held: dict[str, Path] = {}
    for path in sorted(_RUBRICS.glob("*.md")):
        header = _RUBRIC_HEADER.fullmatch(path.read_text(encoding="utf-8").partition("\n")[0])
        if header and header["name"] == name:
            held[header["version"]] = path
    if not held:
        return None
    if version not in held:
        raise SystemExit(
            f"--rubric {rubric_id}: the repository holds {name} at "
            f"{', '.join('@' + v for v in sorted(held))}; a version is read by its own text"
        )
    return held[version].read_text(encoding="utf-8")


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
        rubric_text=rubric_text(args.rubric),
        framework_git_sha=args.framework_git_sha,
        excluded=excluded,
    )
    return frozen.to_dict(), case_lessons


def skill_cases_text(cases_id: str) -> tuple[object, str]:
    """The cases a ``<name>@<version>`` names, and their file's text, which the manifest pins.
    A name no file holds, or a version of it no file holds, is refused."""
    from squadops.memory.skill_replay import SkillCasesError, read_cases

    name, _, version = cases_id.rpartition("@")
    held: dict[str, tuple[object, str]] = {}
    for path in sorted(_SKILL_CASES.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        try:
            cases = read_cases(text)
        except SkillCasesError as exc:
            raise SystemExit(f"{path.name}: {exc}") from exc
        if cases.name == name:
            held[cases.version] = (cases, text)
    if version not in held:
        versions = ", ".join("@" + v for v in sorted(held)) or "no version"
        raise SystemExit(
            f"--skill-cases {cases_id}: the repository holds {name or cases_id} at {versions}"
        )
    return held[version]


def skill_plan(
    args, envelopes: list[dict], cases, cases_text: str
) -> tuple[dict, list[dict], dict]:
    """The frozen manifest, each case's envelope, and each case's notes by its envelope's id.

    A case names its captured task by type, so the capture holds exactly one envelope of it. A
    case's envelope is the capture's under an id of the case's own, since several cases may
    start from one capture."""
    from squadops.memory.replay import Arm, manifest

    by_type: dict[str, list[dict]] = defaultdict(list)
    for envelope in envelopes:
        by_type[envelope["task_type"]].append(envelope)
    case_envelopes, notes = [], {}
    for case in cases.cases:
        found = by_type.get(case.task_type, [])
        if len(found) != 1:
            raise SystemExit(
                f"case {case.id}: the capture holds {len(found)} envelopes of {case.task_type}, "
                "and a case starts from exactly one"
            )
        envelope = {**found[0], "envelope_id": f"{found[0]['envelope_id']}#{case.id}"}
        case_envelopes.append(envelope)
        notes[envelope["envelope_id"]] = case.notes()
    frozen = manifest(
        experiment_id=args.experiment,
        created_at=datetime.now(UTC),
        envelopes=case_envelopes,
        arms=[Arm.BASELINE, Arm.SKILLS],
        generations=args.generations,
        seed=args.seed,
        lessons=[],
        static_guidance="",
        rubric=f"skill-cases.{cases.id}",
        rubric_text=cases_text,
        framework_git_sha=args.framework_git_sha,
        case_notes=notes,
    )
    return frozen.to_dict(), case_envelopes, notes


def under_test(envelope: dict) -> list[dict]:
    """The files a captured test task was written against: its ``implementation_artifacts``, with
    the bodies its inputs hold. The product's checkout is at the pin, before the run's own change,
    so a spec for that change needs them laid over it. A named file the inputs don't hold is
    refused: the spec would fail on the product for want of it and read as the skill's failure."""
    inputs = envelope.get("inputs") or {}
    held = inputs.get("artifact_contents") or {}
    files = []
    for name in inputs.get("implementation_artifacts") or ():
        if not isinstance(held.get(name), str):
            raise SystemExit(
                f"{envelope['envelope_id']}: the task tests {name}, and its inputs hold no body "
                "for it"
            )
        files.append({"name": name, "content": held[name]})
    return files


def run_specs(
    checkout: Path,
    artifacts: list[dict],
    argv: tuple[str, ...],
    *,
    beneath: tuple[dict, ...] | list[dict] = (),
) -> dict:
    """The emitted spec files' results on the product: ``{"passed", "failed"}`` by test id, as the
    framework's ``luau`` reader reads the product's own runner.

    ``beneath`` (the files the task was written against, ``under_test``) and then the emitted
    files are laid over a copy of ``checkout``, and ``argv`` is run there. Only the emitted specs'
    own tests are counted: the product's other specs ran before the change and are no evidence
    about it. A run the reader can't read fails, with the reader's reason."""
    from squadops.sandbox.findings import LUAU, read

    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "product"
        shutil.copytree(checkout, tree, ignore=shutil.ignore_patterns(".git"), symlinks=True)
        emitted = []
        for laid, counted in ((beneath, False), (artifacts, True)):
            for artifact in laid:
                relative = PurePosixPath(str(artifact["name"]))
                if relative.is_absolute() or ".." in relative.parts:
                    raise SystemExit(f"an emitted file's path leaves the product: {relative}")
                target = tree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(artifact["content"]), encoding="utf-8")
                if counted and relative.name.endswith(".spec.luau"):
                    emitted.append(relative.name)
        if not emitted:
            return {"passed": [], "failed": ["no emitted file is a *.spec.luau spec"]}
        try:
            done = subprocess.run(
                list(argv),
                cwd=tree,
                capture_output=True,
                text=True,
                timeout=_SPEC_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"passed": [], "failed": [f"the runner did not run: {exc}"]}
    reading = read(LUAU, done.stdout, done.stderr, done.returncode)
    if not reading.readable:
        return {"passed": [], "failed": [f"unreadable: {reading.reason}"]}

    def mine(test_id: str) -> bool:
        # A pass is ``<file> > <name>``; a failure's key leads with ``FAILED`` or ``ERROR``.
        return PurePosixPath(test_id.split(" > ")[0].split(" ")[-1]).name in emitted

    return {
        "passed": sorted(i for i in reading.passing or () if mine(i)),
        "failed": sorted(k for k in reading.counts if mine(k)),
    }


def spec_discrimination(
    checkout: Path,
    artifacts: list[dict],
    argv: tuple[str, ...],
    *,
    beneath: tuple[dict, ...] | list[dict] = (),
) -> dict:
    """Whether each emitted spec proves the change it was written for, by the Campaign's own rule
    (``discrimination_on_runner``, SIP-0109 §24ci (a)): ``{<spec's path>: <reason>}``, where the
    reason is ``discriminates`` or why it doesn't.

    Each spec is run alone, as the runner runs one file (its path after ``argv``): on the product
    as checked out, where one of its tests must fail for a reason of its own, and again with the
    files its task was written against laid beneath (``under_test``), where that test must pass.
    A spec that can't load on the product before the change reads ``only_setup_failures``
    (SIP-0109 §24ec). A run that didn't happen reads ``not_run``."""
    from squadops.campaigns.acceptance import discrimination_on_runner
    from squadops.sandbox.findings import LUAU, read

    def reading(layers: list[dict], spec: str):
        with tempfile.TemporaryDirectory() as scratch:
            tree = Path(scratch) / "product"
            shutil.copytree(checkout, tree, ignore=shutil.ignore_patterns(".git"), symlinks=True)
            for artifact in layers:
                relative = PurePosixPath(str(artifact["name"]))
                if relative.is_absolute() or ".." in relative.parts:
                    raise SystemExit(f"an emitted file's path leaves the product: {relative}")
                target = tree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(artifact["content"]), encoding="utf-8")
            try:
                done = subprocess.run(
                    [*argv, spec],
                    cwd=tree,
                    capture_output=True,
                    text=True,
                    timeout=_SPEC_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.TimeoutExpired):
                return None
        return read(LUAU, done.stdout, done.stderr, done.returncode)

    found = {}
    for artifact in artifacts:
        spec = str(artifact["name"])
        if not spec.endswith(".spec.luau"):
            continue
        before = reading(list(artifacts), spec)
        after = reading([*beneath, *artifacts], spec)
        found[spec] = str(discrimination_on_runner(spec, LUAU, before, after).reason)
    return found


def judge_records(records: list[dict], notes: dict, specs_for) -> list[dict]:
    """Each authoring record's judgement. The skills arm is held to its case's expectation; the
    baseline is recorded for contrast and held to nothing, since it was handed no skill.
    ``specs_for(record)`` runs a record's emitted specs, or is ``None`` when no product checkout
    was given."""
    from squadops.memory.replay import Arm
    from squadops.memory.skill_replay import judge

    judged = []
    for record in records:
        if record.get("record") != "authoring":
            continue
        expect = notes[record["envelope_id"]]["expect"]
        row = {
            "case": record["case"],
            "arm": record["arm"],
            "generation": record["generation"],
            "success": record["success"],
            "skill_stop": record.get("skill_stop"),
        }
        if record["arm"] == Arm.SKILLS.value:
            wants_specs = (
                bool(expect.get("specs_pass") or expect.get("discriminates"))
                and specs_for is not None
            )
            specs = specs_for(record) if wants_specs and record["success"] else None
            row.update(judge(expect, record, specs=specs))
            if specs is not None:
                row["specs"] = specs
        judged.append(row)
    return judged


def _judge_and_report(args, cases, case_envelopes, records, notes, directory) -> None:
    """Judge each authoring record against its case, write ``judged.jsonl``, and print each
    case's line. With a product checkout the emitted specs are run on it first."""
    from squadops.memory.skill_replay import MET

    specs_for = None
    if args.product_checkout:
        argv = tuple(args.spec_argv)
        beneath = {e["envelope_id"]: under_test(e) for e in case_envelopes}

        def specs_for(record: dict) -> dict:
            laid = beneath[record["envelope_id"]]
            return {
                **run_specs(args.product_checkout, record["artifacts"], argv, beneath=laid),
                "discrimination": spec_discrimination(
                    args.product_checkout, record["artifacts"], argv, beneath=laid
                ),
            }

    judged = judge_records(records, notes, specs_for)
    with (directory / "judged.jsonl").open("w") as out:
        for row in judged:
            out.write(json.dumps(row) + "\n")
    for case in cases.cases:
        skills = [j for j in judged if j["case"] == case.id and j["arm"] == "skills"]
        base = [j for j in judged if j["case"] == case.id and j["arm"] == "baseline"]
        verdicts = [j["verdict"] for j in skills]
        print(
            f"  {case.id}: skills arm met {verdicts.count(MET)} of {len(skills)} "
            f"({', '.join(verdicts) or 'none authored'}); baseline accepted "
            f"{sum(bool(j['success']) for j in base)} of {len(base)}"
        )
        for j in skills:
            for finding in j["findings"]:
                print(f"    generation {j['generation']}: {finding}")


def _skills_main(args, envelopes: list[dict], containers: dict[str, str]) -> int:
    from squadops.memory.replay import Arm, schedule

    cases, text = skill_cases_text(args.skill_cases)
    frozen, case_envelopes, notes = skill_plan(args, envelopes, cases, text)
    directory = _REPO / "var" / "replays" / args.experiment
    _freeze(directory, frozen, validity_only=args.validity_only)
    order = schedule(
        [e["envelope_id"] for e in case_envelopes],
        [Arm(a) for a in frozen["arms"]],
        args.generations,
        args.seed,
    )
    records = []
    for role, container in sorted(containers.items()):
        mine = [e for e in case_envelopes if e["role"] == role]
        ids = {e["envelope_id"] for e in mine}
        if not mine:
            continue
        records.extend(
            _run_in(
                container,
                {
                    "experiment_id": args.experiment,
                    "cases": mine,
                    "arms": frozen["arms"],
                    "skill_cases": {k: v for k, v in notes.items() if k in ids},
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
    print(f"{args.experiment}: {sum(r['valid'] for r in checks)} of {len(checks)} cases valid")
    for r in checks:
        if r["valid"]:
            sizes = r["prompt_chars"]
            print(
                f"  {r['case']}: valid; capture checked={r['capture_checked']}; prompt "
                f"{sizes['baseline']:,} characters, {sizes['skills']:,} with its skills"
            )
        else:
            print(f"  {r['case']}: NOT VALID: {r.get('reason') or 'its prompts do not line up'}")
    if not args.validity_only:
        _judge_and_report(args, cases, case_envelopes, records, notes, directory)
    print(f"records: {directory}")
    return 0 if all(r["valid"] for r in checks) else 1


def _freeze(directory: Path, frozen: dict, *, validity_only: bool = False) -> None:
    """Write the manifest, or refuse a named experiment whose inputs changed (§0.12).

    A validity-only pass makes no model call and authors nothing, so it has no run to freeze and
    is held to no earlier one (#3148): the run that follows freezes its own manifest. Frozen, the
    pass's generations and seed refused that run for differing from a pass that never used them."""
    directory.mkdir(parents=True, exist_ok=True)
    if validity_only:
        return
    path = directory / "manifest.json"
    if path.exists():
        held = json.loads(path.read_text())
        mine = {k: v for k, v in frozen.items() if k != "created_at"}
        if {k: v for k, v in held.items() if k != "created_at"} != mine:
            raise SystemExit(
                f"{path}: this experiment's manifest is frozen and differs; name a new experiment"
            )
        return
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
    ap.add_argument("--rubric")
    ap.add_argument("--validity-only", action="store_true")
    ap.add_argument("--skill-cases", help="a skills replay's cases, as <name>@<version>")
    ap.add_argument("--product-checkout", type=Path)
    ap.add_argument("--spec-argv", nargs="+", default=list(_SPEC_ARGV))
    args = ap.parse_args()
    if not args.envelope and not args.run:
        ap.error("name the cases: --envelope, or --run")
    if args.skill_cases and (args.lessons or args.static_guidance or args.rubric):
        ap.error("--skill-cases is its own experiment: no --lessons, --static-guidance or --rubric")
    if not args.skill_cases and not args.rubric:
        ap.error("--rubric is required")
    if args.product_checkout and not args.product_checkout.is_dir():
        ap.error(f"--product-checkout {args.product_checkout} is not a directory")

    from squadops.memory.replay import Arm, schedule

    envelopes = _envelopes(args)
    if not envelopes:
        print("no envelopes match")
        return 1
    containers = {role: _container_for(role) for role in {e["role"] for e in envelopes}}
    args.framework_git_sha = _framework_sha(next(iter(containers.values())))
    if args.skill_cases:
        return _skills_main(args, envelopes, containers)
    lessons = _lessons(args.lessons)
    frozen, case_lessons = plan(args, envelopes, lessons)
    directory = _REPO / "var" / "replays" / args.experiment
    _freeze(directory, frozen, validity_only=args.validity_only)
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
        mine = [r for r in authored if r["arm"] == arm]
        exact = [r for r in mine if r.get("first_call_is_the_capture")]
        fidelity = f", first call is the capture in {len(exact)}" if arm == "baseline" else ""
        print(f"  {arm}: {len(mine)} authorings{fidelity}")
    print(f"records: {directory}")
    return 0 if all(r["valid"] for r in checks) else 1


if __name__ == "__main__":
    sys.exit(main())

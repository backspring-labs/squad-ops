"""Record a scripted squad's script from a finished run's stored emissions (#2495).

Reads one cycle's (or one run's) artifacts from a deploy's vault, read-only, and writes a script
in the format ``squadops.llm.script`` defines: one answer per task attempt, keyed
``(task_type, occurrence, call)`` the way the scripted provider counts them. A
``machinery`` cycle then runs on it with ``--set llm_script=<name>@<version>``; the version is
printed when the script is written.

What it recovers, and what it can't:
- **Each attempt's files.** The vault keeps the files a task's answer yielded, not the answer
  itself, so the answer is rebuilt from them: a task that yielded one document is answered with
  that document; any other is answered with every file in the strict ``<lang>:<path>`` fence,
  the format the fenced parser reads losslessly.
- **Only what a model wrote** (#2892, from the soak's recording). A retest re-runs a repaired
  suite with no model call, so its stored report is no answer: kept, it would take an
  occurrence the replay never counts, and every later task of its type would be answered from
  the one before. A handler's own record of an answer (``typed_check_evaluation``,
  ``test_report``) is no part of it either, and a repair's bytes stored again, the same, under
  the task it repaired are one file, not two.
- **A repair's revision as edits.** A repair step that revises an existing file may only edit it
  (``_RepairPromptMixin``; re-emitting it whole is refused, SIP-0107 §9.4). The vault keeps the
  revised file, not the edits, so each is rebuilt as one anchored edit from the file's last
  earlier stored version, and checked by applying it to that version before it is written.
- **Not a task's extra calls.** A self-evaluation pass, a re-ask or an authoring loop's earlier
  tries left no file of their own, so a task that made more than one call is recorded as its
  last. Running the script names the first key it lacks, and that answer is written by hand.
- **Latency, approximately** (``--replay-latency``): the time from the previous attempt's last
  stored file to this attempt's first. It includes the orchestration between them, and any wait
  at a gate between them, which can be longer than the deploy lets one task run. So
  ``--latency-cap`` holds each answer under a ceiling (set it below the deploy's
  ``SQUADOPS__DISPATCH__TASK_TIMEOUT``), and ``--latency-scale`` multiplies every gap, for a
  run that must last longer than its recording did (#2892's soak). Both are written into the
  script's ``recorded_from.latency``, with the total and the number capped, so the record says
  how the replayed time was made.

A recorded script is a starting point: run it once, and read the first failure.

Usage::

    python scripts/dev/record_llm_script.py --vault <vault dir> --project <project> \
        --cycle <cycle_id> [--run <run_id>] --name <script> --description "<what it drives>" \
        [--replay-latency [--latency-scale <k>] [--latency-cap <seconds>]] [--out <dir>]
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

from llm_script_check import CHANGE_REQUESTS_KEY, FAILED_KEY, script_problems  # noqa: E402

from squadops.campaigns.change_request import stored_proposal  # noqa: E402
from squadops.capabilities.anchored_edits import (  # noqa: E402
    DIVIDER_MARKER,
    EDIT_FENCE_LANGUAGE,
    REPLACE_MARKER,
    SEARCH_MARKER,
    apply_anchored_edits,
    parse_anchored_edits,
)
from squadops.capabilities.handlers.planning.proposal import (  # noqa: E402
    CHANGE_REQUEST_ARTIFACT_TYPE,
)
from squadops.execution.correction_ids import is_retest_task_id  # noqa: E402
from squadops.llm.script import (  # noqa: E402
    PACKAGED_SCRIPTS_DIR,
    AnswerKey,
    LLMScriptError,
    parse_script,
    script_version,
)
from squadops.tasks.task_types import TaskType  # noqa: E402

_TASK_TYPES = frozenset(t.value for t in TaskType)

#: What a handler stores about an answer, never part of it: the typed checks it evaluated on the
#: answer's files, and the report of the suite it ran.
_HANDLER_RECORDS = frozenset({"typed_check_evaluation", "test_report"})

#: The steps whose handler revises an existing file only by anchored edits and refuses it
#: re-emitted whole (``_RepairPromptMixin``'s handlers, SIP-0107 §9.4).
_ANCHORED_EDIT_STEPS = frozenset(
    {
        TaskType.DEVELOPMENT_CORRECTION_REPAIR,
        TaskType.BUILDER_ASSEMBLE_REPAIR,
        TaskType.QA_TEST_REPAIR,
    }
)

_FENCE_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".toml": "toml",
    ".sh": "bash",
    ".sql": "sql",
}


@dataclass(frozen=True)
class StoredFile:
    """One artifact as the vault holds it: its metadata and its bytes."""

    ref: Any  # squadops.cycles.models.ArtifactRef
    content: bytes


@dataclass
class _Attempt:
    task_type: str
    task_id: str
    attempt: int
    files: list[StoredFile]

    @property
    def first(self) -> Any:
        return min(f.ref.created_at for f in self.files)

    @property
    def last(self) -> Any:
        return max(f.ref.created_at for f in self.files)


def _writer(ref: Any) -> tuple[str, str] | None:
    """The task type and id whose answer yielded this file, or ``None`` when no model wrote it.

    A repair's bytes are stored under the task they repaired, with the repairing step named as
    ``written_by_*`` (#2206): the step that called the model is the writer. A retest calls no
    model, and a handler's record of an answer is not the answer.
    """
    meta = ref.metadata or {}
    if meta.get("scaffold_seeded") or ref.artifact_type in _HANDLER_RECORDS:
        return None
    task_type = meta.get("written_by_task_type") or meta.get("producing_task_type")
    task_id = meta.get("written_by_task_id") or meta.get("task_id")
    if not task_type or not task_id or task_type not in _TASK_TYPES:
        return None
    if is_retest_task_id(str(task_id)):
        return None
    return str(task_type), str(task_id)


def _whole_block(f: StoredFile) -> str:
    body = f.content.decode("utf-8", errors="replace")
    if not body.endswith("\n"):
        body += "\n"
    lang = _FENCE_LANGUAGE.get(Path(f.ref.filename).suffix.lower(), "text")
    return f"```{lang}:{f.ref.filename}\n{body}```"


_MARKERS = (SEARCH_MARKER, DIVIDER_MARKER, REPLACE_MARKER, "<<<<<<< ", ">>>>>>> ")


def _edit_block(path: str, base: str, revised: str) -> str | None:
    """``revised`` as one anchored edit of ``base``: the changed lines, widened by unchanged ones
    until the anchor occurs once. ``None`` when no edit can say it: nothing changed, or a line
    reads as an edit marker."""
    old = base.splitlines(keepends=True)
    new = revised.splitlines(keepends=True)
    changed = [
        op
        for op in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
        if op[0] != "equal"
    ]
    if not changed:
        return None
    i1, j1, i2, j2 = changed[0][1], changed[0][3], changed[-1][2], changed[-1][4]
    while True:
        anchor = "".join(old[i1:i2])
        if (anchor and base.count(anchor) == 1) or (i1 == 0 and i2 == len(old)):
            break
        if i1 > 0:
            i1, j1 = i1 - 1, j1 - 1
        if i2 < len(old):
            i2, j2 = i2 + 1, j2 + 1
    search, replace = old[i1:i2], new[j1:j2]
    if not search or any(line.startswith(_MARKERS) for line in search + replace):
        return None

    def lines(chunk: list[str]) -> str:
        return "".join(line if line.endswith("\n") else line + "\n" for line in chunk)

    return (
        f"```{EDIT_FENCE_LANGUAGE}:{path}\n{SEARCH_MARKER}\n{lines(search)}{DIVIDER_MARKER}\n"
        f"{lines(replace)}{REPLACE_MARKER}\n```"
    )


def _applies(block: str, path: str, base: str, revised: str, attempt: _Attempt) -> bool:
    """Whether ``block`` turns ``base`` into ``revised`` exactly, as the repair handler applies
    it."""
    application = apply_anchored_edits(
        parse_anchored_edits(block),
        {path: base},
        writable=[path],
        producer=attempt.task_type,
        task_id=attempt.task_id,
    )
    return (
        application.accepted
        and application.outcome is not None
        and application.outcome.candidate_files.get(path) == revised
    )


_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w-]*):")


def _authored_change_request(document: str) -> tuple[str, dict[str, Any]]:
    """A stored change request as its proposer authored it, and the fields the framework derived.

    The stored document carries the derived fields (``stored_change_request``), and the handler
    refuses a document that authors them (``parse_change_request``). Which ones, and how the
    footprint on a campaign branch was extended, is ``stored_proposal``'s. Their lines are cut
    from the stored text and every other line is kept as it is, and the result must load as the
    authored mapping.

    Raises:
        ValueError: the cut text doesn't load as the authored fields.
    """
    proposal = stored_proposal(document)
    data = yaml.safe_load(document)
    # In the document's order, so a re-record writes the same bytes.
    derived = {k: v for k, v in data.items() if k not in proposal.authored}
    cut = set(derived)
    placed = {f.path for f in proposal.criterion_files}
    trimmed = (
        "footprint" in proposal.authored and data["footprint"] != proposal.authored["footprint"]
    )
    if trimmed:
        # On a campaign branch the stored footprint is the authored globs and the placed files.
        derived["footprint"] = data["footprint"]
    kept: list[str] = []
    key = None
    for line in document.splitlines(keepends=True):
        top = _TOP_LEVEL_KEY.match(line)
        if top:
            key = top.group(1)
        if key in cut:
            continue
        if trimmed and key == "footprint" and not top and line.startswith("- "):
            if yaml.safe_load(line[2:]) in placed:
                continue
        kept.append(line)
    text = "".join(kept)
    if yaml.safe_load(text) != proposal.authored:
        raise ValueError("the change request's derived fields could not be cut from its text")
    return text, derived


def _answer_content(attempt: _Attempt, bases: dict[str, list[StoredFile]], notes: list[str]) -> str:
    """The answer an attempt's files were parsed from, rebuilt. A step that may only edit an
    existing file answers with an edit of each file it revised (``_ANCHORED_EDIT_STEPS``)."""
    files = attempt.files
    if len(files) == 1 and files[0].ref.artifact_type == "document":
        return files[0].content.decode("utf-8", errors="replace")
    blocks = []
    for f in sorted(files, key=lambda f: f.ref.filename):
        path = f.ref.filename
        earlier = [b for b in bases.get(path, []) if b.ref.created_at < attempt.first]
        if attempt.task_type not in _ANCHORED_EDIT_STEPS or not earlier:
            blocks.append(_whole_block(f))
            continue
        base = earlier[-1].content.decode("utf-8", errors="replace")
        revised = f.content.decode("utf-8", errors="replace")
        if base == revised:
            notes.append(
                f"{attempt.task_type} ({attempt.task_id}) left {path} as it was: no edit is "
                "written for it"
            )
            continue
        block = _edit_block(path, base, revised)
        if block is None or not _applies(block, path, base, revised, attempt):
            notes.append(
                f"{attempt.task_type} ({attempt.task_id}): no edit rebuilds {path}, so it is "
                "answered whole, which the repair handler refuses: write this answer by hand"
            )
            blocks.append(_whole_block(f))
            continue
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


@dataclass
class _ReplayedLatency:
    """How a recorded gap becomes the latency an answer replays: times ``scale``, held at ``cap``,
    with the running total and the count held, for the script's own record of it."""

    scale: float
    cap: float | None
    total: float = 0.0
    capped: int = 0

    @classmethod
    def of(cls, replay: bool, scale: float, cap: float | None) -> _ReplayedLatency | None:
        if scale <= 0 or (cap is not None and cap <= 0):
            raise ValueError("--latency-scale and --latency-cap must be positive")
        if not replay:
            if scale != 1.0 or cap is not None:
                raise ValueError(
                    "--latency-scale and --latency-cap shape a replayed latency: add "
                    "--replay-latency"
                )
            return None
        return cls(scale, cap)

    def of_gap(self, gap: Any) -> float:
        latency = max(gap.total_seconds(), 0.0) * self.scale
        if self.cap is not None and latency > self.cap:
            latency = self.cap
            self.capped += 1
        latency = round(latency, 3)
        self.total += latency
        return latency

    def record(self) -> dict[str, Any]:
        return {
            "scale": self.scale,
            "cap_seconds": self.cap,
            "capped": self.capped,
            "total_seconds": round(self.total, 3),
        }


def _attempts(stored: list[StoredFile]) -> tuple[list[_Attempt], int]:
    """Each task attempt a model call answered, from the files it yielded, and how many stored
    files no model call wrote."""
    written: list[tuple[str, str, int | None, StoredFile]] = []
    skipped = 0
    for f in stored:
        writer = _writer(f.ref)
        if writer is None:
            skipped += 1
            continue
        stamped = (f.ref.metadata or {}).get("attempt")
        written.append((*writer, int(stamped) if stamped is not None else None, f))
    # Only a banked failed attempt is stamped with its attempt (#1436). The accepted emission is
    # stored unstamped, and it is the attempt after the last banked one.
    banked: dict[str, int] = {}
    for _, task_id, stamped, _ in written:
        if stamped is not None:
            banked[task_id] = max(banked.get(task_id, 0), stamped)
    attempts: dict[tuple[str, int], _Attempt] = {}
    for task_type, task_id, stamped, f in written:
        attempt = stamped if stamped is not None else banked.get(task_id, 0) + 1
        entry = attempts.setdefault((task_id, attempt), _Attempt(task_type, task_id, attempt, []))
        # A repair's bytes are stored again, the same, under the task it repaired: one file.
        if any(g.ref.filename == f.ref.filename and g.content == f.content for g in entry.files):
            skipped += 1
            continue
        entry.files.append(f)
    return list(attempts.values()), skipped


def build_script(
    stored: Iterable[StoredFile],
    *,
    name: str,
    description: str,
    recorded_from: dict[str, Any],
    replay_latency: bool,
    latency_scale: float = 1.0,
    latency_cap: float | None = None,
) -> tuple[bytes, list[str]]:
    """The script file's bytes, and what the recording could not recover.

    With ``replay_latency``, each answer's latency is its gap times ``latency_scale``, held at
    ``latency_cap`` when one is given."""
    replayed = _ReplayedLatency.of(replay_latency, latency_scale, latency_cap)
    stored = sorted(stored, key=lambda f: f.ref.created_at)
    # Every stored version of each path, in order: a repair's edit is rebuilt from the last one
    # before it.
    bases: dict[str, list[StoredFile]] = {}
    for f in stored:
        bases.setdefault(f.ref.filename, []).append(f)
    attempts, skipped = _attempts(stored)
    if not attempts:
        raise ValueError("no artifact here was written by a task's model call")

    ordered = sorted(attempts, key=lambda a: (a.first, a.task_id, a.attempt))
    occurrence_of: dict[str, int] = {}
    per_type: dict[str, int] = {}
    calls: dict[str, int] = {}
    answers: list[dict[str, Any]] = []
    unrebuilt: list[str] = []
    change_requests: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    previous_last = None
    for attempt in ordered:
        if attempt.task_id not in occurrence_of:
            per_type[attempt.task_type] = per_type.get(attempt.task_type, 0) + 1
            occurrence_of[attempt.task_id] = per_type[attempt.task_type]
        calls[attempt.task_id] = calls.get(attempt.task_id, 0) + 1
        key = AnswerKey(attempt.task_type, occurrence_of[attempt.task_id], calls[attempt.task_id])
        content = _answer_content(attempt, bases, unrebuilt)
        proposed = [f for f in attempt.files if f.ref.artifact_type == CHANGE_REQUEST_ARTIFACT_TYPE]
        if proposed:
            authored, derived = _authored_change_request(proposed[0].content.decode("utf-8"))
            content = _whole_block(StoredFile(proposed[0].ref, authored.encode())) + "\n"
            change_requests[str(key)] = derived
        if any((f.ref.metadata or {}).get("emission_status") == "failed" for f in attempt.files):
            failed.append(str(key))
        answer: dict[str, Any] = {
            "task_type": attempt.task_type,
            "occurrence": key.occurrence,
            "call": key.call,
            "content": content,
        }
        if replayed is not None and previous_last is not None:
            answer["latency_seconds"] = replayed.of_gap(attempt.first - previous_last)
        previous_last = attempt.last
        answers.append(answer)

    if change_requests:
        recorded_from = {**recorded_from, CHANGE_REQUESTS_KEY: change_requests}
    if failed:
        recorded_from = {**recorded_from, FAILED_KEY: failed}
    if replayed is not None:
        recorded_from = {**recorded_from, "latency": replayed.record()}
    doc = {
        "script": name,
        "description": description,
        "replay_latency": replay_latency,
        "recorded_from": recorded_from,
        "answers": answers,
    }
    raw = yaml.dump(doc, Dumper=_LiteralDumper, sort_keys=False, allow_unicode=True).encode()
    # The recording is refused here rather than at its first call.
    refused = script_problems(parse_script(raw, name=name))
    notes = [
        f"{len(answers)} answers over {len(occurrence_of)} tasks; {skipped} stored files no "
        "model call wrote were left out",
        "a task's self-evaluation passes, re-asks and earlier authoring tries left no files, so "
        "each attempt is recorded as one call: run the script and add any key it names",
    ]
    notes.extend(unrebuilt)
    notes.extend(f"its handler would refuse {problem}" for problem in refused)
    if replayed is not None:
        notes.append(
            "latency is the gap between stored files, orchestration and gate waits included; the "
            f"first answer has none. Replayed: {round(replayed.total)} s in all, scale "
            f"{replayed.scale}, {replayed.capped} answer(s) held at the cap {replayed.cap}"
        )
    return raw, notes


class _LiteralDumper(yaml.SafeDumper):
    """Multi-line strings as literal blocks, so a recorded answer reads as the model wrote it."""


def _str_presenter(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_LiteralDumper.add_representer(str, _str_presenter)


async def _read_vault(
    vault_dir: Path, project_id: str, cycle_id: str, run_id: str | None
) -> list[StoredFile]:
    from read_only_vault import ReadOnlyVault

    vault = ReadOnlyVault(base_dir=str(vault_dir))
    refs = await vault.list_artifacts(project_id=project_id, cycle_id=cycle_id, run_id=run_id)
    stored = []
    for ref in refs:
        _, content = await vault.retrieve(ref.artifact_id)
        stored.append(StoredFile(ref, content))
    return stored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--vault", required=True, type=Path, help="the artifact vault directory")
    parser.add_argument("--project", required=True)
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--run", default=None, help="one run of the cycle; default: all of them")
    parser.add_argument("--name", required=True, help="the script's name, and its file's")
    parser.add_argument("--description", required=True, help="what the script drives, and why")
    parser.add_argument("--replay-latency", action="store_true")
    parser.add_argument(
        "--latency-scale",
        type=float,
        default=1.0,
        help="multiply every recorded gap (with --replay-latency); written into the script",
    )
    parser.add_argument(
        "--latency-cap",
        type=float,
        default=None,
        help="hold each answer's latency at most this many seconds, below the deploy's task "
        "timeout (with --replay-latency); written into the script",
    )
    parser.add_argument("--out", type=Path, default=PACKAGED_SCRIPTS_DIR)
    args = parser.parse_args(argv)

    stored = asyncio.run(_read_vault(args.vault, args.project, args.cycle, args.run))
    recorded_from = {"project_id": args.project, "cycle_id": args.cycle}
    if args.run:
        recorded_from["run_id"] = args.run
    try:
        raw, notes = build_script(
            stored,
            name=args.name,
            description=args.description,
            recorded_from=recorded_from,
            replay_latency=args.replay_latency,
            latency_scale=args.latency_scale,
            latency_cap=args.latency_cap,
        )
    except (ValueError, LLMScriptError) as exc:
        print(f"record_llm_script: refused: {exc}", file=sys.stderr)
        return 2
    out = args.out / f"{args.name}.yaml"
    if out.exists():
        print(
            f"record_llm_script: refused: {out} exists; a script is never overwritten",
            file=sys.stderr,
        )
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print(f"wrote {out}: --set llm_script={args.name}@{script_version(raw)}")
    for note in notes:
        print(f"  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
- **Not a task's extra calls.** A self-evaluation pass, a re-ask or an authoring loop's earlier
  tries left no file of their own, so a task that made more than one call is recorded as its
  last. Running the script names the first key it lacks, and that answer is written by hand.
- **Latency, approximately** (``--replay-latency``): the time from the previous attempt's last
  stored file to this attempt's first. It includes the orchestration between them.

A recorded script is a starting point: run it once, and read the first failure.

Usage::

    python scripts/dev/record_llm_script.py --vault <vault dir> --project <project> \
        --cycle <cycle_id> [--run <run_id>] --name <script> --description "<what it drives>" \
        [--replay-latency] [--out <dir>]
"""

from __future__ import annotations

import argparse
import asyncio
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

from squadops.llm.script import (  # noqa: E402
    PACKAGED_SCRIPTS_DIR,
    LLMScriptError,
    parse_script,
    script_version,
)
from squadops.tasks.task_types import TaskType  # noqa: E402

_TASK_TYPES = frozenset(t.value for t in TaskType)

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
    ``written_by_*`` (#2206): the step that called the model is the writer.
    """
    meta = ref.metadata or {}
    if meta.get("scaffold_seeded"):
        return None
    task_type = meta.get("written_by_task_type") or meta.get("producing_task_type")
    task_id = meta.get("written_by_task_id") or meta.get("task_id")
    if not task_type or not task_id or task_type not in _TASK_TYPES:
        return None
    return str(task_type), str(task_id)


def _answer_content(files: list[StoredFile]) -> str:
    """The answer an attempt's files were parsed from, rebuilt."""
    if len(files) == 1 and files[0].ref.artifact_type == "document":
        return files[0].content.decode("utf-8", errors="replace")
    blocks = []
    for f in sorted(files, key=lambda f: f.ref.filename):
        body = f.content.decode("utf-8", errors="replace")
        if not body.endswith("\n"):
            body += "\n"
        lang = _FENCE_LANGUAGE.get(Path(f.ref.filename).suffix.lower(), "text")
        blocks.append(f"```{lang}:{f.ref.filename}\n{body}```")
    return "\n\n".join(blocks) + "\n"


def build_script(
    stored: Iterable[StoredFile],
    *,
    name: str,
    description: str,
    recorded_from: dict[str, Any],
    replay_latency: bool,
) -> tuple[bytes, list[str]]:
    """The script file's bytes, and what the recording could not recover."""
    attempts: dict[tuple[str, int], _Attempt] = {}
    skipped = 0
    for f in stored:
        writer = _writer(f.ref)
        if writer is None:
            skipped += 1
            continue
        task_type, task_id = writer
        attempt = int((f.ref.metadata or {}).get("attempt") or 1)
        entry = attempts.setdefault((task_id, attempt), _Attempt(task_type, task_id, attempt, []))
        entry.files.append(f)
    if not attempts:
        raise ValueError("no artifact here was written by a task's model call")

    ordered = sorted(attempts.values(), key=lambda a: (a.first, a.task_id, a.attempt))
    occurrence_of: dict[str, int] = {}
    per_type: dict[str, int] = {}
    calls: dict[str, int] = {}
    answers: list[dict[str, Any]] = []
    previous_last = None
    for attempt in ordered:
        if attempt.task_id not in occurrence_of:
            per_type[attempt.task_type] = per_type.get(attempt.task_type, 0) + 1
            occurrence_of[attempt.task_id] = per_type[attempt.task_type]
        calls[attempt.task_id] = calls.get(attempt.task_id, 0) + 1
        answer: dict[str, Any] = {
            "task_type": attempt.task_type,
            "occurrence": occurrence_of[attempt.task_id],
            "call": calls[attempt.task_id],
            "content": _answer_content(attempt.files),
        }
        if replay_latency and previous_last is not None:
            answer["latency_seconds"] = round(
                max((attempt.first - previous_last).total_seconds(), 0.0), 3
            )
        previous_last = attempt.last
        answers.append(answer)

    doc = {
        "script": name,
        "description": description,
        "replay_latency": replay_latency,
        "recorded_from": recorded_from,
        "answers": answers,
    }
    raw = yaml.dump(doc, Dumper=_LiteralDumper, sort_keys=False, allow_unicode=True).encode()
    parse_script(raw, name=name)  # the recording is refused here rather than at its first call
    notes = [
        f"{len(answers)} answers over {len(occurrence_of)} tasks; {skipped} stored files no "
        "model call wrote were left out",
        "a task's self-evaluation passes, re-asks and earlier authoring tries left no files, so "
        "each attempt is recorded as one call: run the script and add any key it names",
    ]
    if replay_latency:
        notes.append(
            "latency is the gap between stored files, orchestration included; the first answer "
            "has none"
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

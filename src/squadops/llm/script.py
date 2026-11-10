"""Recorded LLM scripts: the data a scripted squad answers from (#2495).

A **machinery** cycle checks the execution machinery (dispatch, emission, correction, acceptance),
not a model. Its squad's agents all name the model :data:`SCRIPTED_MODEL`, and every call they make
is answered from a script instead of a model: the same answers every time, in seconds, with no
model loaded. A scripted run is never evidence about a model or a prompt, and its records say so.

**The format** (YAML, one file per script, ``<name>.yaml``)::

    script: shelf-search-flag          # the file's own name, without .yaml
    description: what the script drives the cycle through, and why
    replay_latency: false              # true: each answer waits its latency_seconds first
    recorded_from:                     # optional: the run its answers were recorded from
      project_id: ...
      cycle_id: ...
      run_id: ...
    answers:
      - task_type: strategy.analyze_prd
        occurrence: 1                  # the first task of this type the cycle dispatches
        call: 1                        # the task's first model call
        content: |
          ...the answer, exactly as a model would have returned it...
        latency_seconds: 41.5          # optional
        prompt_tokens: 1200            # optional; each figure absent is "not reported"
        completion_tokens: 800         # optional
        reasoning_tokens: 0            # optional
        reasoning_text: ...            # optional
        termination: stop              # optional: stop | length

**The key.** An answer is keyed by ``(task_type, occurrence, call)``, never by the prompt: a
prompt carries run-specific ids, so a prompt hash would miss on every new run.

- ``occurrence`` is the ordinal of the task among the tasks of its type that the cycle has asked
  this agent to answer, counted by distinct task id in the order their first calls arrive. A
  re-roll, a repair step of the same type, or a retest is the next occurrence.
- ``call`` is the ordinal of the call within that task: a re-ask, a self-evaluation pass and
  every attempt of the same task id count on.

So a script can carry a deliberate bad answer (a malformed plan, a failing patch) at one key and
the good one at the next, which makes reachable the re-roll, correction and rewind paths a model
reaches only by chance.

**The version** is the first 12 hex digits of the sha256 of the script file's bytes. A cycle names
its script with its version, ``--set llm_script=<name>@<version>``, so the cycle's record says
which answers it ran on, and an agent holding a different copy refuses rather than answering from
it. A Campaign's cycles are built server-side, so a scripted Campaign names one script per cycle it
launches, in launch order (``policy.llm_scripts``, SIP-0109 §24dt), and each increment answers from
its own.

Pure data and parsing. The library reads files from one directory and writes none.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from squadops.llm.models import Termination
from squadops.tasks.task_types import TaskType

#: The model a scripted agent names in its squad profile. The deploy's LLM port answers it from a
#: script and sends every other model to the engine (``adapters.llm.scripted``).
SCRIPTED_MODEL = "scripted"

#: The engine that answers :data:`SCRIPTED_MODEL`. A call's metrics carry it, so a scripted call is
#: never charted as the deploy engine's.
SCRIPTED_ENGINE = "scripted"

#: The cycle config key that names the script, ``<name>@<version>`` (``--set llm_script=...``).
LLM_SCRIPT_KEY = "llm_script"

#: Where the scripts a deploy can answer from live: package data, so the runtime (which validates
#: and pins a cycle's script) and the agents (which answer from it) hold the same files.
PACKAGED_SCRIPTS_DIR = Path(__file__).resolve().parent / "llm_scripts"

_VERSION_LENGTH = 12
_TERMINATIONS = frozenset({Termination.STOP, Termination.LENGTH})
_TOP_LEVEL_KEYS = frozenset({"script", "description", "replay_latency", "recorded_from", "answers"})
_ANSWER_KEYS = frozenset(
    {
        "task_type",
        "occurrence",
        "call",
        "content",
        "latency_seconds",
        "prompt_tokens",
        "completion_tokens",
        "reasoning_tokens",
        "reasoning_text",
        "termination",
    }
)
_TASK_TYPES = frozenset(t.value for t in TaskType)


class LLMScriptError(Exception):
    """A scripted call could not be answered from its script.

    Deliberately NOT an ``LLMError``: a handler's model-error path (a re-ask, a ``NEEDS_REPLAN``,
    a degraded answer) is for a model's bad day. A script that can't answer is a broken fixture,
    and it fails the task with this message instead.
    """


class ScriptFormatError(LLMScriptError):
    """A script file that does not parse, or breaks a rule of the format."""


class ScriptNotFoundError(LLMScriptError):
    """A cycle named a script the library does not hold."""


class ScriptVersionMismatchError(LLMScriptError):
    """A cycle pinned a version of a script that differs from the one the library holds."""


class ScriptEntryMissingError(LLMScriptError):
    """A call reached a key the script has no answer for. Never answered by a model instead."""


class UnscopedScriptedCallError(LLMScriptError):
    """A scripted call made outside any task, so there is no key to answer it by."""


@dataclass(frozen=True, order=True)
class AnswerKey:
    """Which answer a call takes: the task's type, its occurrence, and the call within it."""

    task_type: str
    occurrence: int
    call: int

    def __str__(self) -> str:
        return f"{self.task_type} occurrence {self.occurrence} call {self.call}"


@dataclass(frozen=True)
class ScriptedAnswer:
    """One recorded answer: the content, and the figures a real response would carry.

    Every figure the script leaves out is ``None`` (not reported), never zero, so usage records
    count it as unreported rather than as a free call.
    """

    content: str
    latency_seconds: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    reasoning_text: str | None = None
    termination: str | None = None


@dataclass(frozen=True)
class ScriptReference:
    """A cycle's ``llm_script`` value: the script's name and the version it was pinned to."""

    name: str
    version: str

    @classmethod
    def parse(cls, value: object) -> ScriptReference:
        """Read ``<name>@<version>``.

        Raises:
            ScriptFormatError: the value is not a string of that shape.
        """
        if not isinstance(value, str) or value.count("@") != 1:
            raise ScriptFormatError(f"{LLM_SCRIPT_KEY} must be '<name>@<version>', not {value!r}")
        name, version = value.split("@")
        if not name or not version:
            raise ScriptFormatError(f"{LLM_SCRIPT_KEY} must be '<name>@<version>', not {value!r}")
        return cls(name=name, version=version)

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class LLMScript:
    """A parsed script: its identity, whether it replays latency, and its answers by key."""

    name: str
    version: str
    description: str
    replay_latency: bool
    answers: Mapping[AnswerKey, ScriptedAnswer]
    recorded_from: Mapping[str, Any] = field(default_factory=dict)

    @property
    def reference(self) -> ScriptReference:
        return ScriptReference(self.name, self.version)

    def answer_for(self, key: AnswerKey) -> ScriptedAnswer:
        """The answer at ``key``.

        Raises:
            ScriptEntryMissingError: the script has none. The message names the key it looked for
                and the keys the script holds for that task type, so the gap can be filled.
        """
        answer = self.answers.get(key)
        if answer is not None:
            return answer
        held = sorted(k for k in self.answers if k.task_type == key.task_type)
        holds = ", ".join(f"occurrence {k.occurrence} call {k.call}" for k in held) or "none"
        raise ScriptEntryMissingError(
            f"script {self.reference} has no answer for {key} (it holds, for "
            f"{key.task_type}: {holds}). A scripted call is never answered by a model instead."
        )


def script_version(raw: bytes) -> str:
    """The version of a script file: the first 12 hex digits of the sha256 of its bytes."""
    return hashlib.sha256(raw).hexdigest()[:_VERSION_LENGTH]


def parse_script(raw: bytes, *, name: str) -> LLMScript:
    """Parse the bytes of the script file ``<name>.yaml``.

    Raises:
        ScriptFormatError: naming the first rule broken — the YAML, the declared name, an unknown
            key, a task type the framework does not dispatch, a duplicate key, or an answer field
            of the wrong type.
    """
    where = f"script {name!r}"
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ScriptFormatError(f"{where} is not valid YAML: {exc}") from exc
    if not isinstance(doc, dict):
        raise ScriptFormatError(f"{where} must be a mapping")
    unknown = sorted(set(doc) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ScriptFormatError(f"{where} has unknown keys {unknown}")
    if doc.get("script") != name:
        raise ScriptFormatError(
            f"{where} declares script {doc.get('script')!r}; it must name itself as its file does"
        )
    replay_latency = doc.get("replay_latency", False)
    if not isinstance(replay_latency, bool):
        raise ScriptFormatError(f"{where}: replay_latency must be true or false")
    recorded_from = doc.get("recorded_from") or {}
    if not isinstance(recorded_from, dict):
        raise ScriptFormatError(f"{where}: recorded_from must be a mapping")
    entries = doc.get("answers")
    if not isinstance(entries, list) or not entries:
        raise ScriptFormatError(f"{where} must hold a non-empty list of answers")

    answers: dict[AnswerKey, ScriptedAnswer] = {}
    for index, entry in enumerate(entries, start=1):
        key, answer = _parse_answer(entry, f"{where} answer {index}")
        if key in answers:
            raise ScriptFormatError(f"{where} holds two answers for {key}")
        answers[key] = answer
    return LLMScript(
        name=name,
        version=script_version(raw),
        description=str(doc.get("description") or ""),
        replay_latency=replay_latency,
        answers=answers,
        recorded_from=dict(recorded_from),
    )


def _parse_answer(entry: object, where: str) -> tuple[AnswerKey, ScriptedAnswer]:
    if not isinstance(entry, dict):
        raise ScriptFormatError(f"{where} must be a mapping")
    unknown = sorted(set(entry) - _ANSWER_KEYS)
    if unknown:
        raise ScriptFormatError(f"{where} has unknown keys {unknown}")
    task_type = entry.get("task_type")
    if task_type not in _TASK_TYPES:
        raise ScriptFormatError(
            f"{where}: {task_type!r} is not a task type the framework dispatches"
        )
    occurrence = _positive_int(entry.get("occurrence"), f"{where} occurrence")
    call = _positive_int(entry.get("call"), f"{where} call")
    content = entry.get("content")
    if not isinstance(content, str):
        raise ScriptFormatError(f"{where}: content must be a string (it may be empty)")
    termination = entry.get("termination")
    if termination is not None and termination not in _TERMINATIONS:
        raise ScriptFormatError(f"{where}: termination must be one of {sorted(_TERMINATIONS)}")
    reasoning_text = entry.get("reasoning_text")
    if reasoning_text is not None and not isinstance(reasoning_text, str):
        raise ScriptFormatError(f"{where}: reasoning_text must be a string")
    latency = entry.get("latency_seconds")
    if latency is not None and (
        isinstance(latency, bool) or not isinstance(latency, int | float) or latency < 0
    ):
        raise ScriptFormatError(f"{where}: latency_seconds must be a non-negative number")
    return (
        AnswerKey(str(task_type), occurrence, call),
        ScriptedAnswer(
            content=content,
            latency_seconds=float(latency) if latency is not None else None,
            prompt_tokens=_token_count(entry.get("prompt_tokens"), f"{where} prompt_tokens"),
            completion_tokens=_token_count(
                entry.get("completion_tokens"), f"{where} completion_tokens"
            ),
            reasoning_tokens=_token_count(
                entry.get("reasoning_tokens"), f"{where} reasoning_tokens"
            ),
            reasoning_text=reasoning_text,
            termination=termination,
        ),
    )


def _positive_int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ScriptFormatError(f"{where} must be a whole number from 1, not {value!r}")
    return value


def _token_count(value: object, where: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScriptFormatError(f"{where} must be a non-negative whole number, not {value!r}")
    return value


class ScriptLibrary:
    """The scripts in one directory, ``<name>.yaml`` each. Read on demand, never written."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    @classmethod
    def packaged(cls) -> ScriptLibrary:
        """The library a deploy serves: the package's own ``llm_scripts`` directory."""
        return cls(PACKAGED_SCRIPTS_DIR)

    @property
    def directory(self) -> Path:
        return self._directory

    def names(self) -> list[str]:
        """Every script's name, sorted. An absent directory holds none."""
        if not self._directory.is_dir():
            return []
        return sorted(p.stem for p in self._directory.glob("*.yaml"))

    def get(self, name: str) -> LLMScript:
        """The script named ``name``, at the version the library holds.

        Raises:
            ScriptNotFoundError: the library holds no script by that name.
            ScriptFormatError: the file does not parse.
        """
        if "/" in name or "\\" in name or name.startswith("."):
            raise ScriptNotFoundError(f"{name!r} is not a script name")
        path = self._directory / f"{name}.yaml"
        if not path.is_file():
            raise ScriptNotFoundError(
                f"no script {name!r} in {self._directory}; it holds {self.names() or 'none'}"
            )
        return parse_script(path.read_bytes(), name=name)

    def resolve(self, reference: ScriptReference) -> LLMScript:
        """The script ``reference`` names, refused unless the library holds that exact version.

        Raises:
            ScriptNotFoundError, ScriptFormatError: as :meth:`get`.
            ScriptVersionMismatchError: the library's copy is another version, so answering from
                it would make the cycle's record name answers it never ran on.
        """
        script = self.get(reference.name)
        if script.version != reference.version:
            raise ScriptVersionMismatchError(
                f"the cycle pinned {reference}, but {self._directory} holds "
                f"{script.reference}: this process was built from a different tree than the one "
                "the cycle was created against"
            )
        return script

    def digest(self) -> str:
        """One version for the whole library, over every script's name and version. The deploy
        record carries it as the scripted model's digest, so a deploy says which scripts it held.
        """
        scripts = ";".join(
            f"{name}@{script_version((self._directory / f'{name}.yaml').read_bytes())}"
            for name in self.names()
        )
        return hashlib.sha256(scripts.encode()).hexdigest()[:_VERSION_LENGTH]

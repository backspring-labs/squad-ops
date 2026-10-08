"""The authoring replay envelope (SIP-0110 §0.11; #2105).

One authoring task's pre-authoring state, captured immediately before its first model call, so
the replay (#2106) can run the same authoring with and without a memory intervention. It holds:
- the messages exactly as sent;
- the inputs the handler was handed, so the handler's own prompt construction can be re-run
  from them;
- the model's settings;
- when it was captured, which is the target's **pre-authoring cutoff** for temporal validity
  (§0.11): no lesson resting on later evidence may be replayed into it.

Pure: no I/O. ``_llm_call`` builds the envelope, the task result carries it, and the runtime
records it through the cycle registry. It is never a run artifact: the run's artifacts feed
later tasks' prompts by producing task (`_resolve_artifact_contents`), and an envelope there
would feed one task's prompt into the next.

The capture is complete, independent of the 10,000-character cut on LangFuse's stored prompts
(#1756). It covers the four seams only, for replay. It does not store every generation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: Bumped when a field changes meaning, so a reader can refuse an envelope it cannot replay.
ENVELOPE_SCHEMA_VERSION = 1


class AuthoringSeam(StrEnum):
    """The four authoring seams where memory is supplied and authoring is captured (§0.9)."""

    PLAN_WRITING = "plan_writing"
    BUILD_AUTHORING = "build_authoring"
    REPAIR = "repair"
    PROPOSAL_WRITING = "proposal_writing"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_safe(value: Any) -> tuple[Any, list[str]]:
    """``value`` as plain JSON, and the dotted paths of what could not be carried.

    A task's inputs are JSON on the wire, but the agent may add an object (a port, a vault) before
    the handler runs. Such a value cannot be replayed from text, so it is named rather than
    rendered as its ``repr``: a replay that needed it fails loudly instead of re-authoring from a
    string that only looks like an input.
    """
    dropped: list[str] = []

    def walk(item: Any, path: str) -> Any:
        if item is None or isinstance(item, (str, bool, int, float)):
            return item
        if isinstance(item, Mapping):
            return {str(k): walk(v, f"{path}.{k}" if path else str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(item)]
        dropped.append(path or "<root>")
        return None

    return walk(value, ""), dropped


def envelope_id(envelope: Mapping[str, Any]) -> str:
    """One capture's identity: its task, its cutoff and its messages. A duplicate delivery of the
    same capture has the same id, and a retried task's new authoring a new one."""
    return sha256_text(
        f"{envelope['task_id']}|{envelope['captured_at']}|{envelope['messages_sha256']}"
    )


def messages_digest(messages: Sequence[Mapping[str, str]]) -> str:
    """One hash over the ordered (role, content) pairs, so a reordered or re-roled message is a
    different prompt even when every content is the same."""
    canonical = json.dumps(
        [[m["role"], m["content"]] for m in messages], ensure_ascii=False, separators=(",", ":")
    )
    return sha256_text(canonical)


@dataclass(frozen=True)
class AuthoringReplayEnvelope:
    """What one authoring task was given, immediately before it authored (§0.11)."""

    seam: AuthoringSeam
    task_type: str
    task_id: str
    cycle_id: str
    project_id: str
    agent_id: str
    role: str
    handler_name: str
    #: The pre-authoring cutoff, UTC ISO-8601: the moment of the first model call.
    captured_at: str
    #: Each message as sent, in order: ``{"role": ..., "content": ...}``.
    messages: tuple[dict[str, str], ...]
    messages_sha256: str
    #: The call's settings (model, temperature, token budget, reasoning), as sent.
    chat_kwargs: dict[str, Any]
    #: The inputs the handler was handed, as plain JSON.
    inputs: dict[str, Any]
    #: Input paths that held a value JSON cannot carry; a replay that needs one cannot run.
    inputs_not_captured: tuple[str, ...] = ()
    #: The request template's provenance, where the handler passed its render to the call.
    request_template: dict[str, str] | None = None
    #: The memory snapshot pinned for the unit and the exact intervention supplied. Empty until
    #: slice 3 supplies memory (#2096); a replay arm records its own.
    memory: dict[str, Any] = field(default_factory=lambda: {"snapshot": None, "intervention": None})
    schema_version: int = ENVELOPE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "seam": self.seam.value,
            "task_type": self.task_type,
            "task_id": self.task_id,
            "cycle_id": self.cycle_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "handler_name": self.handler_name,
            "captured_at": self.captured_at,
            "messages": [dict(m) for m in self.messages],
            "messages_sha256": self.messages_sha256,
            "chat_kwargs": dict(self.chat_kwargs),
            "inputs": dict(self.inputs),
            "inputs_not_captured": list(self.inputs_not_captured),
            "request_template": dict(self.request_template) if self.request_template else None,
            "memory": dict(self.memory),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AuthoringReplayEnvelope:
        """The envelope a ``to_dict`` produced. Refuses a schema this reader does not know and a
        message list that no longer matches its own hash: either would replay something other
        than what was captured."""
        version = int(data.get("schema_version", 0))
        if version != ENVELOPE_SCHEMA_VERSION:
            raise ValueError(
                f"authoring envelope schema {version} is not {ENVELOPE_SCHEMA_VERSION}, "
                "which this reader replays"
            )
        messages = tuple(
            {"role": str(m["role"]), "content": str(m["content"])} for m in data["messages"]
        )
        if messages_digest(messages) != data["messages_sha256"]:
            raise ValueError(
                f"authoring envelope {data.get('task_id')}: its messages do not match their hash"
            )
        return cls(
            seam=AuthoringSeam(data["seam"]),
            task_type=str(data["task_type"]),
            task_id=str(data["task_id"]),
            cycle_id=str(data["cycle_id"]),
            project_id=str(data.get("project_id") or ""),
            agent_id=str(data.get("agent_id") or ""),
            role=str(data.get("role") or ""),
            handler_name=str(data.get("handler_name") or ""),
            captured_at=str(data["captured_at"]),
            messages=messages,
            messages_sha256=str(data["messages_sha256"]),
            chat_kwargs=dict(data.get("chat_kwargs") or {}),
            inputs=dict(data.get("inputs") or {}),
            inputs_not_captured=tuple(data.get("inputs_not_captured") or ()),
            request_template=dict(data["request_template"])
            if data.get("request_template")
            else None,
            memory=dict(data.get("memory") or {"snapshot": None, "intervention": None}),
            schema_version=version,
        )


def capture_envelope(
    *,
    seam: AuthoringSeam,
    task_type: str,
    task_id: str,
    cycle_id: str,
    project_id: str,
    agent_id: str,
    role: str,
    handler_name: str,
    captured_at: str,
    messages: Sequence[tuple[str, str]],
    chat_kwargs: Mapping[str, Any],
    inputs: Mapping[str, Any],
    inputs_not_captured: Sequence[str] = (),
    request_template: Mapping[str, str] | None = None,
) -> AuthoringReplayEnvelope:
    """The envelope for one authoring call. ``messages`` are ``(role, content)`` pairs as sent.

    ``inputs`` may already be plain JSON, taken when the handler was handed them, with
    ``inputs_not_captured`` naming what that copy could not carry."""
    sent = tuple({"role": role_, "content": content} for role_, content in messages)
    safe_inputs, dropped = json_safe(dict(inputs))
    not_captured = [*inputs_not_captured, *(p for p in dropped if p not in inputs_not_captured)]
    safe_kwargs, _ = json_safe(dict(chat_kwargs))
    return AuthoringReplayEnvelope(
        seam=seam,
        task_type=str(task_type),
        task_id=task_id,
        cycle_id=cycle_id,
        project_id=project_id,
        agent_id=agent_id,
        role=role,
        handler_name=handler_name,
        captured_at=captured_at,
        messages=sent,
        messages_sha256=messages_digest(sent),
        chat_kwargs=safe_kwargs,
        inputs=safe_inputs,
        inputs_not_captured=tuple(not_captured),
        request_template=dict(request_template) if request_template else None,
    )

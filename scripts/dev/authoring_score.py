#!/usr/bin/env python3
"""Score recorded answers with their task type's own handler, run inside the agent container of the
envelopes' role (SIP-0111 §4's G1; #2199). The host side is ``engine_replay.py score``, which copies this
file, ``authoring_replay.py`` and ``authoring_reconstruct.py`` in and pipes the answers on stdin; one JSON
record per line comes back on stdout.

Each answer is handed to the handler that asked for it, on the envelope's own inputs, through a model
port that returns the recorded answer to the first call. The handler's own parsing, validation and
emission path then run on it as they would in a cycle. **The first answer is what is scored:** a
handler that calls the model again (its retry with the failure's fact, a correction) is stopped there,
and the request it would have sent is recorded as the reason.

**Isolation:** as in the replay, nothing here touches a store, and no envelope is captured.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from authoring_reconstruct import _Captured  # noqa: E402
from authoring_replay import _context  # noqa: E402


class _Recorded:
    """A model port that answers the first call with the recorded answer and stops at the second."""

    default_model = "recorded"

    def __init__(self, reply: Any) -> None:
        self._reply = reply
        self.first: list[Any] | None = None

    async def chat_stream_with_usage(self, messages: list[Any], **chat_kwargs: Any) -> Any:
        if self.first is not None:
            raise _Captured(list(messages), dict(chat_kwargs))
        self.first = list(messages)
        return self._reply

    async def chat(self, messages: list[Any], **chat_kwargs: Any) -> Any:
        return await self.chat_stream_with_usage(messages, **chat_kwargs)


def _reply(answer: dict) -> Any:
    from squadops.llm.models import ChatMessage

    prompt, completion = answer.get("prompt_tokens"), answer.get("completion_tokens")
    return ChatMessage(
        role="assistant",
        content=answer["content"],
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=(prompt or 0) + (completion or 0) if prompt or completion else None,
        reasoning_text=answer.get("reasoning_text"),
        # How the call ended, where the engine's adapter reports it (TensorFold's; Ollama's reports
        # none). The cap check reads it before the token count (``reached_cap``), as in production.
        termination=answer.get("termination"),
    )


async def score(
    envelope: dict, answer: dict, registry: Any, prompt_service: Any, renderer: Any
) -> dict:
    from squadops.memory.authoring_envelope import (
        AuthoringReplayEnvelope,
        inputs_as_handed,
        messages_digest,
    )

    port = _Recorded(_reply(answer))
    context = _context(envelope, port, prompt_service, renderer)
    handler = registry.get(envelope["task_type"])
    inputs = inputs_as_handed(AuthoringReplayEnvelope.from_dict(envelope))
    record: dict[str, Any] = {"record": "score", "key": answer["key"]}
    try:
        result = await handler.handle(context, copy.deepcopy(inputs))
    except _Captured as again:
        last = again.messages[-1] if again.messages else None
        record.update(
            verdict="asked_again",
            # The fact the handler would have sent with its second call: the first answer's failure.
            asked=str(getattr(last, "content", ""))[-4000:],
        )
    except Exception as exc:  # the handler raised on the answer: recorded, never taken as a pass
        record.update(verdict="raised", error=f"{type(exc).__name__}: {exc}"[:4000])
    else:
        outputs = getattr(result, "outputs", {}) or {}
        record.update(
            verdict="pass" if getattr(result, "success", False) else "failed",
            error=getattr(result, "error", None),
            artifacts=[a.get("name") for a in outputs.get("artifacts", []) if isinstance(a, dict)],
        )
    # Whether the handler, on today's code, asks the question the answer was written for.
    record["first_call_is_the_capture"] = (
        port.first is not None
        and messages_digest([{"role": m.role, "content": m.content} for m in port.first])
        == envelope["messages_sha256"]
    )
    return record


async def _main() -> int:
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.bootstrap.handlers import create_handler_registry
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer

    payload = json.load(sys.stdin)
    registry = create_handler_registry()
    prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    envelopes = {e["envelope_id"]: e for e in payload["cases"]}
    for answer in payload["answers"]:
        record = await score(
            envelopes[answer["envelope_id"]], answer, registry, prompt_service, renderer
        )
        print(json.dumps(record), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

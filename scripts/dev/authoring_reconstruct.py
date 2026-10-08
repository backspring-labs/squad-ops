"""Re-run an authoring task's own prompt construction from its envelope (SIP-0110 §0.11; #2105).

The proof that an envelope is complete: hand the captured inputs to the same handler, with the
image's own prompt assets, stop at the model call, and compare what would have been sent with
what was sent, byte for byte. The replay's baseline arm (#2106) is this same re-run, and its
memory arm differs only by the intervention.

Runs **inside the agent container that captured the envelope**, so the handler code and the
prompt assets are the deploy's own. The renderer reads the image's shipped files: a deploy whose
asset source is the LangFuse registry refuses to boot unless the registry serves those same
files (`verify_registry_serves_shipped_assets`, #352), so the two are one source.

Reads a JSON list of envelopes on stdin and writes a JSON list of verdicts on stdout. The host
side is `verify_authoring_envelopes.py`.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from types import SimpleNamespace
from typing import Any


class _Captured(BaseException):  # noqa: N818 - a stop signal, not an error
    """Raised at the model call to stop the re-run with what it would have sent.

    A ``BaseException`` so a handler's ``except Exception`` cannot swallow it and carry on as if
    the model had failed."""

    def __init__(self, messages: list[Any], chat_kwargs: dict[str, Any]) -> None:
        super().__init__("captured")
        self.messages = messages
        self.chat_kwargs = chat_kwargs


class _StopAtTheCall:
    """An LLM port that answers nothing: the first call is where the re-run ends."""

    default_model = "reconstruction"

    async def chat_stream_with_usage(self, messages: list[Any], **chat_kwargs: Any) -> Any:
        raise _Captured(list(messages), dict(chat_kwargs))

    async def chat(self, messages: list[Any], **chat_kwargs: Any) -> Any:
        raise _Captured(list(messages), dict(chat_kwargs))


def _first_difference(expected: list[tuple[str, str]], got: list[tuple[str, str]]) -> dict | None:
    for index, (want, have) in enumerate(zip(expected, got, strict=False)):
        if want == have:
            continue
        if want[0] != have[0]:
            return {"message": index, "field": "role", "expected": want[0], "got": have[0]}
        at = next(
            (i for i, (a, b) in enumerate(zip(want[1], have[1], strict=False)) if a != b),
            min(len(want[1]), len(have[1])),
        )
        return {
            "message": index,
            "field": "content",
            "char": at,
            "expected": want[1][max(0, at - 60) : at + 60],
            "got": have[1][max(0, at - 60) : at + 60],
        }
    if len(expected) != len(got):
        return {
            "message": min(len(expected), len(got)),
            "field": "count",
            "expected": len(expected),
            "got": len(got),
        }
    return None


async def reconstruct(
    envelope: dict[str, Any], registry: Any, prompt_service: Any, renderer: Any
) -> dict:
    """One envelope's verdict: whether its handler, re-run on its inputs, sends exactly its
    messages. ``registry``, ``prompt_service`` and ``renderer`` are the image's own."""
    from squadops.capabilities.handlers.context import ExecutionContext
    from squadops.memory.authoring_envelope import AuthoringReplayEnvelope

    captured = AuthoringReplayEnvelope.from_dict(envelope)
    verdict: dict[str, Any] = {
        "task_id": captured.task_id,
        "task_type": captured.task_type,
        "seam": captured.seam.value,
        "captured_at": captured.captured_at,
        "envelope_bytes": len(json.dumps(envelope).encode("utf-8")),
    }
    if captured.inputs_not_captured:
        return {
            **verdict,
            "byte_exact": False,
            "reason": "inputs not captured",
            "paths": list(captured.inputs_not_captured),
        }
    ports = SimpleNamespace(
        llm=_StopAtTheCall(),
        prompt_service=prompt_service,
        request_renderer=renderer,
        llm_observability=None,
        filesystem=None,
        memory=None,
        queue=None,
        metrics=None,
        events=None,
    )
    context = ExecutionContext.create(
        agent_id=captured.agent_id,
        role_id=captured.role,
        task_id=captured.task_id,
        cycle_id=captured.cycle_id,
        ports=ports,  # type: ignore[arg-type]
        project_id=captured.project_id,
    )
    handler = registry.get(captured.task_type)
    try:
        await handler.handle(context, copy.deepcopy(captured.inputs))
    except _Captured as stop:
        got = [(m.role, m.content) for m in stop.messages]
        expected = [(m["role"], m["content"]) for m in captured.messages]
        difference = _first_difference(expected, got)
        return {
            **verdict,
            "byte_exact": difference is None,
            "first_difference": difference,
            "chat_kwargs_equal": json.loads(json.dumps(stop.chat_kwargs, default=str))
            == captured.chat_kwargs,
        }
    except Exception as exc:  # the re-run failed before reaching the model
        return {
            **verdict,
            "byte_exact": False,
            "reason": f"the re-run raised {type(exc).__name__}: {exc}",
        }
    return {
        **verdict,
        "byte_exact": False,
        "reason": "the re-run returned without calling the model",
    }


async def _main() -> int:
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.bootstrap.handlers import create_handler_registry
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer

    envelopes = json.load(sys.stdin)
    registry = create_handler_registry()
    prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    verdicts = [await reconstruct(e, registry, prompt_service, renderer) for e in envelopes]
    json.dump(verdicts, sys.stdout)
    return 0 if all(v["byte_exact"] for v in verdicts) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

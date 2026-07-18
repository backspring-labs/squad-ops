"""Shared helpers for plan-authoring handlers (SIP-0093).

Multi-role plan authoring routes through three handler families:

- ``*.propose_plan_tasks`` — per-role proposers (dev, qa, builder)
  emit ``proposed_plan_tasks.yaml`` scoped to their domain.
- ``governance.merge_plan`` — the lead merges proposals into the
  canonical ``implementation_plan.yaml`` + ``merge_decisions.yaml``
  + ``planning_artifact.md``.

Each handler runs a retry-with-corrective-feedback LLM loop and emits
fenced YAML in a known filename. ``retry_yaml_call`` below is the shared
loop body; handlers plug in their own parse/validate via the
``parse_and_validate`` callback.

This module is intentionally function-style (no service class). The
handlers are the agents; this module is their toolbox.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

logger = logging.getLogger(__name__)


async def retry_yaml_call(
    llm: Any,
    chat_kwargs: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    parse_and_validate: Callable[[str | None], tuple[Any | None, str | None]],
    max_attempts: int,
    handler_name: str,
    on_success_content: Callable[[str], None] | None = None,
) -> tuple[Any | None, str | None, str | None]:
    """Drive an LLM call with up to ``max_attempts`` retries.

    On each attempt, ``parse_and_validate(yaml_or_none)`` returns
    ``(parsed_obj, error_msg)``. ``error_msg is None`` means accept;
    otherwise the message becomes corrective feedback for the next
    attempt.

    Returns ``(parsed_obj, last_yaml, last_error)``. ``parsed_obj`` is
    ``None`` if all attempts failed; ``last_yaml`` carries the most
    recent raw YAML for diagnostic logging.

    ``on_success_content``, if given, is called with the full raw response of
    the accepted attempt — the caller can then pull additional fenced blocks
    the primary YAML extractor discards (SIP-0099 99.2: the interface manifest
    a framing proposer may emit alongside ``proposed_plan_tasks.yaml``).
    """
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
    last_yaml: str | None = None
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = await llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning(
                "%s: LLM call failed on attempt %d/%d (%s)",
                handler_name,
                attempt,
                max_attempts,
                exc,
            )
            last_error = str(exc)
            if attempt >= max_attempts:
                return None, last_yaml, last_error
            messages = messages[:2]
            continue

        content = response.content
        # Each handler tells us which filename to expect via the
        # closure in parse_and_validate; this layer just hands over the
        # raw YAML or None.
        last_yaml = _first_yaml_block_or_none(content)

        parsed, err = parse_and_validate(last_yaml)
        if err is None and parsed is not None:
            logger.info("%s: produced valid output on attempt %d", handler_name, attempt)
            if on_success_content is not None:
                on_success_content(content)
            return parsed, last_yaml, None

        logger.warning(
            "%s: attempt %d/%d failed: %s",
            handler_name,
            attempt,
            max_attempts,
            err,
        )
        last_error = err
        if attempt >= max_attempts:
            return None, last_yaml, last_error

        messages = [
            *messages,
            ChatMessage(role="assistant", content=content),
            ChatMessage(role="user", content=err or "Please correct the previous output."),
        ]

    return None, last_yaml, last_error


def extract_interface_manifest_yaml(content: str) -> str | None:
    """Return the raw ``interface_manifest.yaml`` fenced block a framing role emitted,
    or ``None`` if it did not (SIP-0099 phase 99.2). Data-driven: absence means the
    cycle keeps today's non-scaffolded behavior. Selected by filename, so it is robust
    to block ordering (unlike the first-yaml-block plan extraction)."""
    for f in extract_fenced_files(content or ""):
        if f["filename"] == "interface_manifest.yaml":
            return f["content"]
    return None


def _first_yaml_block_or_none(content: str) -> str | None:
    """Best-effort YAML extraction without a known filename. Used by
    ``retry_yaml_call`` when the parse_and_validate callback handles
    filename-specific shape itself."""
    import re

    extracted = extract_fenced_files(content)
    if extracted:
        for f in extracted:
            if f["filename"].endswith(".yaml") or f["filename"].endswith(".yml"):
                return f["content"]
    pattern = r"```yaml\s*\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(1).strip()
        if block:
            return block
    return None

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

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

logger = logging.getLogger(__name__)


async def contract_surface_sections(renderer: Any, inputs: dict[str, Any]) -> str:
    """The contract surfaces an author needs, rendered, or ``""``.

    Two managed assets (#448 — the prose is theirs, only the index data is a variable):

    - ``request.plan_bind_criteria_appendix`` — *bind, don't author* plus the criteria
      index, so covered-file criteria arrive as ``criteria_refs`` (SIP-0098 98.3);
    - ``request.plan_frozen_surface_appendix`` — what the scaffold froze, so a check is
      not written against an invented interior and a frozen file is not claimed as a
      deliverable (pf-42).

    **Shared because it had two authors and reached one (#846).** Only
    ``*.propose_plan_tasks`` rendered these. When no ``plan_authoring_contributors`` are
    configured — every CRP but ``validation-multirole``  — the proposers do not run at all
    and ``governance.merge_plan`` authors the plan alone through
    ``_plan_authoring_service.produce_plan``, which had no access to either surface.

    Measured on VS's Next.js re-roll (``cyc_0edb55919384``), whose plan was
    ``authoring_mode: sole_author`` with every task ``gap_filled``: **0 criteria_refs**
    (it could not bind an index it never saw), 3 frozen files claimed as deliverables,
    8 invented paths and 3 fill slots claimed by nothing. The paths it invented were
    plausible variants of the real ones — ``app/api/runs/[id]/route.ts`` for the slot's
    ``[run_id]`` — which is what an author with the manifest's endpoints and none of the
    contract's file list produces.

    Empty when the keys are absent, which is author mode with no derived contract: the
    prompt stays byte-identical there.
    """
    if renderer is None:
        return ""
    surfaces = (
        ("request.plan_bind_criteria_appendix", "criteria_index", "contract_criteria_index"),
        ("request.plan_frozen_surface_appendix", "frozen_surface_index", "frozen_surface_index"),
    )
    sections: list[str] = []
    for template_id, variable, input_key in surfaces:
        index = inputs.get(input_key)
        if not index:
            continue
        rendered = await renderer.render(template_id, {variable: index})
        sections.append(rendered.content)
    return "".join(sections)


async def retry_yaml_call(
    llm: Any,
    chat_kwargs: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    parse_and_validate: Callable[
        [str | None],
        tuple[Any | None, str | None] | Awaitable[tuple[Any | None, str | None]],
    ],
    max_attempts: int,
    handler_name: str,
) -> tuple[Any | None, str | None, str | None]:
    """Drive an LLM call with up to ``max_attempts`` retries.

    On each attempt, ``parse_and_validate(yaml_or_none)`` returns
    ``(parsed_obj, error_msg)``. ``error_msg is None`` means accept;
    otherwise the message becomes corrective feedback for the next
    attempt.

    Returns ``(parsed_obj, last_yaml, last_error)``. ``parsed_obj`` is
    ``None`` if all attempts failed; ``last_yaml`` carries the most
    recent raw YAML for diagnostic logging.

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

        verdict = parse_and_validate(last_yaml)
        # An async callback is accepted so a handler can render its corrective feedback
        # through a managed prompt asset rather than assembling the prose inline
        # (CLAUDE.md #448) — the manifest-authoring loop needs that, the plan loops do
        # not, and a sync callback is unaffected.
        if inspect.isawaitable(verdict):
            verdict = await verdict
        parsed, err = verdict
        if err is None and parsed is not None:
            logger.info("%s: produced valid output on attempt %d", handler_name, attempt)
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

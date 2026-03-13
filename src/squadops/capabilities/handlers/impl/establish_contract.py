"""Governance establish_contract handler (SIP-0079 §7.2).

Extracts the planning artifact from prior outputs and asks the LLM
to produce a structured RunContract (objective, acceptance criteria,
stop conditions, etc.). On parse failure returns NEEDS_REPLAN.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.cycle_tasks import _CycleTaskHandler
from squadops.cycles.task_outcome import TaskOutcome
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

_CONTRACT_SYSTEM_PROMPT = """\
You are the governance lead. Given the planning artifacts and PRD, produce a
JSON run contract with these fields:
- objective (string): one-sentence goal
- acceptance_criteria (list[string]): measurable success criteria
- non_goals (list[string]): explicitly out of scope
- time_budget_seconds (int): maximum wall-clock seconds
- stop_conditions (list[string]): conditions that should halt execution
- required_artifacts (list[string]): artifact filenames that must be produced

Return ONLY valid JSON, no markdown fences, no explanation."""


class GovernanceEstablishContractHandler(_CycleTaskHandler):
    """Establish a run contract before implementation begins."""

    _handler_name = "governance_establish_contract_handler"
    _capability_id = "governance.establish_contract"
    _role = "lead"
    _artifact_name = "run_contract.json"

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        start_time = time.perf_counter()

        prd = inputs.get("prd", "")
        prior_outputs = inputs.get("prior_outputs")

        # SIP-0084: dual-path — use request renderer when available
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is not None:
            variables = self._build_render_variables(prd, prior_outputs, inputs)
            rendered = await renderer.render(self._request_template_id, variables)
            user_prompt = rendered.content
        else:
            user_prompt = self._build_user_prompt(prd, prior_outputs)

        messages = [
            ChatMessage(role="system", content=_CONTRACT_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        chat_kwargs = self._build_chat_kwargs(inputs)

        try:
            response = await context.ports.llm.chat(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning("LLM call failed for %s: %s", self._handler_name, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={"outcome_class": TaskOutcome.NEEDS_REPLAN},
                _evidence=evidence,
                error=str(exc),
            )

        content = response.content

        # Parse JSON contract from LLM response
        try:
            # Strip markdown fences if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)
            contract_data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse run contract JSON: %s", exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self._handler_name,
                capability_id=self._capability_id,
                duration_ms=duration_ms,
                inputs_hash=self._hash_dict(inputs),
            )
            return HandlerResult(
                success=False,
                outputs={"outcome_class": TaskOutcome.NEEDS_REPLAN},
                _evidence=evidence,
                error=f"Failed to parse run contract: {exc}",
            )

        duration_ms = (time.perf_counter() - start_time) * 1000

        outputs = {
            "summary": (
                f"[lead] Run contract established: "
                f"{contract_data.get('objective', '')[:60]}"
            ),
            "role": self._role,
            "contract": contract_data,
            "artifacts": [
                {
                    "name": self._artifact_name,
                    "content": json.dumps(contract_data, indent=2),
                    "media_type": "application/json",
                    "type": "run_contract",
                },
            ],
        }

        evidence = HandlerEvidence.create(
            handler_name=self._handler_name,
            capability_id=self._capability_id,
            duration_ms=duration_ms,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict(outputs),
        )

        return HandlerResult(success=True, outputs=outputs, _evidence=evidence)

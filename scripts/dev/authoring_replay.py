#!/usr/bin/env python3
"""The authoring replay, run inside the agent container of the envelopes' role (SIP-0110 §0.11; slice 2,
#2106). The host runner (``run_authoring_replay.py``) copies this file and ``authoring_reconstruct.py``
in and pipes the experiment on stdin; one JSON record per line comes back on stdout.

For each case it first checks **instrument validity**: the baseline arm, re-run up to its model call,
sends exactly the captured prompt, and the memory arm's prompt differs from it only by the lessons'
section. A case that fails is reported and never authored. Then each scheduled ``(case, arm,
generation)`` is authored for real, with the image's own handler, prompt assets and model port, and
its prompt, the model's replies and the handler's outputs are recorded.

**A skills case** (SIP-0116 §17p; ``payload["skill_cases"]``) is authored under two arms: the
baseline, and the task handed the skills its cycle would hand it if its development profile
required the case's skillset. Its equipment is built here, from the image's own packaged
skillsets. A case with swaps has no capture behind its prompt, so only an unswapped case is
checked against one; every case's skills arm must differ from its baseline by the skills'
section alone. Each authoring records the declared stop its model answered with, if any.

**Isolation:** nothing here touches a store. The context carries no authoring capture, so no
envelope is recorded, and the records go only to stdout.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from authoring_reconstruct import _Captured, _StopAtTheCall  # noqa: E402


class _Recording:
    """The model port, recording every call's messages and reply."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm
        self.default_model = getattr(llm, "default_model", None)
        self.calls: list[dict[str, Any]] = []

    async def chat_stream_with_usage(self, messages: list[Any], **kwargs: Any) -> Any:
        reply = await self._llm.chat_stream_with_usage(messages, **kwargs)
        self._record(messages, reply)
        return reply

    async def chat(self, messages: list[Any], **kwargs: Any) -> Any:
        reply = await self._llm.chat(messages, **kwargs)
        self._record(messages, reply)
        return reply

    def _record(self, messages: list[Any], reply: Any) -> None:
        from squadops.memory.authoring_envelope import messages_digest

        # The envelope's own digest, so a baseline call reads against its case's messages_sha256.
        self.calls.append(
            {
                "messages_sha256": messages_digest(
                    [{"role": m.role, "content": m.content} for m in messages]
                ),
                "reply": str(getattr(reply, "content", reply)),
            }
        )


def _context(envelope: dict, llm: Any, prompt_service: Any, renderer: Any) -> Any:
    from squadops.capabilities.handlers.context import ExecutionContext

    ports = SimpleNamespace(
        llm=llm,
        prompt_service=prompt_service,
        request_renderer=renderer,
        llm_observability=None,
        filesystem=None,
        queue=None,
        metrics=None,
        events=None,
    )
    return ExecutionContext.create(
        agent_id=envelope["agent_id"],
        role_id=envelope["role"],
        task_id=envelope["task_id"],
        cycle_id=envelope["cycle_id"],
        ports=ports,  # type: ignore[arg-type]
        project_id=envelope["project_id"],
    )


async def _prompt(handler: Any, envelope: dict, inputs: dict, prompt_service: Any, renderer: Any):
    """What the handler would send for ``inputs``, stopped at the model call."""
    context = _context(envelope, _StopAtTheCall(), prompt_service, renderer)
    try:
        await handler.handle(context, copy.deepcopy(inputs))
    except _Captured as stop:
        return [m.content for m in stop.messages]
    return None


async def _skill_case(
    envelope_id: str,
    envelope: dict,
    case: dict,
    handler: Any,
    prompt_service: Any,
    renderer: Any,
    catalog: Any,
    experiment: str,
) -> tuple[dict, dict[str, dict]]:
    """One skills case's validity record, and its inputs by arm (empty when it isn't valid).

    A case that can't be built as written (a swap that changes nothing, a skillset that loads
    no skill for the task) is reported with its reason and never authored."""
    from squadops.campaigns.change_request import PRODUCT_PROPOSAL_INPUT
    from squadops.capabilities.handlers.skills import skills_section
    from squadops.capabilities.skillsets import SKILLS_INPUT
    from squadops.cycles.skillset_replay import task_equipment
    from squadops.memory.authoring_envelope import AuthoringReplayEnvelope, inputs_as_handed
    from squadops.memory.replay import Arm, arm_inputs, swapped_inputs, validity

    swaps = case.get("swaps") or []
    record: dict[str, Any] = {
        "record": "validity",
        "envelope_id": envelope_id,
        "case": case["case"],
        "capture_checked": not swaps,
    }
    try:
        own = swapped_inputs(envelope["inputs"], swaps) if swaps else envelope["inputs"]
        equipment = task_equipment(
            catalog,
            skillset=case["skillset"],
            role=envelope["role"],
            agent_id=envelope["agent_id"],
            task_type=envelope["task_type"],
            vocabulary_skillset=case.get("vocabulary_skillset") or "",
        )
        handed = [((SKILLS_INPUT,), equipment.skills)]
        if equipment.scenario_vocabulary is not None:
            handed.append(
                ((PRODUCT_PROPOSAL_INPUT, "scenario_vocabulary"), equipment.scenario_vocabulary)
            )
        inputs = {
            Arm.BASELINE.value: arm_inputs(own, Arm.BASELINE, experiment_id=experiment),
            Arm.SKILLS.value: arm_inputs(
                own, Arm.SKILLS, experiment_id=experiment, equipment=handed
            ),
        }
    except ValueError as exc:
        return {**record, "valid": False, "reason": str(exc)}, {}
    baseline = await _prompt(
        handler, envelope, inputs[Arm.BASELINE.value], prompt_service, renderer
    )
    skills = await _prompt(handler, envelope, inputs[Arm.SKILLS.value], prompt_service, renderer)
    section = await skills_section(renderer, inputs[Arm.SKILLS.value])
    if swaps:
        # No capture stands behind a swapped prompt, so there is nothing to reproduce.
        captured = reproduced = baseline or []
    else:
        captured = [m["content"] for m in envelope["messages"]]
        reproduced = await _prompt(
            handler,
            envelope,
            inputs_as_handed(AuthoringReplayEnvelope.from_dict(envelope)),
            prompt_service,
            renderer,
        )
    verdict = validity(captured, reproduced or [], baseline or [], skills, section)
    record.update(
        {
            "baseline_exact": verdict.baseline_exact if not swaps else None,
            "skills_differ_only_by_their_section": verdict.memory_differs_only_by_its_section,
            "valid": bool(baseline) and verdict.valid,
            "skills": equipment.digests(),
            "prompt_chars": {
                "baseline": sum(len(m) for m in baseline or []),
                "skills": sum(len(m) for m in skills or []),
            },
        }
    )
    return record, inputs if record["valid"] else {}


async def replay(
    payload: dict,
    registry: Any,
    prompt_service: Any,
    renderer: Any,
    llm: Any,
    catalog: Any = None,
) -> list[dict]:
    """The experiment's records: each case's validity, then each scheduled authoring.
    ``catalog`` is the skillsets a skills case's equipment is built from: the image's own
    packaged ones when it isn't given."""
    from squadops.capabilities.handlers.cross_cycle_lessons import cross_cycle_lessons_section
    from squadops.capabilities.skill_stops import SkillStop
    from squadops.execution.product_suite import left_to_the_product_runner
    from squadops.memory.authoring_envelope import (
        AuthoringReplayEnvelope,
        inputs_as_handed,
    )
    from squadops.memory.authoring_envelope import envelope_id as id_of
    from squadops.memory.replay import Arm, ReplayLesson, arm_inputs, validity

    experiment = payload["experiment_id"]
    lessons_by_id = {
        lesson["revision_id"]: ReplayLesson(lesson["revision_id"], lesson["text"], ())
        for lesson in payload.get("lessons", [])
    }
    cases = {e.get("envelope_id") or id_of(e): e for e in payload["cases"]}
    skill_cases = payload.get("skill_cases") or {}
    if skill_cases and catalog is None:
        from squadops.capabilities.skillsets import load_skillsets

        catalog = load_skillsets()
    records: list[dict] = []
    valid: set[str] = set()
    inputs_of: dict[tuple[str, str], dict] = {}
    for envelope_id, envelope in cases.items():
        handler = registry.get(envelope["task_type"])
        if envelope_id in skill_cases:
            check, by_arm = await _skill_case(
                envelope_id,
                envelope,
                skill_cases[envelope_id],
                handler,
                prompt_service,
                renderer,
                catalog,
                experiment,
            )
            records.append(check)
            if check["valid"]:
                valid.add(envelope_id)
            inputs_of.update({(envelope_id, arm): held for arm, held in by_arm.items()})
            continue
        own = envelope["inputs"]
        lessons = [lessons_by_id[r] for r in payload.get("case_lessons", {}).get(envelope_id, [])]
        arms = [Arm(a) for a in payload["arms"]]
        for arm in arms:
            if arm is Arm.SCOPED_MEMORY and not lessons:
                continue
            inputs_of[(envelope_id, arm.value)] = arm_inputs(
                own,
                arm,
                experiment_id=experiment,
                lessons=lessons,
                static_guidance=payload.get("static_guidance", ""),
            )
        handed = inputs_as_handed(AuthoringReplayEnvelope.from_dict(envelope))
        reproduced = await _prompt(handler, envelope, handed, prompt_service, renderer)
        baseline = (
            reproduced
            if handed == own
            else await _prompt(handler, envelope, own, prompt_service, renderer)
        )
        memory_inputs = inputs_of.get((envelope_id, Arm.SCOPED_MEMORY.value))
        memory = (
            await _prompt(handler, envelope, memory_inputs, prompt_service, renderer)
            if memory_inputs
            else None
        )
        section = (
            await cross_cycle_lessons_section(renderer, memory_inputs) if memory_inputs else ""
        )
        captured = [m["content"] for m in envelope["messages"]]
        verdict = validity(captured, reproduced or [], baseline or [], memory, section)
        records.append(
            {
                "record": "validity",
                "envelope_id": envelope_id,
                "baseline_exact": verdict.baseline_exact,
                "memory_differs_only_by_its_section": verdict.memory_differs_only_by_its_section,
                "valid": verdict.valid,
            }
        )
        if verdict.valid:
            valid.add(envelope_id)
    if payload.get("validity_only"):
        return records
    for envelope_id, arm_name, generation in payload["schedule"]:
        inputs = inputs_of.get((envelope_id, arm_name))
        if envelope_id not in valid or inputs is None:
            continue
        envelope = cases[envelope_id]
        recording = _Recording(llm)
        context = _context(envelope, recording, prompt_service, renderer)
        result = await registry.get(envelope["task_type"]).handle(context, copy.deepcopy(inputs))
        # Validity checked the baseline's prompt before the model was called; this is the call the
        # scored authoring actually made, read against the capture.
        case = skill_cases.get(envelope_id)
        swapped = bool(case and case.get("swaps"))
        fidelity = (
            {
                "first_call_is_the_capture": bool(recording.calls)
                and recording.calls[0]["messages_sha256"] == envelope["messages_sha256"]
            }
            if arm_name == Arm.BASELINE.value and not swapped
            else {}
        )
        if case is not None:
            # SIP-0116 §17o: the declared stop the model answered with, as ``_llm_call`` read
            # it. The handler's own failure is whatever its seam makes of a failed call.
            stop = context.skill_stop
            fidelity = {
                **fidelity,
                "case": case["case"],
                "skill_stop": stop.to_dict() if isinstance(stop, SkillStop) else None,
                # What the task as authored expected, after the case's swaps: a captured case
                # names no file of its own, since another capture brings another plan.
                "expected_artifacts": [str(e) for e in inputs.get("expected_artifacts") or ()],
                # #3150: a suite the qa image left to the product's own runner (SIP-0112 H.26)
                # comes back ``success=False`` with no verdict of its own. The framework's own
                # reading of that, so the judge never takes a hand-off for a refusal.
                "left_to_the_product_runner": left_to_the_product_runner(result),
            }
        records.append(
            {
                "record": "authoring",
                "envelope_id": envelope_id,
                "arm": arm_name,
                "generation": generation,
                **fidelity,
                "success": bool(getattr(result, "success", False)),
                "error": getattr(result, "error", None),
                "calls": recording.calls,
                "artifacts": [
                    {"name": a.get("name"), "content": a.get("content")}
                    for a in (getattr(result, "outputs", {}) or {}).get("artifacts", [])
                    if isinstance(a, dict)
                ],
            }
        )
    return records


async def _main() -> int:
    from adapters.llm.factory import create_llm_provider
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.bootstrap.handlers import create_handler_registry
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.config import load_config
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer

    payload = json.load(sys.stdin)
    # The agent's config resolves its secret:// references as the entrypoint does.
    config = load_config(secret_provider_factory=secret_provider_for)
    llm = create_llm_provider(
        provider=config.llm.provider,
        base_url=config.llm.url,
        default_model=config.llm.model,
        timeout_seconds=config.llm.timeout,
        api_key=config.llm.api_key,
    )
    records = await replay(
        payload,
        create_handler_registry(),
        PromptAssembler(create_prompt_repository("filesystem")),
        RequestTemplateRenderer(create_prompt_asset_source("filesystem")),
        llm,
    )
    for record in records:
        print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

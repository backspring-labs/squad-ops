"""An increment's acceptance, on the stack's runner (SIP-0109 §8; #1705 e, part 1).

Deterministic: no model is asked anything. The qa role's container runs it because the stack's
runners, and their per-test reports, live there (the sandbox's typed operations report an exit
code and an output tail, which the §8.2 reading cannot use; #1705 step e reading).

Handed at plan time the increment's id, each new criterion's own file (§8.1) and the routes the
candidate declares; at dispatch the accepted tree as the increment seeded it (#1842) and the
candidate as built (the acceptance workspace). Rendering is not read here (§8.3, #1796): every
declared route arrives unrendered and is ``blocked_unverified``, never passed by omission.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import partial
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.tasks.task_types import TaskType

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

#: Per suite run; two per new criterion (the baseline and the candidate) and one per frozen one.
_SUITE_TIMEOUT_SECONDS = 300


async def _rendered(
    stack: str,
    files: dict[str, str],
    declared: dict[str, tuple[str, ...]],
    inputs: dict[str, Any],
) -> dict[str, frozenset[str] | None]:
    """The test ids each declared route's page rendered (§8.3), by the stack's render profile;
    every route unread (``None``, blocked) for a stack that declares none."""
    from squadops.capabilities.handlers.probe_runner import profile_for_stack
    from squadops.capabilities.handlers.route_rendering import render_profile_for, render_routes
    from squadops.capabilities.scaffold import render_profile_name_for

    if not declared:
        return {}
    profile = render_profile_for(render_profile_name_for(stack))
    probe = profile_for_stack(stack)
    if profile is None or probe is None:
        logger.warning("stack %r declares no render profile: every route is unread", stack)
        return {route: None for route in declared}
    return await asyncio.to_thread(
        render_routes,
        files,
        declared,
        inputs.get("increment_route_seeds") or {},
        profile=profile,
        backend_argv=probe.boot_argv,
        backend_ready_path=probe.ready_path,
    )


class QAEvaluateIncrementHandler(CapabilityHandler):
    """``qa.evaluate_increment``: the increment's discrimination, accumulated acceptance and
    rendering, written as the ``increment_evaluation`` artifact."""

    _handler_name = "qa_evaluate_increment_handler"
    _task_type = TaskType.QA_EVALUATE_INCREMENT

    @property
    def name(self) -> str:
        return self._handler_name

    @property
    def task_type(self) -> str:
        return self._task_type

    async def handle(self, context: ExecutionContext, inputs: dict[str, Any]) -> HandlerResult:
        from squadops.campaigns.acceptance_run import (
            NewCriterion,
            evaluate_increment,
            evaluation_document,
            frozen_criteria_from,
        )
        from squadops.campaigns.evaluator_trees import FileTree, TestSurface
        from squadops.campaigns.increment_tree import (
            INCREMENT_EVALUATION_ARTIFACT_TYPE,
            INCREMENT_EVALUATION_FILENAME,
        )
        from squadops.capabilities.development_profiles import get_development_profile
        from squadops.capabilities.handlers.test_runner import run_suite
        from squadops.capabilities.scaffold import development_profile_for, scaffold_stack_for

        started = time.perf_counter()
        stack = scaffold_stack_for(inputs.get("resolved_config"))
        framework = get_development_profile(development_profile_for(stack)).test_framework
        accepted = FileTree.of(inputs.get("accepted_tree_files") or {})
        candidate = FileTree.of(inputs.get("acceptance_workspace_files") or {})
        increment_id = str(inputs.get("increment_id") or "")
        missing = [
            name
            for name, present in (
                ("the increment's id", increment_id),
                ("the accepted tree", accepted.files),
                ("the candidate tree", candidate.files),
            )
            if not present
        ]
        if missing:
            # Nothing is judged without both trees: an evaluation against an empty baseline
            # would read every new test as discriminating.
            return self._result(
                inputs, started, success=False, error=f"no {', no '.join(missing)} to evaluate"
            )

        new = [
            NewCriterion(f["criterion_id"], f["path"])
            for f in inputs.get("increment_criterion_files") or ()
        ]
        declared = {
            path: tuple(ids)
            for path, ids in (inputs.get("increment_declared_routes") or {}).items()
        }
        candidate_files = dict(inputs.get("acceptance_workspace_files") or {})
        retired = tuple(str(c) for c in inputs.get("increment_retired_criteria") or ())
        evaluation = await evaluate_increment(
            increment_id=increment_id,
            accepted=accepted,
            candidate=candidate,
            surface=TestSurface.for_stack(stack),
            new=new,
            # §8.1: every criterion earlier increments froze, by the bundle its launch pinned.
            frozen=frozen_criteria_from(
                inputs.get("increment_frozen_criteria") or (), inputs.get("frozen_bundles") or {}
            ),
            declared_routes=declared,
            rendered=await _rendered(stack, candidate_files, declared, inputs),
            run=partial(run_suite, framework, timeout_seconds=_SUITE_TIMEOUT_SECONDS),
            invocation=(framework,),
            retired=retired,
        )
        document = evaluation_document(
            evaluation,
            increment_id=increment_id,
            accepted=accepted,
            candidate=candidate,
            new=new,
            retired=retired,
        )
        return self._result(
            inputs,
            started,
            success=True,
            summary=f"[qa] increment {increment_id}: {document['verdict']}",
            artifact={
                "name": INCREMENT_EVALUATION_FILENAME,
                "content": json.dumps(document, indent=2, sort_keys=True),
                "media_type": "application/json",
                "type": INCREMENT_EVALUATION_ARTIFACT_TYPE,
            },
        )

    def _result(
        self,
        inputs: dict[str, Any],
        started: float,
        *,
        success: bool,
        summary: str = "",
        artifact: dict | None = None,
        error: str | None = None,
    ) -> HandlerResult:
        outputs: dict[str, Any] = {"summary": summary or f"[qa] {error}", "role": "qa"}
        if artifact is not None:
            outputs["artifacts"] = [artifact]
        evidence = HandlerEvidence.create(
            handler_name=self.name,
            task_type=self.task_type,
            duration_ms=(time.perf_counter() - started) * 1000,
            inputs_hash=self._hash_dict(
                {k: v for k, v in inputs.items() if not k.endswith("_files")}
            ),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(success=success, outputs=outputs, _evidence=evidence, error=error)

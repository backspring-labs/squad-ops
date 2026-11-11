"""``qa.run_remote_operation``: a verification run by a provider's operation (SIP-0117 R4.4).

Tool-backed and engine-neutral. The plan names a capability contract and a verification mode;
this handler finds the skillset the cycle's record says supplies it, takes that skillset's tool
request, asks the remote-execution port to run the operation against the candidate tree, and
turns the provider's assertion records into the task's evidence. No model is called and no
source is authored.

**Nothing here reads "didn't run" as a pass.** Every assertion the scenario declares produces
one check row:

- ``passed`` and ``failed`` are executed results;
- everything else is not executed, named by its reason, and marked as a criterion the run
  could not verify, so the run's verdict is ``blocked_unverified`` (SIP-0096), never accepted.

An operation that didn't run at all (no port bound, a provider that reports ``not_executed``
or ``interrupted``, or a result that can't be believed) gives every declared assertion that
same not-executed row, with the operation's reason.

**What a failure of this task means.** A failed assertion fails the task, and the correction
loop repairs the application: a dev repair aimed at the implementation, then this operation
re-run on the repaired tree (SIP-0117 R4.4, R5.1). Every other failure of this task (a supplier
the deployment can't vouch for, a provider that raised) carries no executed failure, and
``TaskType.corrects_only_executed_failures`` ends the run on it: there is no application defect
for a developer to fix. A run whose assertions only *didn't execute* isn't a failed task at
all. It succeeds with its unverified rows, and the roll-up reads ``blocked_unverified``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.models import TaskContract
from squadops.capabilities.skillsets import Skillset, packaged_skillsets
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.verification_integrity import ResultStatus
from squadops.remote_execution.models import (
    ASSERTION_RECORDS_ARTIFACT_TYPE,
    OPERATION_EVIDENCE_ARTIFACT_TYPE,
    AssertionOutcome,
    OperationStatus,
    ReadingSide,
    RemoteOperationRequest,
    RemoteOperationResult,
    Scenario,
    outcomes_by_assertion,
    records_document,
    result_defects,
)
from squadops.remote_execution.scenario import staged_revision
from squadops.tasks.task_types import TaskType

ASSERTION_RECORDS_FILENAME = "operation_assertions.json"

#: Reasons for an operation that produced no executed assertion, as the evidence names them.
REASON_NO_PORT = "no_remote_execution_port"
REASON_RESULT_UNREADABLE = "operation_result_unreadable"
REASON_NOT_EXECUTED = "operation_not_executed"
REASON_INTERRUPTED = "operation_interrupted"


def assertion_check_id(scenario_id: str, assertion_id: str) -> str:
    """The check id of one scenario assertion, and its criterion id: an assertion is the
    criterion the scenario froze."""
    return f"scenario:{scenario_id}:{assertion_id}"


class QARunRemoteOperationHandler(CapabilityHandler):
    """``qa.run_remote_operation``: one frozen scenario, run by a provider's operation."""

    _handler_name = "qa_run_remote_operation_handler"
    _task_type = TaskType.QA_RUN_REMOTE_OPERATION

    @property
    def name(self) -> str:
        return self._handler_name

    @property
    def task_type(self) -> str:
        return self._task_type

    def validate_inputs(
        self, inputs: dict[str, Any], contract: TaskContract | None = None
    ) -> list[str]:
        """Everything the operation needs is required, and nothing is filled in: the contract
        and its supplier from the cycle's record, the frozen scenario, and the candidate tree,
        which holds the scenario's declaration at the path the scenario names (#3044)."""
        errors = super().validate_inputs(inputs, contract)
        operation = inputs.get("operation")
        if not isinstance(operation, Mapping):
            errors.append(
                "'operation' is required: the contract, mode and supplying skillset the "
                "cycle's skillset record offers this task"
            )
        else:
            errors.extend(
                f"'operation.{key}' is required"
                for key in ("contract", "skillset", "skillset_digest")
                if not isinstance(operation.get(key), str) or not operation.get(key)
            )
            if not isinstance(operation.get("mode"), str):
                errors.append("'operation.mode' is required, and is empty for a contract with none")
        scenario_errors = _scenario_errors(inputs.get("operation_scenario"))
        errors.extend(scenario_errors)
        files = inputs.get("acceptance_workspace_files")
        if not isinstance(files, Mapping):
            errors.append("'acceptance_workspace_files' is required: the candidate tree to verify")
        elif not scenario_errors:
            path = inputs["operation_scenario"]["path"]
            if not isinstance(files.get(path), str):
                errors.append(
                    f"the candidate tree holds no scenario declaration at {path!r}, where the "
                    "frozen scenario was placed"
                )
        return errors

    async def handle(self, context: ExecutionContext, inputs: dict[str, Any]) -> HandlerResult:
        started = time.perf_counter()
        # The wire stages text. A path whose content isn't text is left out, and named in the
        # reading (#3044 §4), so a result on a tree without it is never read as the whole tree's.
        tree = inputs["acceptance_workspace_files"]
        files = {path: content for path, content in tree.items() if isinstance(content, str)}
        not_staged = tuple(sorted(path for path in tree if path not in files))
        operation = inputs["operation"]
        scenario = _scenario(inputs["operation_scenario"], files)
        try:
            tool = _tool_request(packaged_skillsets(), operation)
        except ValueError as refused:
            # The deployment no longer holds what the cycle's record says supplies this
            # contract. Nothing can be run in its name.
            return self._finish(inputs, started, error=str(refused))
        if context.dispatch_id is None:
            # The operation is asked for, read and stopped under the send this task came in
            # (SIP-0117 R5.6), and the task id is no send: never ask in its place.
            return self._finish(
                inputs,
                started,
                error=(
                    f"task {context.task_id} came in no named send (its envelope has no "
                    "dispatch id), so no remote operation can be asked for under it"
                ),
            )

        request = RemoteOperationRequest(
            contract=operation["contract"],
            mode=operation["mode"],
            provider=tool.provider,
            operation=tool.id,
            location=tool.location,
            # The revision of exactly what is staged (#3044 §4), so a reading binds to the tree
            # the provider ran on, cut the way every lane cuts it.
            source_revision=staged_revision(files),
            source_files=files,
            scenario=scenario,
            task_id=context.task_id,
            dispatch_id=context.dispatch_id,
        )
        port = getattr(context.ports, "remote_execution", None)
        if port is None:
            result = RemoteOperationResult(
                OperationStatus.NOT_EXECUTED,
                reason="this agent has no remote-execution port bound",
                dispatch_id=request.dispatch_id,
            )
            operation_reason = REASON_NO_PORT
        else:
            result = await port.run_operation(request)
            operation_reason = ""

        defects = result_defects(request, result)
        if defects:
            # A provider is outside the framework. A result that doesn't answer this request
            # is evidence of nothing, so no record in it is credited.
            result = RemoteOperationResult(
                OperationStatus.NOT_EXECUTED,
                reason="the provider's result can't be read: " + "; ".join(defects),
                evidence=result.evidence,
                provider_version=result.provider_version,
                ran_with=result.ran_with,
                dispatch_id=request.dispatch_id,
            )
            operation_reason = REASON_RESULT_UNREADABLE
        elif result.status is OperationStatus.NOT_EXECUTED:
            operation_reason = operation_reason or REASON_NOT_EXECUTED
        elif result.status is OperationStatus.INTERRUPTED:
            operation_reason = REASON_INTERRUPTED

        checks = _check_rows(request, result, operation_reason)
        # This task verifies the candidate tree it was handed: its reading is the candidate's.
        document = records_document(
            request,
            result,
            ReadingSide.CANDIDATE,
            not_staged=not_staged,
            skillset=operation["skillset"],
            skillset_digest=operation["skillset_digest"],
        )
        executed = [c for c in checks if c["status"] != ResultStatus.SKIPPED]
        failed = [c for c in checks if c["status"] == ResultStatus.FAILED]
        summary = (
            f"[qa] {request.contract} in {request.mode or 'no'} mode: "
            f"{len(executed) - len(failed)} passed, {len(failed)} failed, "
            f"{len(checks) - len(executed)} not executed of {len(checks)}"
        )
        artifacts = [
            {
                "name": ASSERTION_RECORDS_FILENAME,
                "content": json.dumps(document, indent=2, sort_keys=True),
                "media_type": "application/json",
                "type": ASSERTION_RECORDS_ARTIFACT_TYPE,
            },
            *(
                {
                    "name": item.name,
                    "content": item.content,
                    "media_type": item.media_type,
                    "type": OPERATION_EVIDENCE_ARTIFACT_TYPE,
                }
                for item in result.evidence
            ),
        ]
        error = "; ".join(f"{row['check']}: {row['reason']}" for row in failed) if failed else None
        return self._finish(
            inputs, started, summary=summary, checks=checks, artifacts=artifacts, error=error
        )

    def _finish(
        self,
        inputs: dict[str, Any],
        started: float,
        *,
        summary: str = "",
        checks: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> HandlerResult:
        outputs: dict[str, Any] = {"summary": summary or f"[qa] {error}", "role": "qa"}
        if checks is not None:
            outputs["validation_result"] = {"checks": checks}
        if error is not None:
            # Deterministic either way: the same operation on the same tree fails the same
            # assertion, and a refused supplier stays refused. So never a blind retry. The
            # executor then repairs an executed failure and ends the run on anything else.
            outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
        if artifacts:
            outputs["artifacts"] = artifacts
        evidence = HandlerEvidence.create(
            handler_name=self.name,
            task_type=self.task_type,
            duration_ms=(time.perf_counter() - started) * 1000,
            inputs_hash=self._hash_dict(
                {k: v for k, v in inputs.items() if not k.endswith("_files")}
            ),
            outputs_hash=self._hash_dict(outputs),
        )
        return HandlerResult(
            success=error is None, outputs=outputs, _evidence=evidence, error=error
        )


def _scenario_errors(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return ["'operation_scenario' is required: the frozen scenario the operation runs"]
    errors = [
        f"'operation_scenario.{key}' is required"
        for key in ("scenario_id", "digest", "named_assertion", "path")
        if not isinstance(value.get(key), str) or not value.get(key)
    ]
    assertions = value.get("assertions")
    if (
        not isinstance(assertions, list | tuple)
        or not assertions
        or any(not isinstance(a, str) or not a for a in assertions)
        or len(set(assertions)) != len(assertions)
    ):
        errors.append(
            "'operation_scenario.assertions' is required: the distinct ids of the assertions "
            "the scenario declares. A scenario that asserts nothing verifies nothing"
        )
    elif isinstance(value.get("named_assertion"), str) and value["named_assertion"] not in (
        assertions
    ):
        errors.append(
            f"'operation_scenario.named_assertion' is {value['named_assertion']!r}, which the "
            "scenario doesn't declare"
        )
    return errors


def _scenario(value: Mapping[str, Any], files: Mapping[str, str]) -> Scenario:
    """The frozen scenario, with its declaration read from the tree at its path. The provider
    digests that text and runs it only when it is the frozen one, so an edit made to the file
    after it was frozen reads not executed there (#3044)."""
    return Scenario(
        scenario_id=value["scenario_id"],
        digest=value["digest"],
        assertions=tuple(value["assertions"]),
        named_assertion=value["named_assertion"],
        document=files[value["path"]],
    )


def _tool_request(catalog: Mapping[str, Skillset], operation: Mapping[str, Any]) -> Any:
    """The one tool the supplying skillset requests for this contract. Raises ``ValueError``
    naming what is wrong: the skillset isn't held, isn't the one the cycle recorded, doesn't
    specialize the contract in this mode, or requests no single tool for it."""
    skillset = catalog.get(operation["skillset"])
    if skillset is None:
        raise ValueError(
            f"skillset `{operation['skillset']}` supplies this task by the cycle's record, and "
            "this deployment doesn't hold it"
        )
    if skillset.digest != operation["skillset_digest"]:
        raise ValueError(
            f"skillset `{skillset.id}` has changed since the cycle was created: the record "
            f"holds digest {operation['skillset_digest']}, and this deployment holds "
            f"{skillset.digest}"
        )
    capability = skillset.capability_for(operation["contract"])
    if capability is None or (
        operation["mode"] and operation["mode"] not in [m.value for m in capability.modes]
    ):
        raise ValueError(
            f"skillset `{skillset.id}` doesn't specialize `{operation['contract']}`"
            + (f" in `{operation['mode']}` mode" if operation["mode"] else "")
        )
    if len(capability.tools) != 1:
        raise ValueError(
            f"skillset `{skillset.id}` requests {len(capability.tools)} tools for "
            f"`{operation['contract']}`; the operation to run is the one it requests"
        )
    return capability.tools[0]


def _check_rows(
    request: RemoteOperationRequest, result: RemoteOperationResult, operation_reason: str
) -> list[dict[str, Any]]:
    """One check row per declared assertion, in SIP-0096's vocabulary."""
    rows: list[dict[str, Any]] = []
    recorded = (
        outcomes_by_assertion(request, result) if result.status is OperationStatus.COMPLETED else {}
    )
    for assertion_id in request.scenario.assertions:
        check_id = assertion_check_id(request.scenario.scenario_id, assertion_id)
        record = recorded.get(assertion_id)
        if record is not None and record.outcome.executed:
            rows.append(
                {
                    "check": check_id,
                    "criterion_id": check_id,
                    "status": (
                        ResultStatus.PASSED
                        if record.outcome is AssertionOutcome.PASSED
                        else ResultStatus.FAILED
                    ),
                    "reason": (
                        ""
                        if record.outcome is AssertionOutcome.PASSED
                        else f"observed {record.observed!r}, expected {record.expected!r}"
                    ),
                }
            )
            continue
        rows.append(
            {
                "check": check_id,
                "criterion_id": check_id,
                "status": ResultStatus.SKIPPED,
                # The assertion's own outcome where the operation ran, and the operation's
                # where it didn't. Either way a criterion the run could not verify: the
                # roll-up reads this pair as required-level unverified (SIP-0096 #423).
                "reason": record.outcome.value if record is not None else operation_reason,
                "evidence_gap": True,
            }
        )
    return rows

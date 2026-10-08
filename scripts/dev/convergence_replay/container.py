"""The convergence replay's container stage (#1764): runs INSIDE a one-off of the qa service.

    docker compose run --rm --no-deps -T \\
        -v <repo>/scripts/dev/convergence_replay:/replay:ro -v <out>:/out \\
        eve python /replay/container.py admit --bundles /out/bundles --out /out/admission.jsonl

The qa image carries every toolchain a round's checks need: pytest, vitest, Node and tsc. A
one-off of the service has the agent's own configuration and network but not its command, so
nothing here consumes from the queue.

**The ports mirror ``AgentRunner._create_ports``**, with four exceptions, each named where it is
built:
- the memory port is a null store, because the one-off shares the qa agent's memory volume;
- the queue refuses every call;
- telemetry is ``null``, and LLM observability is the no-op;
- request templates come from a filesystem source for the arm. The scoped arm reads today's
  templates; the whole-file arm reads a copy with the revision instruction swapped.

``create_system`` is then called unchanged, and every task runs through
``orchestrator.submit_task``, as an agent runs it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from squadops.ports.comms.queue import QueuePort
from squadops.ports.memory.store import MemoryPort

#: The admission verdicts. A round is replayable only when its recorded failure reproduces.
ADMITTED = "admitted"
NOT_REPRODUCED = "not_reproduced"
NO_RECORDED_CHECK = "no_recorded_failed_check"
UNRUNNABLE = "unrunnable"
#: A recorded check the verifier returns no row for: a framework-owed row (a build step's
#: ``acceptance:frontend_compiles``) that the producing handler writes, not a typed criterion.
UNEVALUATED = "recorded_check_not_evaluated_here"


class NullMemory(MemoryPort):
    """Stores nothing and finds nothing: the one-off shares the qa agent's memory volume."""

    async def store(self, entry: Any) -> str:
        return "null"

    async def search(self, query: Any) -> list[Any]:
        return []

    async def get(self, memory_id: str) -> Any:
        return None

    async def delete(self, memory_id: str) -> bool:
        return False


class RefusingQueuePort(QueuePort):
    """Refuses every call: the replay runs tasks in-process, never through the broker."""

    def _refuse(self, name: str) -> RuntimeError:
        return RuntimeError(f"the convergence replay never touches the queue ({name})")

    async def publish(self, *args: Any, **kwargs: Any) -> None:
        raise self._refuse("publish")

    async def consume(self, queue_name: str, max_messages: int = 1) -> list[Any]:
        raise self._refuse("consume")

    async def ack(self, message: Any) -> None:
        raise self._refuse("ack")

    async def retry(self, message: Any, delay_seconds: int) -> None:
        raise self._refuse("retry")

    async def health(self) -> dict[str, Any]:
        return {"healthy": False, "reason": "the convergence replay has no queue"}

    def capabilities(self) -> dict[str, bool]:
        return {}


async def compose_system(
    role: str, *, model: str, templates_dir: Path | None = None, llm: Any = None
) -> Any:
    """The agent's system for ``role``, composed as ``AgentRunner._create_ports`` composes it."""
    from adapters.llm.factory import create_llm_provider
    from adapters.prompts import create_prompt_repository
    from adapters.prompts.factory import create_prompt_asset_source
    from adapters.telemetry.factory import create_telemetry_provider
    from adapters.tools.factory import create_filesystem_provider
    from squadops.bootstrap import SystemConfig, create_system
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.config import load_config
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer
    from squadops.telemetry.noop import NoOpLLMObservabilityAdapter

    config = load_config(secret_provider_factory=secret_provider_for)
    llm = llm or create_llm_provider(
        provider=config.llm.provider,
        base_url=config.llm.url,
        default_model=model,
        timeout_seconds=config.llm.timeout,
        api_key=config.llm.api_key,
    )
    asset_source = create_prompt_asset_source(
        provider="filesystem", **({"templates_path": templates_dir} if templates_dir else {})
    )
    metrics, events = create_telemetry_provider("null")
    return create_system(
        llm=llm,
        memory=NullMemory(),
        prompt_service=PromptAssembler(create_prompt_repository("filesystem")),
        queue=RefusingQueuePort(),
        metrics=metrics,
        events=events,
        filesystem=create_filesystem_provider(
            provider=config.tools.filesystem.provider, allowed_roots=None, production_mode=False
        ),
        llm_observability=NoOpLLMObservabilityAdapter(),
        request_renderer=RequestTemplateRenderer(asset_source),
        messaging=None,
        config=SystemConfig(role=role, roles=[role]),
    )


def retest_envelope(bundle: dict[str, Any], files: list[dict[str, str]]) -> Any:
    """The execute-only retest, built as ``CorrectionRunner.reexecute_repaired_suite`` builds it:
    the failed task's own type, ``retest_files`` set, no generation."""
    from squadops.capabilities.context_assembly import retest_forwarded_inputs
    from squadops.tasks.models import TaskEnvelope

    failed = TaskEnvelope.from_dict(bundle["envelope"])
    qa = bundle["agents"]["qa"]
    inputs = {
        "prd": bundle["prd"],
        "retest_files": [
            {"filename": f["name"], "content": f["content"]} for f in workspace_files(files)
        ],
        "agent_model": qa["model"],
        "agent_config_overrides": qa["config_overrides"],
        **retest_forwarded_inputs(failed.inputs or {}),
    }
    return TaskEnvelope(
        task_id=f"retest-replay-{uuid4().hex[:12]}-{failed.task_type}",
        agent_id=qa["agent_id"],
        cycle_id=failed.cycle_id,
        pulse_id=uuid4().hex,
        project_id=failed.project_id,
        task_type=failed.task_type,
        correlation_id=uuid4().hex,
        causation_id=failed.task_id,
        trace_id=uuid4().hex,
        span_id=uuid4().hex,
        inputs=inputs,
        metadata={"role": "qa", "retest": True},
    )


def workspace_files(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The artifacts that belong in a tree: the product's own exclusion, by type, of the records a
    task writes beside its files (``CorrectionRunner._NON_WORKSPACE_ARTIFACT_TYPES``)."""
    from adapters.cycles.correction_runner import CorrectionRunner

    return [
        a
        for a in artifacts
        if isinstance(a, dict)
        and a.get("type") not in CorrectionRunner._NON_WORKSPACE_ARTIFACT_TYPES
    ]


def _tests_pass_row(result: Any) -> dict[str, Any]:
    rows = ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
    row = next((r for r in rows if isinstance(r, dict) and r.get("check") == "tests_pass"), {})
    return {k: row.get(k) for k in ("passed", "executed", "failing_tests")}


def failed_checks_of(result: Any) -> set[str]:
    rows = ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
    return {r.get("check") for r in rows if isinstance(r, dict) and r.get("passed") is False}


async def admit(bundle: dict[str, Any], system: Any) -> dict[str, Any]:
    """Whether the round's recorded failed checks reproduce on its rebuilt tree."""
    from squadops.cycles.acceptance_evaluation import resolve_check_stack
    from squadops.cycles.patch_verification import verify_patched_artifacts

    recorded = set(bundle["round"]["failure"]["failed_checks"])
    if not recorded:
        return {"verdict": NO_RECORDED_CHECK, "recorded": []}
    inputs = bundle["envelope"]["inputs"]
    reproduced: set[str] = set()
    retest_evidence: dict[str, Any] | None = None
    typed_rows: list[dict[str, Any]] | None = None
    if "tests_pass" in recorded:
        result = await system.orchestrator.submit_task(
            retest_envelope(bundle, bundle["failed_artifacts"]), timeout_seconds=900
        )
        reproduced |= failed_checks_of(result) & {"tests_pass"}
        retest_row = next(
            (
                r
                for r in ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
                if isinstance(r, dict) and r.get("check") == "tests_pass"
            ),
            {},
        )
        # A suite that did not execute is not a reproduction of one that failed. (A failing
        # suite's result also carries an error, "Repaired suite still fails" — that is the
        # failure reproducing, not a reason to discard it.)
        if retest_row.get("executed") is not True:
            reproduced.discard("tests_pass")
        retest_evidence = {
            "status": str(result.status),
            "error": (result.error or "")[:200],
            "row": {
                k: retest_row.get(k) for k in ("passed", "executed", "reason", "failing_tests")
            },
        }
    typed = recorded - {"tests_pass"}
    if typed:
        verification = await verify_patched_artifacts(
            inputs.get("acceptance_criteria") or [],
            [{"name": f["name"], "content": f["content"]} for f in bundle["failed_artifacts"]],
            workspace_files=inputs.get("acceptance_workspace_files") or {},
            stack=resolve_check_stack(bundle["resolved_config"]),
        )
        reproduced |= {c.check for c in verification.checks if c.status == "failed"} & typed
        typed_rows = [
            {"check": c.check, "status": c.status, "reason": (c.reason or "")[:160]}
            for c in verification.checks
            if c.check in typed
        ]
    evaluated = {r["check"] for r in typed_rows or []} | ({"tests_pass"} & recorded)
    if recorded - evaluated:
        verdict = UNEVALUATED
    else:
        verdict = ADMITTED if reproduced == recorded else NOT_REPRODUCED
    return {
        "verdict": verdict,
        "recorded": sorted(recorded),
        "reproduced": sorted(reproduced),
        "retest": retest_evidence,
        "typed_rows": typed_rows,
    }


def without_faults(value: Any) -> Any:
    """``value`` with every fault declaration removed, at any depth (#1764).

    A round from a diagnostic cycle carries that cycle's declared faults: in its resolved config,
    in the cycle's ``applied_defaults`` and ``execution_overrides``, and in the envelope's own
    ``inputs``. Rebuilt as-is, the faults fire **inside the replay**. The first live sample showed
    it: `repair_prose_only` replaced the model's repair with 48 characters of planted prose, so the
    sample measured the fault, not the arm. The planted defect in the failing tree stays; it is
    what the repair must fix. Only the declaration that would fire again is removed. Only dict
    keys are touched, never file content that happens to mention one.
    """
    from squadops.capabilities.handlers.fault_injection import DECLARATION_KEY

    if isinstance(value, dict):
        return {k: without_faults(v) for k, v in value.items() if k != DECLARATION_KEY}
    if isinstance(value, list):
        return [without_faults(v) for v in value]
    return value


def load_bundle(path: Path) -> dict[str, Any]:
    """A bundle as every stage of the replay must see it: with no fault left to fire."""
    return without_faults(json.loads(path.read_text()))


async def _admit_all(bundles: Path, out: Path) -> dict[str, int]:
    rows, tally = [], {}
    systems: dict[str, Any] = {}
    for path in sorted(bundles.glob("*.json")):
        bundle = load_bundle(path)
        model = bundle["agents"]["qa"]["model"]
        system = systems.get(model) or await compose_system("qa", model=model)
        systems[model] = system
        try:
            reading = await admit(bundle, system)
        except Exception as exc:  # noqa: BLE001 - a round that cannot run is counted, not fatal
            reading = {"verdict": UNRUNNABLE, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        reading["bundle"] = path.name
        rows.append(reading)
        tally[reading["verdict"]] = tally.get(reading["verdict"], 0) + 1
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tally


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("admit", help="reproduce each bundle's recorded failure on its tree")
    a.add_argument("--bundles", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("replay", help="repair each admitted round, per arm, and judge it")
    r.add_argument("--bundles", type=Path, required=True)
    r.add_argument("--admission", type=Path, required=True)
    r.add_argument("--arm", choices=(SCOPED, WHOLE_FILE), required=True)
    r.add_argument("--samples", type=int, default=3)
    r.add_argument("--out", type=Path, required=True, help="JSON lines, appended")
    r.add_argument("--stub-llm", action="store_true", help="plumbing test: no model call")
    r.add_argument("--only", nargs="*", help="bundle file names to replay (the registered sample)")
    args = ap.parse_args(argv)
    if args.command == "replay":
        tally = asyncio.run(
            _replay_all(
                args.bundles,
                args.admission,
                args.arm,
                args.samples,
                args.out,
                args.stub_llm,
                set(args.only) if args.only else None,
            )
        )
    else:
        tally = asyncio.run(_admit_all(args.bundles, args.out))
    print(json.dumps(tally, indent=2))
    return 0


# ---------------------------------------------------------------------------------------------
# The replay: each admitted round repaired through the product's own CorrectionRepair, per arm
# ---------------------------------------------------------------------------------------------

SCOPED = "scoped"
WHOLE_FILE = "whole_file"


def cycle_from_dict(d: dict[str, Any]) -> Any:
    """A Cycle from ``dataclasses.asdict``, rebuilt as the Postgres registry rebuilds one."""
    from datetime import datetime

    from squadops.cycles.models import Cycle, Gate, TaskFlowPolicy

    tfp = d["task_flow_policy"]
    fields = dict(d)
    fields["task_flow_policy"] = TaskFlowPolicy(
        mode=tfp["mode"],
        gates=tuple(
            Gate(
                name=g["name"],
                description=g["description"],
                after_task_types=tuple(g["after_task_types"]),
            )
            for g in tfp.get("gates", ())
        ),
    )
    fields["expected_artifact_types"] = tuple(d.get("expected_artifact_types") or ())
    if isinstance(fields.get("created_at"), str):
        fields["created_at"] = datetime.fromisoformat(fields["created_at"])
    return Cycle(**fields)


def profile_from_dict(d: dict[str, Any]) -> Any:
    from datetime import datetime

    from squadops.cycles.models import AgentProfileEntry, SquadProfile

    fields = dict(d)
    fields["agents"] = tuple(
        AgentProfileEntry(**{**a, "serves_roles": tuple(a.get("serves_roles") or ())})
        for a in d["agents"]
    )
    if isinstance(fields.get("created_at"), str):
        fields["created_at"] = datetime.fromisoformat(fields["created_at"])
    return SquadProfile(**fields)


def use_arm(arm: str) -> None:
    """The whole-file arm is the product's own non-anchorable branch (#1764 build notes): with
    no file offered the edit form, the repair is asked "exactly as before" 1.8 — the output
    section, the closing line and the absent edit-form appendix all follow the one decision."""
    if arm == WHOLE_FILE:
        from squadops.capabilities.handlers.impl import repair_handlers

        repair_handlers._RepairPromptMixin._anchorable_files = lambda self, inputs: []


def failed_result(bundle: dict[str, Any], retest: Any) -> Any:
    """The failed task's result: the retest's fresh execution on the failed tree, carrying the
    failed task's own files as its artifacts."""
    from squadops.tasks.models import TaskResult

    return TaskResult(
        task_id=bundle["envelope"]["task_id"],
        status="FAILED",
        outputs={
            **(retest.outputs or {}),
            "artifacts": [
                {"name": f["name"], "content": f["content"], "type": f.get("type") or "source"}
                for f in bundle["failed_artifacts"]
            ],
        },
        error=retest.error,
    )


def _changed_lines(before: str, after: str) -> int:
    import difflib

    return sum(
        1
        for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )


def response_measures(
    bundle: dict[str, Any], artifacts: list[dict[str, Any]], *, asked: set[str]
) -> dict[str, Any]:
    """Emitted size against actual change, per file the repair was asked to revise (the 1.8.1
    pair-5 lesson: a span reported as 95% of a file for a 12-line diff). Only the repair step's
    ``expected_artifacts`` count: the reports and evaluation records a handler writes on its own
    are not the model's revision."""
    from squadops.cycles.write_authorization import normalize_ws_path

    asked = {normalize_ws_path(str(p)) for p in asked}
    # The failed tree: the workspace with the failed task's own files over it (#1264), the
    # tree the repair patches and the verifier materializes.
    base = dict(bundle["envelope"]["inputs"].get("acceptance_workspace_files") or {})
    base.update({f["name"]: f["content"] for f in bundle["failed_artifacts"]})
    files = []
    for art in workspace_files(artifacts):
        name, content = art.get("name"), art.get("content") or ""
        if not isinstance(name, str) or normalize_ws_path(name) not in asked:
            continue
        before = base.get(name, "")
        files.append(
            {
                "file": name,
                "emitted_chars": len(content),
                "file_lines": len(before.splitlines()) or len(content.splitlines()),
                "changed_lines": _changed_lines(before, content),
                "new_file": name not in base,
            }
        )
    return {
        "files": files,
        "emitted_chars": sum(f["emitted_chars"] for f in files),
        "changed_lines": sum(f["changed_lines"] for f in files),
        "empty": not files,
    }


#: Each response is kept whole up to this many characters: enough to tell an abstention, a
#: prose-only answer and an edit that failed to parse apart, which ``emitted 0`` cannot (#1788).
RAW_RESPONSE_LIMIT = 6000


class RecordingLLM:
    """The adapter with every generation it makes kept, in order, until drained (#1788).

    The replay's per-file measures read only what a repair's artifacts became, so a response
    that yielded no file read ``emitted 0`` whatever it said. This keeps what the model sent.
    A call that raises is kept as its error, then re-raised unchanged.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._calls: list[Any] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def chat_stream_with_usage(self, messages: Any, **kwargs: Any) -> Any:
        try:
            reply = await self._inner.chat_stream_with_usage(messages, **kwargs)
        except Exception as exc:
            self._calls.append(exc)
            raise
        self._calls.append(reply)
        return reply

    def drain(self) -> list[Any]:
        """Every generation since the last drain, and forget them."""
        calls, self._calls = self._calls, []
        return calls


def response_reading(call: Any) -> dict[str, Any]:
    """One generation as the replay keeps it: the text (bounded), what its fences parsed to,
    and the call's token usage — the evidence a live cycle's emission-shape line gives."""
    from squadops.capabilities.anchored_edits import parse_anchored_edits, strip_edit_blocks
    from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

    if isinstance(call, BaseException):
        return {"error": f"{type(call).__name__}: {str(call)[:300]}"}
    text = call.content or ""
    parse = parse_anchored_edits(text)
    body = strip_edit_blocks(text) if parse.found else text
    return {
        "chars": len(text),
        "text": text[:RAW_RESPONSE_LIMIT],
        "truncated": len(text) > RAW_RESPONSE_LIMIT,
        "reasoning_chars": len(call.reasoning_text or ""),
        "prompt_tokens": call.prompt_tokens,
        "completion_tokens": call.completion_tokens,
        "reasoning_tokens": call.reasoning_tokens,
        "edit_fences_found": parse.found,
        "edits_parsed": len(parse.edits),
        "edits_malformed": [{"path": m.path, "reason": m.reason} for m in parse.malformed],
        "whole_files": [f["filename"] for f in extract_fenced_files(body)],
    }


def step_record(
    role: str, step_envelope: Any, step: Any, offered: Any, calls: list[Any]
) -> dict[str, Any]:
    """One repair step of a sample: what it was offered and asked, each generation it made, and
    the transaction its handler recorded (accepted, or every refusal)."""
    outputs = step.outputs or {}
    return {
        "role": role,
        "task_type": step_envelope.task_type,
        "edit_form_offered": offered,
        "expected": list((step_envelope.inputs or {}).get("expected_artifacts") or []),
        "usage": outputs.get("llm_usage"),
        "responses": [response_reading(c) for c in calls],
        "anchored_edits": outputs.get("anchored_edits"),
    }


async def compose_recorded_systems(
    bundle: dict[str, Any], *, stub: bool
) -> tuple[dict[str, Any], StubLLM | None]:
    """Each role's system with its generations recorded; under ``stub`` one canned adapter
    answers for every role, beneath each role's own recorder."""
    systems: dict[str, Any] = {}
    stub_llm = None
    for role, agent in bundle["agents"].items():
        llm = (await compose_system(role, model=agent["model"])).ports.llm
        if stub:
            stub_llm = stub_llm or StubLLM(llm)
            llm = stub_llm
        systems[role] = await compose_system(role, model=agent["model"], llm=RecordingLLM(llm))
    return systems, stub_llm


async def replay_sample(
    bundle: dict[str, Any], systems: dict[str, Any], retest: Any
) -> dict[str, Any]:
    """One repair of one admitted round, and its judgement by the deployed PatchAcceptance."""
    import time
    from uuid import uuid4

    from adapters.cycles.correction_repair import CorrectionRepair
    from adapters.cycles.correction_runner import _Diagnosis, _inject_deterministic_evidence
    from adapters.cycles.patch_acceptance import PatchAcceptance
    from adapters.noop.ports import NoOpFailurePatternRecall
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.cycles.failure_evidence import build_failure_evidence
    from squadops.tasks.models import TaskEnvelope

    envelope = TaskEnvelope.from_dict(bundle["envelope"])
    cycle = cycle_from_dict(bundle["cycle"])
    profile = profile_from_dict(bundle["profile"])
    manifest = (
        InterfaceManifest.from_yaml(bundle["interface_manifest_yaml"])
        if bundle.get("interface_manifest_yaml")
        else None
    )
    result = failed_result(bundle, retest)
    inputs = envelope.inputs or {}
    evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=0)
    _inject_deterministic_evidence(
        evidence,
        envelope=envelope,
        interface_manifest=manifest,
        artifact_contents=inputs.get("artifact_contents"),
        scaffold_enforcement_carry=None,
    )
    diagnosis = _Diagnosis(
        failure_evidence=evidence,
        analysis_outputs=bundle["analysis"],
        decision_outputs=bundle["decision"],
        correlation_id=uuid4().hex,
    )
    usage: list[dict[str, Any]] = []
    retests: list[dict[str, Any]] = []

    async def dispatch_step(
        step_envelope: Any, run_id: str, cycle: Any, flow_run_id: Any, **_: Any
    ) -> Any:
        from squadops.capabilities.handlers.impl import repair_handlers

        role = (step_envelope.metadata or {}).get("role") or "qa"
        # What the arm offered this repair: the files it may revise by anchored edit. Read
        # through the handler's own decision (after the arm's override), not inferred.
        probe = type("_Probe", (repair_handlers._RepairPromptMixin,), {})()
        offered = probe._anchorable_files(step_envelope.inputs or {})
        recorder = systems[role].ports.llm
        recorder.drain()  # only this step's generations are its responses
        step = await systems[role].orchestrator.submit_task(step_envelope, timeout_seconds=1800)
        usage.append(step_record(role, step_envelope, step, offered, recorder.drain()))
        return step

    async def reexecute_repaired_suite(
        run_id: str,
        cycle: Any,
        env: Any,
        patched_artifacts: list[dict[str, Any]],
        *a: Any,
        **k: Any,
    ) -> Any:
        after = await systems["qa"].orchestrator.submit_task(
            retest_envelope(bundle, [a_ for a_ in patched_artifacts if isinstance(a_, dict)]),
            timeout_seconds=900,
        )
        retests.append(_tests_pass_row(after))
        return after

    started = time.perf_counter()
    # Memory disabled (SIP-0110 §0.7): the repair's prompt renders as it did before memory existed,
    # which is what a replay of a pre-memory round compares.
    outcome = await CorrectionRepair(
        dispatch_step=dispatch_step, failure_recall=NoOpFailurePatternRecall()
    ).dispatch(
        "patch",
        diagnosis,
        envelope,
        result,
        cycle,
        bundle["round"]["run_id"],
        0,
        prior_outputs=inputs.get("prior_outputs") or {},
        all_artifact_refs=list(inputs.get("artifact_refs") or []),
        stored_artifacts=[],
        completed_task_ids=[],
        plan_delta_refs=[],
        profile=profile,
        flow_run_id=None,
        interface_manifest=manifest,
        scaffold_enforcement_carry=None,
        budget_guard=None,
        bound_record=None,
    )
    repair_seconds = time.perf_counter() - started
    verdict = await PatchAcceptance(
        reexecute_repaired_suite=reexecute_repaired_suite,
        # No bound scaffold record is rebuilt (#1764 build notes): frozen ownership passes
        # through, identically for both arms, and so does the evidence it would emit.
        enforce_frozen_ownership=lambda artifacts, *a, **k: (artifacts, []),
        emit_integrity_evidence=lambda *a, **k: None,
        enforce_compliance_budget=lambda *a, **k: None,
    ).accept(
        envelope,
        result,
        outcome.artifacts,
        {},
        run_id=bundle["round"]["run_id"],
        cycle=cycle,
        prior_outputs=inputs.get("prior_outputs") or {},
        all_artifact_refs=list(inputs.get("artifact_refs") or []),
        stored_artifacts=[],
        completed_task_ids=[],
        plan_delta_refs=[],
        profile=profile,
        enriched_envelope=envelope,
        interface_manifest=manifest,
        repair_typed_checks=outcome.typed_checks,
    )
    return {
        "verdict": verdict,
        "accepted": verdict == "accept_patch",
        # Before the repair (the failed tree's retest) and after it (each retest the judge ran):
        # a test failing after that was not failing before is a regression.
        "failing_before": sorted(_tests_pass_row(retest).get("failing_tests") or []),
        "retests_after": retests,
        "regressions": sorted(
            set().union(*[set(r.get("failing_tests") or []) for r in retests])
            - set(_tests_pass_row(retest).get("failing_tests") or [])
        )
        if retests
        else [],
        "repair_seconds": round(repair_seconds, 1),
        "total_seconds": round(time.perf_counter() - started, 1),
        "steps_ran": outcome.steps_ran,
        "empty_signatures": outcome.empty_signatures,
        "anchored_edits_refused": outcome.anchored_edits_refused,
        "usage": usage,
        **response_measures(
            bundle,
            outcome.artifacts,
            asked={path for u in usage for path in u.get("expected") or []},
        ),
    }


class StubLLM:
    """The real adapter with its generation replaced by a canned answer: the plumbing test runs
    every seam, the repair's parse included, without a GPU call while the set holds the box."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.canned = ""

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    async def chat_stream_with_usage(self, messages: Any, **kwargs: Any) -> Any:
        from squadops.llm.models import ChatMessage

        return ChatMessage(
            role="assistant", content=self.canned, prompt_tokens=1, completion_tokens=1
        )


def _canned_unchanged(bundle: dict[str, Any]) -> str:
    """A repair that re-emits the failed suite unchanged: the retest must fail and the patch
    must be refused, which is the plumbing test's expected verdict."""
    return "\n\n".join(
        f"```text:{f['name']}\n{f['content']}\n```" for f in bundle["failed_artifacts"]
    )


async def _replay_all(
    bundles: Path,
    admission: Path,
    arm: str,
    samples: int,
    out: Path,
    stub: bool,
    only: set[str] | None = None,
) -> dict[str, int]:
    use_arm(arm)
    admitted = {
        json.loads(line)["bundle"]
        for line in admission.read_text().splitlines()
        if json.loads(line)["verdict"] == ADMITTED
    }
    tally: dict[str, int] = {}
    with out.open("a") as sink:
        for path in sorted(bundles.glob("*.json")):
            if path.name not in admitted or (only and path.name not in only):
                continue
            bundle = load_bundle(path)
            systems, stub_llm = await compose_recorded_systems(bundle, stub=stub)
            if stub_llm is not None:
                stub_llm.canned = _canned_unchanged(bundle)
            retest = await systems["qa"].orchestrator.submit_task(
                retest_envelope(bundle, bundle["failed_artifacts"]), timeout_seconds=900
            )
            for sample in range(samples):
                try:
                    row = await replay_sample(bundle, systems, retest)
                except Exception as exc:  # noqa: BLE001 - a sample that cannot run is counted
                    row = {
                        "verdict": UNRUNNABLE,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                row.update({"bundle": path.name, "arm": arm, "sample": sample, "stub": stub})
                sink.write(json.dumps(row, default=str) + "\n")
                sink.flush()
                tally[str(row["verdict"])[:60]] = tally.get(str(row["verdict"])[:60], 0) + 1
    return tally


if __name__ == "__main__":
    sys.exit(main())

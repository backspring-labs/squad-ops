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


async def compose_system(role: str, *, model: str, templates_dir: Path | None = None) -> Any:
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
    llm = create_llm_provider(
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
        "retest_files": [{"filename": f["name"], "content": f["content"]} for f in files],
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


async def _admit_all(bundles: Path, out: Path) -> dict[str, int]:
    rows, tally = [], {}
    systems: dict[str, Any] = {}
    for path in sorted(bundles.glob("*.json")):
        bundle = json.loads(path.read_text())
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
    args = ap.parse_args(argv)
    print(json.dumps(asyncio.run(_admit_all(args.bundles, args.out)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

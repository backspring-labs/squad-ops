"""The convergence replay's bundles: one stored failing round, rebuilt by the product's own code (#1764).

No repair envelope is stored anywhere (``agent_task_log`` holds no inputs), so a round's inputs
are rebuilt the way the executor built them:
- **Loading.** The executor's own loaders read the plan, the verification contract and the
  interface manifest (``_load_plan_for_run``, ``_load_contract_for_run``,
  ``_load_interface_manifest_for_run``, the readers ``RunProvisioning`` borrows).
- **The envelope.** ``generate_task_plan`` regenerates it. Task ids are deterministic, so the
  failed task's id finds its envelope, and a failed task whose id the plan does not regenerate is
  refused.
- **Enrichment.** ``_enrich_envelope`` enriches it from the checkpoint written before the round:
  the same composition point the dispatch used, with the same tree (``acceptance_workspace_files``).
- **Emitted files.** The failed task's emitted files come from the vault, under its task id.

The executor is built over the read-only registry and vault, with a queue that refuses every
send, so nothing here can dispatch or write. A bundle is plain JSON, and the container stage
reads it without a database.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from typing import Any


class RefusingQueue:
    """A queue port that refuses: a bundle is built, never dispatched."""

    def __getattr__(self, name: str) -> Any:
        async def _refuse(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(
                f"the convergence replay's bundle stage never touches the queue ({name})"
            )

        return _refuse


@dataclass(frozen=True)
class Bundle:
    round: dict[str, Any]
    prd: str
    agents: dict[str, dict[str, Any]]
    resolved_config: dict[str, Any]
    envelope: dict[str, Any]
    failed_artifacts: list[dict[str, str]]
    analysis: dict[str, Any]
    decision: dict[str, Any]
    profile_snapshot_matches: bool
    notes: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "round": self.round,
                "prd": self.prd,
                "agents": self.agents,
                "resolved_config": self.resolved_config,
                "envelope": self.envelope,
                "failed_artifacts": self.failed_artifacts,
                "analysis": self.analysis,
                "decision": self.decision,
                "profile_snapshot_matches": self.profile_snapshot_matches,
                "notes": list(self.notes),
            },
            default=str,
        )


def find_envelope(envelopes: list[Any], task_id: str) -> Any | None:
    """The regenerated envelope whose id is the failed task's, or None."""
    return next((e for e in envelopes if e.task_id == task_id), None)


async def build_bundle(
    row: dict[str, Any], *, executor: Any, registry: Any, vault: Any, profiles: Any
) -> Bundle | str:
    """A round's bundle, or the reason it cannot be rebuilt."""
    from squadops.cycles.task_plan import generate_task_plan

    cycle = await registry.get_cycle(row["cycle_id"])
    run = await registry.get_run(row["run_id"])
    # SIP-0083: an implementation run sees its framing run's forwarding (the plan's refs among
    # them) merged into the cycle, as _prepare_cycle_for_run merges it. Rebuilt from durable state
    # by the executor's own reader for a mid-sequence entry (#434); the merge is the same.
    start_index = await executor._starting_workload_index(cycle.cycle_id, run.run_id)
    if start_index > 0:
        forwarding = await executor._rebuild_forwarding_overrides_on_entry(
            cycle, cycle.cycle_id, start_index
        )
        if forwarding:
            cycle = dataclasses.replace(
                cycle, execution_overrides={**cycle.execution_overrides, **forwarding}
            )
    # The PRD text, resolved as _prepare_cycle_for_run resolves it (that method also writes a run
    # root, which this stage must not): an artifact id is read from the vault, else the project's
    # PRD file, and the cycle carries the text from here on.
    prd = cycle.prd_ref
    if prd and prd.startswith("art_"):
        prd = (await vault.retrieve(prd))[1].decode("utf-8", errors="replace")
    if not prd:
        prd = await executor._resolve_prd_from_project(cycle.project_id)
    if prd and prd != cycle.prd_ref:
        cycle = dataclasses.replace(cycle, prd_ref=prd)
    profile, snapshot = await profiles.resolve_snapshot(cycle.squad_profile_id)
    plan = await executor._load_plan_for_run(cycle, run)
    contract = await executor._load_contract_for_run(cycle, run)
    manifest = await executor._load_interface_manifest_for_run(cycle, run)
    envelopes = generate_task_plan(
        cycle, run, profile, plan=plan, contract=contract, interface_manifest=manifest
    )
    failed = find_envelope(envelopes, row["failure"]["task_id"])
    if failed is None:
        return "the plan does not regenerate the failed task's id"
    checkpoints = {c.checkpoint_index: c for c in await registry.list_checkpoints(run.run_id)}
    checkpoint = checkpoints.get(row["checkpoint_index"])
    if checkpoint is None:
        return "the checkpoint before the round is gone"
    stored = [(aid, await vault.get_metadata(aid)) for aid in checkpoint.artifact_refs]
    enriched = await executor._enrich_envelope(
        failed,
        dict(checkpoint.prior_outputs),
        list(checkpoint.artifact_refs),
        stored,
        interface_manifest=manifest,
    )
    failed_artifacts = []
    for aid in row["failed_artifact_ids"]:
        ref, content = await vault.retrieve(aid)
        failed_artifacts.append(
            {"name": ref.filename, "content": content.decode("utf-8", "replace")}
        )
    analysis = json.loads((await vault.retrieve(row["analysis_id"]))[1])
    decision = json.loads((await vault.retrieve(row["decision_id"]))[1])
    notes = (
        ()
        if snapshot == cycle.squad_profile_snapshot_ref
        else (
            f"squad profile {cycle.squad_profile_id} moved since the round: {cycle.squad_profile_snapshot_ref[:16]} → {snapshot[:16]}",
        )
    )
    from squadops.cycles.agent_config import resolve_agent_config

    agents = {}
    for role in ("lead", "dev", "qa", "builder", "data", "strat"):
        try:
            resolved = resolve_agent_config(role, profile)
        except Exception:  # noqa: BLE001 - a role the profile does not serve
            continue
        agents[role] = {
            "agent_id": resolved.agent_id,
            "model": resolved.model,
            "config_overrides": dict(resolved.config_overrides or {}),
        }
    return Bundle(
        round=row,
        prd=prd or "",
        agents=agents,
        resolved_config=cycle.resolved_config(),
        envelope=enriched.to_dict(),
        failed_artifacts=failed_artifacts,
        analysis=analysis,
        decision=decision,
        profile_snapshot_matches=snapshot == cycle.squad_profile_snapshot_ref,
        notes=notes,
    )

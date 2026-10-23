"""The proposal task's outcome evidence, composed into its inputs with the run's plan, before the first
dispatch (SIP-0113 §4.5; §10t ruling 1).

A campaign's increment proposal is shown each goal of the pinned suite with its result on the
accepted tree, so it can choose the gap to close. Only that one task is shown it. A cycle's resolved
config reaches every task's envelope, the cycle registry, the API, ``bound_launch``'s retries and
repairs, and the campaign's records a cut attaches to the public Release, so the evidence never
enters it. It is asked of ``ProposalEvidencePort`` when the run's plan is composed
(``RunProvisioning.prepare``) and put on the inputs of each task ``shown_outcome_evidence`` names.
The executor never imports the store the evidence is read from.

**A proposal outside a campaign gets none:** the reference's proposal half (§11a) has no pinned
suite and no evaluated tree, so the port isn't asked. **Nothing to show adds no key,** so the task's
inputs are the ones it had before §4.5. **A failed read raises** (§10t ruling 6): the proposal run
fails, and the campaign proposes again as after any failed proposal run.
"""

from __future__ import annotations

import dataclasses

from squadops.campaigns.increment_tree import accepted_cycle_of
from squadops.cycles.models import Cycle
from squadops.execution.execution_errors import _ExecutionError
from squadops.outcomes.proposal_evidence import PROPOSAL_EVIDENCE_INPUT
from squadops.ports.outcomes import ProposalEvidencePort
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import shown_outcome_evidence


async def with_proposal_evidence(
    port: ProposalEvidencePort, envelopes: list[TaskEnvelope], *, cycle: Cycle
) -> list[TaskEnvelope]:
    """``envelopes`` with the evidence on each task shown it, read once for the run."""
    shown = [i for i, e in enumerate(envelopes) if shown_outcome_evidence(e.task_type)]
    if not shown or cycle.campaign_id is None:
        return envelopes
    accepted = accepted_cycle_of(cycle)
    if accepted is None:
        raise _ExecutionError(
            f"campaign {cycle.campaign_id}'s proposal cycle {cycle.cycle_id} names no accepted "
            "cycle, so there is no tree to show the proposal's evidence of"
        )
    evidence = await port.for_proposal(campaign_id=cycle.campaign_id, accepted_cycle_id=accepted)
    if evidence.is_empty():
        return envelopes
    composed = list(envelopes)
    for i in shown:
        inputs = {**envelopes[i].inputs, PROPOSAL_EVIDENCE_INPUT: evidence.to_inputs()}
        composed[i] = dataclasses.replace(envelopes[i], inputs=inputs)
    return composed

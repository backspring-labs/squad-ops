"""The proposal run's one task: the strategy role proposes the next increment (SIP-0109 §9.1; #1706).

``strategy.propose_increment`` is the only task that authors a change request (§3: only the
strategy role proposes). It is shown the accepted manifest verbatim, the objective and its
allowed scope, and the criteria earlier increments froze; it emits ``change_request.yaml``; and
the rails (``squadops.campaigns.change_request.validate_proposal``) judge it inside the task. A
refusal returns every reason to the model for a revision, up to ``proposal_max_attempts``. A
proposal still refused after them fails the task, and the run's ordinary retry follows (§9.1:
then ``proposal_failed``). A refused proposal is never trimmed into an accepted one.

The proposal's context is persisted as the run's inputs (§9.1): the cycle's configuration
carries a ``campaign_proposal`` block holding the accepted manifest's text, with its artifact id
as provenance. The agent's container has no artifact vault — the first live proposal run
(``cyc_a06843b58e4f``, 2026-10-02) refused for exactly that — and the runtime resolves only a
run's own artifacts into task inputs, so the inputs carry the manifest itself.
"""

from __future__ import annotations

import logging
import time
from functools import partial
from typing import TYPE_CHECKING, Any

import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    ProposalVerdict,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.prior_cycle import brief_lines
from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler
from squadops.capabilities.scaffold import frozen_conventions_for
from squadops.tasks.task_types import TaskType

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)

CHANGE_REQUEST_FILENAME = "change_request.yaml"
CHANGE_REQUEST_ARTIFACT_TYPE = "change_request"

#: The authoring stages' shared default: the manifest author spends the same two attempts when a
#: profile configures neither.
_PROPOSAL_MAX_ATTEMPTS_DEFAULT = 2


class ProposalContextMissing(ValueError):
    """The cycle's configuration does not carry the campaign's proposal context."""


def proposal_context_from(resolved_config: dict, baseline_manifest: str) -> ProposalContext:
    """The rails' context from the cycle's ``campaign_proposal`` block and the fetched manifest."""
    block = resolved_config.get("campaign_proposal")
    if not isinstance(block, dict):
        raise ProposalContextMissing(
            "the cycle carries no campaign_proposal block: a proposal run is launched by a "
            "campaign, which names the accepted tree and the objective it proposes against"
        )
    if not baseline_manifest.strip():
        raise ProposalContextMissing(
            "campaign_proposal carries no baseline_manifest: the accepted manifest is the run's "
            "input (§9.1), persisted with it, not fetched"
        )
    try:
        objective = block["objective"]
        return ProposalContext(
            proposal_id=str(block["proposal_id"]),
            version=int(block["version"]),
            baseline_tree=str(block["baseline_tree"]),
            baseline_manifest=baseline_manifest,
            expected_stack=str(resolved_config.get("build_profile") or ""),
            allowed_scope=tuple(str(s) for s in objective["allowed_scope"]),
            prior_criteria=tuple(str(c) for c in block.get("prior_criteria") or ()),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ProposalContextMissing(f"campaign_proposal is incomplete: {e!r}") from e


async def _context_sections(
    renderer: Any, inputs: dict[str, Any], block: dict[str, Any], proposal_context: ProposalContext
) -> dict[str, str]:
    """The proposal request's optional sections, each rendered through its own managed asset
    (#448), keyed by the request template's variable. Absent context renders no section."""
    out: dict[str, str] = {}
    conventions = frozen_conventions_for(proposal_context.expected_stack)
    if conventions:
        # #1962: what the stack's frozen bytes decide. Shakeout 9's first proposal asserted
        # an optional field absent against a frozen null (#1948), and the 2.0 set's asserted
        # name trimming the frozen request models already did; each cost a revision round.
        sections = [
            (
                await renderer.render(f"request.proposal_convention_{c.kind.value}", dict(c.values))
            ).content
            for c in conventions
        ]
        section = await renderer.render(
            "request.proposal_frozen_conventions",
            {"convention_sections": "\n\n".join(sections)},
        )
        out["frozen_conventions_section"] = section.content
    prd = str(inputs.get("prd") or "").strip()
    if prd:
        # The objective points into the product's requirements (its expansion scope, say);
        # the model is shown them rather than asked to recall them.
        section = await renderer.render("request.proposal_prd_section", {"prd": prd})
        out["prd_section"] = section.content
    note = str(block.get("supervisor_note") or "").strip()
    if note:
        # SIP-0109 §9.2: a revision run is shown the note and the version it revises.
        section = await renderer.render(
            "request.proposal_supervisor_revision",
            {
                "prior_version": str(proposal_context.version - 1),
                "supervisor_note": note,
                "prior_change_request": str(block.get("prior_change_request") or "").strip(),
            },
        )
        out["supervisor_note_section"] = section.content
    proposed = block.get("qa_proposed_behaviours") or []
    if proposed:
        # #1884: what the last increment's qa author proposed instead of testing.
        from squadops.campaigns.proposed_behaviours import proposal_lines

        section = await renderer.render(
            "request.proposal_qa_proposed_behaviours",
            {"proposed_lines": proposal_lines(proposed)},
        )
        out["qa_proposed_behaviours_section"] = section.content
    abandoned = brief_lines(block.get("abandoned_increment"))
    if abandoned:
        # SIP-0109 §7, row 13 (#1692): a fresh proposal is shown why the last increment was
        # abandoned, so it does not propose the same failure again unchanged.
        section = await renderer.render(
            "request.proposal_abandoned_increment", {"brief_lines": abandoned}
        )
        out["abandoned_increment_section"] = section.content
    return out


class StrategyProposeIncrementHandler(_PlanningTaskHandler):
    """Proposal handler: author the typed change request for the next increment."""

    _handler_name = "strategy_propose_increment_handler"
    _task_type = TaskType.STRATEGY_PROPOSE_INCREMENT
    _role = "strat"
    _artifact_name = CHANGE_REQUEST_FILENAME
    _request_template_id = "request.strategy_propose_increment"

    async def handle(self, context: ExecutionContext, inputs: dict[str, Any]) -> HandlerResult:
        from squadops.capabilities.handlers._plan_authoring import retry_yaml_call

        start_time = time.perf_counter()
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return self._failure(
                start_time, inputs, f"{self._handler_name} requires request_renderer"
            )
        resolved_config = inputs.get("resolved_config") or {}
        block = resolved_config.get("campaign_proposal") or {}
        try:
            proposal_context = proposal_context_from(
                resolved_config, str(block.get("baseline_manifest") or "")
            )
        except ProposalContextMissing as e:
            return self._failure(start_time, inputs, str(e))

        variables = _render_variables(block, proposal_context)
        variables.update(await _context_sections(renderer, inputs, block, proposal_context))
        rendered = await renderer.render(self._request_template_id, variables)
        assembled = context.ports.prompt_service.assemble(
            role=context.role_id,  # SIP-0108 §10m: the identity layer is what the process IS
            hook="agent_start",
            task_type=self._task_type,
        )

        verdicts: list[ProposalVerdict] = []

        async def parse_and_validate(text: str | None) -> tuple[Any, str | None]:
            if not text or not text.strip():
                return None, (
                    f"No `{CHANGE_REQUEST_FILENAME}` block was found in your response. Emit "
                    "exactly one fenced block whose header carries that filename."
                )
            try:
                authored = yaml.safe_load(text)
            except yaml.YAMLError as e:
                return None, f"`{CHANGE_REQUEST_FILENAME}` is not valid YAML: {e}"
            verdict = validate_proposal(authored, proposal_context)
            verdicts.append(verdict)
            if verdict.accepted:
                return verdict, None
            feedback = await renderer.render(
                "request.change_request_revision_feedback",
                {"refusals": "\n".join(f"- [{r.kind}] {r.detail}" for r in verdict.refusals)},
            )
            return None, feedback.content

        accepted, _last_yaml, last_error = await retry_yaml_call(
            call=partial(self._llm_call, context, inputs=inputs, started=start_time),
            chat_kwargs=self._build_chat_kwargs(inputs),
            system_prompt=assembled.content,
            user_prompt=rendered.content,
            parse_and_validate=parse_and_validate,
            max_attempts=int(
                resolved_config.get("proposal_max_attempts", _PROPOSAL_MAX_ATTEMPTS_DEFAULT)
            ),
            handler_name=self._handler_name,
        )
        if accepted is None:
            refused = verdicts[-1].refusals if verdicts else ()
            reasons = "; ".join(f"[{r.kind}] {r.detail}" for r in refused) or last_error
            return self._failure(
                start_time,
                inputs,
                f"the proposal was refused after its revision budget (§9.1): {reasons}",
            )
        return self._success(start_time, inputs, accepted, assembled, rendered)

    def _success(
        self,
        start_time: float,
        inputs: dict[str, Any],
        verdict: ProposalVerdict,
        assembled: Any,
        rendered: Any,
    ) -> HandlerResult:
        request = verdict.change_request
        document = stored_change_request(request)
        outputs: dict[str, Any] = {
            "summary": (
                f"[{self._role}] proposed {request.proposal_id} v{request.version} "
                f"({request.kind}, {len(request.criteria)} criteria, "
                f"{len(request.footprint)} footprint entries) — hash {request.content_hash[:12]}"
            ),
            "role": self._role,
            "artifacts": [
                {
                    "name": CHANGE_REQUEST_FILENAME,
                    "content": document,
                    "media_type": "text/yaml",
                    "type": CHANGE_REQUEST_ARTIFACT_TYPE,
                }
            ],
            "change_request": {
                "proposal_id": request.proposal_id,
                "version": request.version,
                "content_hash": request.content_hash,
                "baseline_tree": request.baseline_tree,
            },
            "prompt_provenance": {
                "system_prompt_bundle_hash": assembled.assembly_hash,
                "request_template_id": rendered.template_id,
                "request_template_version": rendered.template_version,
                "request_render_hash": rendered.render_hash,
                "prompt_environment": "production",
            },
        }
        return HandlerResult(
            success=True,
            outputs=outputs,
            _evidence=HandlerEvidence.create(
                handler_name=self._handler_name,
                task_type=self._task_type,
                duration_ms=(time.perf_counter() - start_time) * 1000,
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict(outputs),
            ),
        )

    def _failure(self, start_time: float, inputs: dict[str, Any], error: str) -> HandlerResult:
        logger.warning("%s: %s", self._handler_name, error)
        return HandlerResult(
            success=False,
            outputs={},
            _evidence=HandlerEvidence.create(
                handler_name=self._handler_name,
                task_type=self._task_type,
                duration_ms=(time.perf_counter() - start_time) * 1000,
                inputs_hash=self._hash_dict(inputs),
            ),
            error=error,
        )


def _render_variables(block: dict, context: ProposalContext) -> dict[str, str]:
    objective = block.get("objective") or {}
    variables = {
        "objective_statement": str(objective.get("statement", "")),
        "objective_measurement": str(objective.get("measurement", "")),
        "allowed_scope_lines": "\n".join(f"- `{s}`" for s in context.allowed_scope),
        "baseline_manifest": context.baseline_manifest.strip(),
        "prior_criteria_lines": (
            "\n".join(_frozen_line(c) for c in _frozen(block, context))
            or "- none yet: this is the first increment after calibration"
        ),
    }
    return variables


def _frozen(block: dict, context: ProposalContext) -> list[dict]:
    """Each frozen criterion's record, or its id alone where the block carries no records."""
    records = [c for c in block.get("frozen_criteria") or () if isinstance(c, dict)]
    return records or [{"criterion_id": c} for c in context.prior_criteria]


def _frozen_line(criterion: dict) -> str:
    """A frozen criterion as the proposal sees it: what it asserts, where (#1938). An id alone
    told the strategy role "do not break T3" without saying T3 was the feature it then
    re-proposed. A record frozen before statements were kept shows its id only."""
    line = f"- `{criterion['criterion_id']}`"
    statement = str(criterion.get("statement") or "").strip()
    if not statement:
        return line
    surface = str(criterion.get("surface") or "").strip()
    return f"{line}: {statement}" + (f" (on `{surface}`)" if surface else "")

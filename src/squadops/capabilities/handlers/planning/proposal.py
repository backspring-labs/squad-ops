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
    PRODUCT_PROPOSAL_INPUT,
    IncrementBasis,
    ProductContext,
    ProposalContext,
    ProposalVerdict,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.criterion_placement import RunnerPlacement
from squadops.campaigns.prior_cycle import brief_lines
from squadops.campaigns.proposed_behaviours import proposal_lines
from squadops.campaigns.unapproved_proposals import unapproved_lines
from squadops.capabilities.handlers._plan_authoring import retry_yaml_call
from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
from squadops.capabilities.handlers.cross_cycle_lessons import cross_cycle_lessons_section
from squadops.capabilities.handlers.planning.base import _PlanningTaskHandler
from squadops.capabilities.handlers.task_instructions import (
    project_instructions_section,
    task_instructions_section,
)
from squadops.outcomes.proposal_evidence import (
    PROPOSAL_EVIDENCE_INPUT,
    accepted_prd_lines,
    goal_lines,
    quality_lines,
    shown_goal_ids,
    shown_goal_statements,
)
from squadops.projects.derived_profile import SURFACES
from squadops.stacks.scaffold import frozen_conventions_for
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


def proposal_context_from(
    resolved_config: dict,
    baseline_manifest: str,
    *,
    shown_goals: tuple[str, ...],
    shown_goal_statements: tuple[tuple[str, str], ...],
    product: dict | None = None,
) -> ProposalContext:
    """The rails' context from the cycle's ``campaign_proposal`` block and the fetched manifest,
    and the goals the task's evidence showed it (SIP-0113 §4.5), which its ``moves_goals`` may
    name.

    On a campaign branch (§24bv point 5) there is no manifest: the rails read the product's
    surfaces and runners from ``product``, the ``product_proposal`` input its run composed. A
    branch proposal without it is refused, never read as a sample application's."""
    block = resolved_config.get("campaign_proposal")
    if not isinstance(block, dict):
        raise ProposalContextMissing(
            "the cycle carries no campaign_proposal block: a proposal run is launched by a "
            "campaign, which names the accepted tree and the objective it proposes against"
        )
    try:
        basis = IncrementBasis(str(block.get("basis") or IncrementBasis.MANIFEST))
    except ValueError as e:
        raise ProposalContextMissing(f"campaign_proposal names an unknown basis: {e}") from e
    if basis.has_manifest and not baseline_manifest.strip():
        raise ProposalContextMissing(
            "campaign_proposal carries no baseline_manifest: the accepted manifest is the run's "
            "input (§9.1), persisted with it, not fetched"
        )
    if not basis.has_manifest and not isinstance(product, dict):
        raise ProposalContextMissing(
            f"the proposal is on a campaign branch and was given no {PRODUCT_PROPOSAL_INPUT}: "
            "the product's head, profile and requirements are the run's input (§24bv point 5)"
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
            shown_goals=shown_goals,
            shown_goal_statements=shown_goal_statements,
            product=None if basis.has_manifest else product_context(product or {}),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ProposalContextMissing(f"campaign_proposal is incomplete: {e!r}") from e


def product_context(product: dict) -> ProductContext:
    """The rails' reading of a ``product_proposal`` input: each public surface as ``(kind,
    value)``, and each runner's placement."""
    profile = product["profile"]
    return ProductContext(
        surfaces=tuple(
            (str(s["kind"]), _surface_value(s)) for s in profile.get("public_surfaces") or ()
        ),
        placements=tuple(RunnerPlacement.from_dict(p) for p in profile.get("placements") or ()),
        test_files=tuple(str(g) for g in profile.get("test_files") or ()),
    )


#: SIP-0113 §4.5 (§10t step 4): what the proposal is shown of its accepted tree's outcomes, each
#: part in its own asset, by the request template's variable. A part with nothing in it renders none.
_EVIDENCE_SECTIONS = (
    ("goals", "request.proposal_outcome_goals", "goal_lines", goal_lines, "outcome_goals_section"),
    (
        "quality",
        "request.proposal_quality_moves",
        "quality_lines",
        quality_lines,
        "quality_moves_section",
    ),
    (
        "accepted_prd",
        "request.proposal_accepted_prd",
        "accepted_prd_lines",
        accepted_prd_lines,
        "accepted_prd_section",
    ),
)


async def _evidence_sections(renderer: Any, evidence: dict[str, Any]) -> dict[str, str]:
    """Each part's section, set apart as the template's other spliced sections are: the renderer
    strips an asset's edges, and the template places these side by side."""
    out: dict[str, str] = {}
    for key, template_id, variable, lines, section in _EVIDENCE_SECTIONS:
        if evidence.get(key):
            rendered = await renderer.render(template_id, {variable: lines(evidence)})
            out[section] = "\n\n" + rendered.content.strip("\n") + "\n"
    return out


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
    out.update(await _evidence_sections(renderer, inputs.get(PROPOSAL_EVIDENCE_INPUT) or {}))
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
    unapproved = block.get("unapproved_proposals") or []
    if unapproved:
        # #2593: a fresh proposal is shown each proposal the campaign never approved, with the
        # ruling's reason, as a revision is shown its note.
        section = await renderer.render(
            "request.proposal_unapproved_proposals",
            {"unapproved_lines": unapproved_lines(unapproved)},
        )
        out["unapproved_proposals_section"] = section.content
    proposed = block.get("qa_proposed_behaviours") or []
    if proposed:
        # #1884: what the last increment's qa author proposed instead of testing.

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

        start_time = time.perf_counter()
        renderer = getattr(context.ports, "request_renderer", None)
        if renderer is None:
            return self._failure(
                start_time, inputs, f"{self._handler_name} requires request_renderer"
            )
        resolved_config = inputs.get("resolved_config") or {}
        block = resolved_config.get("campaign_proposal") or {}
        product = inputs.get(PRODUCT_PROPOSAL_INPUT)
        try:
            proposal_context = proposal_context_from(
                resolved_config,
                str(block.get("baseline_manifest") or ""),
                shown_goals=shown_goal_ids(inputs.get(PROPOSAL_EVIDENCE_INPUT)),
                shown_goal_statements=shown_goal_statements(inputs.get(PROPOSAL_EVIDENCE_INPUT)),
                product=product if isinstance(product, dict) else None,
            )
        except ProposalContextMissing as e:
            return self._failure(start_time, inputs, str(e))

        variables = _render_variables(block, proposal_context)
        variables.update(await _context_sections(renderer, inputs, block, proposal_context))
        template_id = self._request_template_id
        if proposal_context.product is not None:
            # §24bv point 5: the product's head, tree, profile, verification and requirements,
            # in place of the accepted manifest.
            assert isinstance(product, dict)
            variables.pop("baseline_manifest")
            variables.update(await product_sections(renderer, inputs, product))
            template_id = PRODUCT_REQUEST_TEMPLATE
        # SIP-0110 §0.9: the lessons approved for this task, in a slot of their own, apart from a
        # revision's note (SIP-0109 §9.2).
        # SIP-0110 Appendix A §3.6 (#2178): this task's instructions, before the lessons.
        instructions = await task_instructions_section(renderer, inputs)
        if instructions:
            variables["task_instructions_section"] = instructions
        project = await project_instructions_section(renderer, inputs)
        if project:
            variables["project_instructions_section"] = project
        lessons = await cross_cycle_lessons_section(renderer, inputs)
        if lessons:
            variables["cross_cycle_lessons_section"] = lessons
        rendered = await renderer.render(template_id, variables)
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


#: §24bv point 5: the request a repository-backed Project's proposal is sent, in place of
#: ``request.strategy_propose_increment``'s manifest.
PRODUCT_REQUEST_TEMPLATE = "request.strategy_propose_product_increment"


async def product_sections(
    renderer: Any, inputs: dict[str, Any], product: dict[str, Any]
) -> dict[str, str]:
    """The product's parts of the request (§24bv point 5), each through its own managed asset
    (#448), keyed by the product template's variables. The lines are data; the prose is the
    assets'."""
    profile = product["profile"]
    verification = product["previous_verification"]
    requirements = product["requirements"]
    profile_variables = {
        "surface_lines": "\n".join(_surface_line(s) for s in profile.get("public_surfaces") or ())
        or "- none: the product declares no start, command or package",
        "placement_lines": "\n".join(_placement_line(p) for p in profile.get("placements") or ())
        or "- none: the product declares no test runner",
    }
    gaps = profile.get("gaps") or []
    if gaps:
        lines = "\n".join(
            f"- {g['id']}"
            + (f" ({g['subject']})" if g.get("subject") else "")
            + f", on `{', '.join(g['paths'])}`: {g['reason']}"
            for g in gaps
        )
        rendered = await renderer.render("request.proposal_product_gaps", {"gap_lines": lines})
        profile_variables["gaps_section"] = rendered.content
    head = str(product["head"]["commit"])
    approved = product.get("approved_manifest")
    sections: dict[str, str] = {}
    if approved:
        # §24bv point 5: a greenfield product's approved manifest (SIP-0112 H.1), beside the rest.
        rendered = await renderer.render(
            "request.proposal_approved_manifest",
            {
                "stack": str(approved["stack"]),
                "commit": str(approved["commit"]),
                "manifest": str(approved["content"]).strip(),
            },
        )
        sections["approved_manifest_section"] = rendered.content
    return {
        **sections,
        "head_commit": head,
        "product_tree_section": await _tree_section(renderer, inputs, head),
        "product_profile_section": (
            await renderer.render("request.proposal_product_profile", profile_variables)
        ).content,
        "previous_verification_section": (
            await renderer.render(
                "request.proposal_previous_verification",
                {
                    "verification_source": str(verification["source"]),
                    "verification_commit": str(verification["commit"]),
                    "check_lines": "\n".join(
                        _check_line(c) for c in verification.get("checks") or ()
                    )
                    or "- no check ran",
                },
            )
        ).content,
        "requirements_section": (
            await renderer.render(
                "request.proposal_requirements_source",
                {
                    "requirements_ref": str(requirements["ref"]),
                    "requirements": str(requirements["content"]).strip(),
                },
            )
        ).content,
    }


async def _tree_section(renderer: Any, inputs: dict[str, Any], head: str) -> str:
    """The head's tree, from the task's bounded ``source_repository`` view (SIP-0112 E.4.3): its
    map and the product's own instruction files. Not the view's whole appendix, which tells a
    build task how to emit files: the proposal emits none. ``""`` for a task given no view."""
    repository = inputs.get("source_repository")
    if not isinstance(repository, dict):
        return ""
    variables = {"head_commit": head, "repository_map": str(repository["map"])}
    instructions = repository.get("instructions") or {}
    if instructions:
        files = "\n\n".join(f"**{p}:**\n```\n{c}\n```" for p, c in instructions.items())
        block = await renderer.render(
            "request.source_repository_instructions_block", {"files": files}
        )
        variables["instructions"] = block.content
    return (await renderer.render("request.proposal_product_tree", variables)).content


def _surface_value(surface: dict) -> str:
    """A contract 8 surface's one value (``SURFACES``): its URL, its argv joined, or its name."""
    value = surface.get(SURFACES.get(str(surface["kind"]), "url"))
    return " ".join(str(a) for a in value) if isinstance(value, list) else str(value)


def _surface_line(surface: dict) -> str:
    return f"- {surface['kind']}: `{_surface_value(surface)}`"


def _placement_line(placement: dict) -> str:
    covers = ", ".join(f"`{c}`" for c in placement.get("covers") or ())
    if placement.get("template"):
        return (
            f"- `{placement['runner']}` tests {covers}: a criterion's test is placed at "
            f"`{placement['template']}`"
        )
    return f"- `{placement['runner']}` tests {covers}: hosts no criterion ({placement['refused']})"


def _check_line(check: dict) -> str:
    line = f"- `{check['id']}`: {check['result']}"
    if check.get("reason"):
        line += f" ({check['reason']})"
    findings = check.get("findings")
    if findings:
        keys = ", ".join(f"`{k}`" for k in findings["keys"])
        more = findings["count"] - len(findings["keys"])
        line += f"; {findings['count']} finding keys: {keys}" + (
            f" and {more} more" if more else ""
        )
    return line


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

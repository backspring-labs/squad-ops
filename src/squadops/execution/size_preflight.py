"""A Campaign's size preflight: every task it dispatches, rendered on the product's tree before its
first cycle (#2889, SIP-0109 §24db).

#2805 and #2810 were each found live, an hour into a Campaign: a task whose prompt, as the composer
counts it (``squadops.capabilities.prompt_budget``, SIP-0110 §3.6), could not fit its model's window
on a repository-backed product, held on its binding. The proving product grows over the line, so
the next one is checked before the first cycle instead.

**Where it runs.** At a repository-backed Campaign's start, beside its calibration record
(``api.routes.campaigns``'s ``_calibration_record``): the one place every such Campaign passes
before its first cycle, and the one that already refuses a start on a blocking gap
(``CalibrationRecordRefused``, 409 ``CALIBRATION_REFUSED``), before anything is written. A sample
application's Campaign has no record and no product tree, and is never read here.

**What it measures.** For each task type the Campaign's increments can dispatch
(``task_plan.dispatched_task_steps``, the reading the #2810 guard reads), on the model its squad
binds the type's role to:
- the envelope the increment's run composes from the product: the tree at the calibration record's
  commit and its manifest (``source_checkout.checkout_of``, ``seeded_files``), selected and held to the limit
  by the executor's own rule (``ArtifactFilter.selects``, ``ARTIFACT_CONTENTS_LIMIT_BYTES``), its
  ``source_repository`` view (``checkout.source_repository_input``), and a repair's forwarded tree
  and failed files (``repair_forwarded_inputs``), with the first increment's resolved config
  (``launch_requests.increment_launch``);
- counted by the composer's own estimate (``prompt_without_memory_tokens``) with its completion
  reserve (``completion_reserve``), against the model's window (``get_model_spec``).

**With the skills each task is handed (SIP-0116 §17m).** The first launch's skillset record is
built here as ``prepare_cycle`` builds it (``skillset_record_and_content``, over the packaged
catalog), under the development profile that launch pins (``development_profile_pin``, the same
call), and each binding's envelope carries the skills dispatch would hand it
(``skill_supply.handed_skills``, the same call). A task is measured with the skills of its own
task type: a planner names no contract today (§17k). A refusal says how many of a binding's
tokens are its skills, and names them. A Campaign whose work requires no skillset is handed none,
and measures as before.

**A floor, so it refuses only what can't fit.** The composer's estimate is an upper bound of what
the handler renders, and it is what holds a task live, so the preflight reads it. What it can't know
before a cycle runs, it leaves out, so each count is the least that task's prompt can be on this
product:
- the squad's own outputs (framing documents, the plan, a failure's evidence) and memory's sections;
- the files a plan names: a task that names files is measured naming one, the smallest file of one
  top-level directory, and the least over the product's directories is its size. A plan naming
  only root-level files is left out: ``qa.test`` would be shown those files alone.
A binding over the window at its floor can't fit on any plan that names files in the product's
directories, and is a blocking gap
(``PROMPT_OVER_WINDOW``), named with its task type, role, model, size and window. One that fits
here can still be held live by a larger plan, and the composer still holds it then.

**Require, don't default.** A binding whose model has no window the registry knows, a squad or
proposal profile that can't be read, and a tree that can't be read (unreachable, refused, past
2.4's limits on what a run takes on, ``CheckoutTooLarge``, or one a run can't carry) each refuse the
start as ``SIZE_UNMEASURED``, naming why. So does a record that can't be built (a squad that
doesn't cover its work's requirements, a skill the catalog holds no text for) and a development
profile the request names that contradicts the product's runners. None is read as fitting, or as a
task handed no skills.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from squadops.campaigns.calibration_record import (
    PROMPT_OVER_WINDOW,
    CalibrationRecord,
    CalibrationRecordRefused,
    RefusalCause,
)
from squadops.campaigns.launch_requests import increment_launch
from squadops.capabilities.context_assembly import (
    ACCEPTANCE_WORKSPACE_FILTER,
    ARTIFACT_CONTENTS_LIMIT_BYTES,
    INCREMENT_CANDIDATE_FILTER,
    LANDING_PRIOR_OUTPUTS,
    REPAIR_FAILED_ARTIFACTS_KEY,
    ArtifactFilter,
    get_context_contract,
    repair_forwarded_inputs,
)
from squadops.capabilities.prompt_budget import completion_reserve, prompt_without_memory_tokens
from squadops.capabilities.skillsets import packaged_skillsets
from squadops.cycles.agent_config import UnservedRoleError, resolve_agent_config
from squadops.cycles.development_pin import (
    derived_profile_at_pin,
    development_profile_pin,
    pinned_overrides,
)
from squadops.cycles.models import CycleError, PreflightRejectedError, resolve_config
from squadops.cycles.skillset_content import (
    SKILLS_INPUT,
    LoadedSkill,
    SkillsetContentError,
    skills_input,
)
from squadops.cycles.skillset_record import skillset_record_and_content
from squadops.cycles.task_plan import (
    DISPATCHED_BY_REPAIR,
    DISPATCHED_BY_WORKLOAD,
    DispatchedStep,
    dispatched_task_steps,
)
from squadops.execution.skill_supply import handed_skills
from squadops.execution.source_checkout import (
    SourceCheckoutRefused,
    checkout_of,
    seeded_files,
)
from squadops.llm.model_registry import get_model_spec
from squadops.projects.checkout import (
    SOURCE_CHECKOUT,
    CheckoutManifest,
    CheckoutTooLarge,
    source_repository_input,
)
from squadops.projects.models import SourceUnavailable
from squadops.projects.source_context import PROJECT_BASELINE, ProjectSourceContext
from squadops.tasks.models import TaskEnvelope

if TYPE_CHECKING:
    from squadops.campaigns.models import Campaign
    from squadops.cycles.models import Project, SquadProfile
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort
    from squadops.projects.derived_profile import DerivedProfile

logger = logging.getLogger(__name__)

#: A checkout file as a run is seeded with it: its path, its text, its artifact type, its bytes.
_File = tuple[str, str, str, int]


@dataclass(frozen=True)
class BindingSize:
    """One binding's measurement: a task type, on the model its role is bound to."""

    task_type: str
    role: str
    model: str
    #: The prompt the composer counts for it on the product, memory's sections aside, at its floor.
    prompt_tokens: int
    completion_reserve: int
    window: int
    #: The skills dispatch hands it, as ``skillset/skill``, and how many of ``prompt_tokens`` they
    #: are: the floor with them, less the floor without them.
    skills: tuple[str, ...] = ()
    skills_tokens: int = 0

    @property
    def fits(self) -> bool:
        return self.prompt_tokens + self.completion_reserve <= self.window

    def to_document(self) -> dict[str, Any]:
        """The binding as a refusal names it. A binding handed skills names them and their
        tokens; one handed none reads as it did before skills were counted."""
        document: dict[str, Any] = {
            "task_type": self.task_type,
            "role": self.role,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_reserve": self.completion_reserve,
            "window": self.window,
        }
        if self.skills:
            document.update(skills=list(self.skills), skills_tokens=self.skills_tokens)
        return document

    def named(self) -> str:
        over = self.prompt_tokens + self.completion_reserve - self.window
        handed = (
            f" ({self.skills_tokens} of them the skills it is handed: {', '.join(self.skills)})"
            if self.skills
            else ""
        )
        return (
            f"{self.task_type} ({self.role}, on {self.model}): its prompt is {self.prompt_tokens} "
            f"tokens{handed} and its completion reserve {self.completion_reserve}, over the "
            f"{self.window}-token window by {over}"
        )


async def size_preflight(
    campaign: Campaign,
    project: Project,
    record: CalibrationRecord,
    *,
    registry: ProjectRegistryPort,
    repository: Any,
    squad_profiles: SquadProfilePort,
) -> tuple[BindingSize, ...]:
    """Every binding of ``campaign``'s increments, measured on ``project``'s tree at ``record``'s
    commit, or :class:`CalibrationRecordRefused`: ``BLOCKING_GAP`` naming each binding over its
    window (``PROMPT_OVER_WINDOW``), or ``SIZE_UNMEASURED`` naming what couldn't be measured.
    Reads only; writes nothing."""
    roster, roster_hash = await _squad(squad_profiles, campaign.policy.squad_profile)
    context = _context(project, record)
    resolved = _pinned(
        _first_increment_request(campaign, record),
        await derived_profile_at_pin(registry, context),
    )
    equipped = _equipped(campaign, roster, roster_hash, resolved)
    bindings = _bindings(resolved, roster)
    files, manifest = await _product(project, context, registry=registry, repository=repository)
    sizes = tuple(
        _measured(task_type, step, binding, resolved, files, manifest, equipped)
        for task_type, (step, binding) in bindings.items()
    )
    logger.info(
        "size_preflight_equipment campaign=%s development_profile=%s skillset_record=%s",
        campaign.campaign_id, equipped.development_profile, equipped.record["digest"],
    )  # fmt: skip
    for size in sizes:
        logger.info(
            "size_preflight campaign=%s %s prompt=%d reserve=%d window=%d",
            campaign.campaign_id, size.task_type, size.prompt_tokens, size.completion_reserve,
            size.window,
        )  # fmt: skip
    over = [s for s in sizes if not s.fits]
    if over:
        raise CalibrationRecordRefused(
            RefusalCause.BLOCKING_GAP,
            f"Project {project.project_id}'s product at {record.commit} is too large for "
            f"{len(over)} of the tasks Campaign {campaign.campaign_id} dispatches, each measured "
            "at the least its prompt can be on this tree: "
            + "; ".join(s.named() for s in over)
            + f" ({PROMPT_OVER_WINDOW}; closes by binding the role to a model with a larger "
            "window, or a smaller product"
            + (", or lighter skills" if any(s.skills for s in over) else "")
            + ")",
            gaps=[PROMPT_OVER_WINDOW],
            bindings=[s.to_document() for s in over],
        )
    return sizes


async def _squad(squad_profiles: SquadProfilePort, profile_id: str) -> tuple[SquadProfile, str]:
    """The squad and its snapshot hash, as ``prepare_cycle`` resolves them for the launch."""
    try:
        return await squad_profiles.resolve_snapshot(profile_id)
    except CycleError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't read squad profile {profile_id!r}, whose models every "
            f"task is measured on: {e}",
        ) from e


def _first_increment_request(campaign: Campaign, record: CalibrationRecord) -> dict[str, Any]:
    """The request body of the Campaign's first increment: the one ``increment_launch`` builds
    once the record is promoted, so the tree it proposes on is the record's commit."""
    promoted = dataclasses.replace(campaign, accepted=record.accepted_tree)
    try:
        return increment_launch(promoted, None).cycle_request["body"]
    except FileNotFoundError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't load proposal profile "
            f"{campaign.policy.proposal_profile!r}, whose tasks it measures: {e}",
        ) from e


def _pinned(body: Mapping[str, Any], derived: DerivedProfile | None) -> dict[str, Any]:
    """The first increment's resolved config with the development profile its launch pins, by
    the call ``prepare_cycle`` makes. A profile the request names that contradicts the product's
    runners refuses the launch there, and refuses the start here."""
    defaults, overrides = body["applied_defaults"], body["execution_overrides"]
    try:
        selection = development_profile_pin(resolve_config(defaults, overrides), derived)
    except PreflightRejectedError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't name the development profile the first launch runs "
            f"under, which the launch would refuse: {e}",
        ) from e
    if selection is not None:
        overrides = pinned_overrides(overrides, selection)
    return resolve_config(defaults, overrides)


@dataclass(frozen=True)
class _Equipped:
    """The first launch's skillset record and the kept copy its skills are read from: ``None``
    when its skillsets load no skill."""

    record: Mapping[str, Any]
    document: Mapping[str, Any] | None

    @property
    def development_profile(self) -> str:
        return str(self.record["development_profile"]["name"])


def _equipped(
    campaign: Campaign, roster: SquadProfile, roster_hash: str, resolved: Mapping[str, Any]
) -> _Equipped:
    """The record ``prepare_cycle`` builds for the first launch, or refused naming why."""
    try:
        record, document = skillset_record_and_content(
            roster, roster_hash, resolved, packaged_skillsets()
        )
    except (ValueError, SkillsetContentError) as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't build the skillset record Campaign "
            f"{campaign.campaign_id}'s first launch is created with, so it can't count the skills "
            f"each task is handed: {e}",
        ) from e
    return _Equipped(record, document)


@dataclass(frozen=True)
class _Binding:
    agent_id: str
    model: str
    overrides: Mapping[str, Any]
    window: int


def _bindings(
    resolved: Mapping[str, Any], roster: SquadProfile
) -> dict[str, tuple[DispatchedStep, _Binding]]:
    """Each task type the increments dispatch, with its model and that model's window. Refused,
    naming every one, when a role is unserved or a model's window is unknown."""
    try:
        steps = dispatched_task_steps(resolved, roster, source_backed=True)
    except (CycleError, UnservedRoleError) as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't read what squad profile {roster.profile_id!r} dispatches: {e}",
        ) from e
    bound: dict[str, tuple[DispatchedStep, _Binding]] = {}
    unknown: list[str] = []
    for task_type, step in steps.items():
        try:
            agent = resolve_agent_config(step.role, roster)
        except UnservedRoleError as e:
            raise CalibrationRecordRefused(RefusalCause.SIZE_UNMEASURED, str(e)) from e
        spec = get_model_spec(agent.model or "")
        if spec is None:
            unknown.append(f"{task_type} ({step.role}, on {agent.model or 'no model'})")
            continue
        bound[task_type] = (
            step,
            _Binding(agent.agent_id, spec.name, agent.config_overrides, spec.context_window),
        )
    if unknown:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"squad profile {roster.profile_id!r} binds {', '.join(unknown)} to a model whose "
            "context window the model registry doesn't know (squadops.llm.model_registry), so "
            "the size preflight can't say whether its prompts fit: bind it to a registered model",
            unknown=unknown,
        )
    return bound


def _context(project: Project, record: CalibrationRecord) -> ProjectSourceContext:
    """The Project pinned at the record's commit and revision."""
    source = project.source
    if source is None:  # a sample application's start has no record, and never reaches here
        raise ValueError(f"Project {project.project_id} has no source to measure")
    return ProjectSourceContext(
        project_id=project.project_id,
        record_version=project.record_version,
        development_configuration_revision=record.development_configuration_revision,
        repo_uri=source.repo_uri,
        development_baseline_commit=record.commit,
        integrated_upstream_commit=project.integrated_upstream_commit,
        pinned_commit=record.commit,
        pinned_from=PROJECT_BASELINE,
        previous_verification_ref=None,
    )


async def _product(
    project: Project,
    context: ProjectSourceContext,
    *,
    registry: ProjectRegistryPort,
    repository: Any,
) -> tuple[list[_File], CheckoutManifest]:
    """The checkout at the context's commit, as a run is seeded with it, or refused naming why."""
    commit = context.pinned_commit
    try:
        tree, manifest = await checkout_of(
            project.project_id, context, repository=repository, registry=registry
        )
    except (SourceUnavailable, SourceCheckoutRefused, CheckoutTooLarge) as e:
        # CheckoutTooLarge: past 2.4's limits on a product a run takes on, which no run of the
        # Campaign could seed either.
        reason = getattr(e, "reason", None) or (
            "too_large" if isinstance(e, CheckoutTooLarge) else "refused"
        )
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't read Project {project.project_id}'s tree at "
            f"{commit} ({reason}): {e}",
            reason=reason,
        ) from e
    files = [
        (path, content.decode(errors="replace"), artifact_type, len(content))
        for path, content, artifact_type, _media in seeded_files(tree, manifest)
    ]
    return files, manifest


def _measured(
    task_type: str,
    step: DispatchedStep,
    binding: _Binding,
    resolved: Mapping[str, Any],
    files: Sequence[_File],
    manifest: CheckoutManifest,
    equipped: _Equipped,
) -> BindingSize:
    """The binding's prompt at its floor, with the skills it is handed: the least over the files
    a plan may name (none, for a task that names none)."""
    base = {
        "resolved_config": dict(resolved),
        "agent_model": binding.model,
        "agent_config_overrides": dict(binding.overrides),
    }
    skills = _skills(task_type, binding, base, equipped)
    choices: list[tuple[str, ...]] = (
        [(path,) for path in _least_per_directory(files)] if step.names_files else []
    ) or [()]
    envelopes = [
        {**base, **inputs}
        for named in choices
        for inputs in _product_inputs(step, task_type, named, files, manifest)
    ]
    handed = {SKILLS_INPUT: skills_input(skills)} if skills else {}
    prompt = min(
        prompt_without_memory_tokens(_envelope(task_type, binding, {**inputs, **handed}))
        for inputs in envelopes
    )
    without = (
        min(prompt_without_memory_tokens(_envelope(task_type, binding, i)) for i in envelopes)
        if skills
        else prompt
    )
    reserve = completion_reserve(
        task_type,
        model_name=binding.model,
        agent_model=binding.model,
        agent_overrides=binding.overrides,
    )
    return BindingSize(
        task_type,
        step.role,
        binding.model,
        prompt,
        reserve or 0,
        binding.window,
        skills=tuple(f"{s.skillset}/{s.skill}" for s in skills),
        skills_tokens=prompt - without,
    )


def _skills(
    task_type: str, binding: _Binding, base: Mapping[str, Any], equipped: _Equipped
) -> tuple[LoadedSkill, ...]:
    """What dispatch hands the binding's task: none when the record's skillsets load no skill."""
    if equipped.document is None:
        return ()
    try:
        return handed_skills(
            equipped.document,
            equipped.record,
            _envelope(task_type, binding, dict(base)),
            of="the first launch",
        )
    except SkillsetContentError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't read the skills {task_type} ({binding.agent_id}) is "
            f"handed: {e}",
        ) from e


def _least_per_directory(files: Iterable[_File]) -> list[str]:
    """The smallest file of each top-level directory, the one a plan's task names when it names
    the least of that directory. A sample application's ``qa.test`` is shown the top-level
    directories its named files live in (``qa_prompt_contents.package_scoped``); a product's is
    shown each named file whole and what fits beside it (``product_scoped``, SIP-0112 H.39), so
    on a product the floor is its named files. Root files are their own "directory" there, so a
    plan naming only a root file would be shown that file alone. That is the degenerate plan the
    floor leaves out, or every product would fit; they are read only for a product with no
    directory."""
    least: dict[str, tuple[int, str]] = {}
    roots: list[str] = []
    for path, text, _type, _size in files:
        top, slash, _rest = path.partition("/")
        if not slash:
            roots.append(path)
        elif top not in least or (len(text), path) < least[top]:
            least[top] = (len(text), path)
    return sorted(path for _size, path in least.values()) or sorted(roots)


def _product_inputs(
    step: DispatchedStep,
    task_type: str,
    named: tuple[str, ...],
    files: Sequence[_File],
    manifest: CheckoutManifest,
) -> list[dict[str, Any]]:
    """What the task's envelope can carry of the product, as the run composes it: a workload's
    task by the executor's enrichment (``_enrich_envelope``); a repair by the correction loop's
    (``correction_repair``), forwarded from a failed task it repairs, one envelope for each. A
    correction step and the pulse chain carry none of it."""
    if step.origin == DISPATCHED_BY_WORKLOAD:
        return [_enriched(task_type, named, files, manifest)]
    if step.origin != DISPATCHED_BY_REPAIR:
        return [{}]
    texts = {path: text for path, text, _type, _size in files}
    failed_files = [{"name": path, "content": texts[path]} for path in named]
    return [
        {
            "expected_artifacts": list(named),
            **repair_forwarded_inputs(_enriched(failed_type, named, files, manifest)),
            **({REPAIR_FAILED_ARTIFACTS_KEY: failed_files} if failed_files else {}),
        }
        for failed_type in step.repairs
    ] or [{}]


def _enriched(
    task_type: str, named: tuple[str, ...], files: Sequence[_File], manifest: CheckoutManifest
) -> dict[str, Any]:
    """A workload task's product inputs, by its context contract as ``_enrich_envelope`` reads it:
    its curated contents, its acceptance workspace, and the bounded repository view every task of a
    source-backed run is handed (SIP-0112 E.4.3)."""
    contract = get_context_contract(task_type)
    inputs: dict[str, Any] = {}
    if named:
        # A plan task's subtask: the focused prompt, scoped to what it names.
        inputs.update(subtask_focus="", expected_artifacts=list(named))
    if contract.artifact_filter is not None:
        contents = _resolved(files, contract.artifact_filter)
        if contents and contract.artifact_landing == LANDING_PRIOR_OUTPUTS:
            inputs["prior_outputs"] = {"artifact_contents": contents}
        elif contents:
            inputs["artifact_contents"] = contents
    texts = {path: text for path, text, _type, _size in files}
    wanted = set(named) | set(manifest.instruction_paths)
    current = {path: texts[path] for path in wanted if path in texts}
    inputs["source_repository"] = source_repository_input(manifest, current, named)
    if contract.acceptance_workspace:
        workspace = _resolved(
            files,
            INCREMENT_CANDIDATE_FILTER
            if contract.increment_evaluation
            else ACCEPTANCE_WORKSPACE_FILTER,
        )
        if workspace:
            inputs["acceptance_workspace_files"] = workspace
    return inputs


def _resolved(files: Sequence[_File], selection: ArtifactFilter) -> dict[str, str]:
    """The checkout's files a resolution selects, refused where the executor's is (#3118): past
    ``ARTIFACT_CONTENTS_LIMIT_BYTES``, by name, never cut short. The checkout cap keeps a product's
    own tree under it."""
    contents = {
        path: text
        for path, text, artifact_type, _size in files
        if selection.selects(SOURCE_CHECKOUT, artifact_type)
    }
    total = sum(size for path, _text, _type, size in files if path in contents)
    if total > ARTIFACT_CONTENTS_LIMIT_BYTES:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't hand a task this product's tree: {total:,} bytes over "
            f"{len(contents)} files, past the {ARTIFACT_CONTENTS_LIMIT_BYTES:,}-byte limit of "
            "one resolution",
        )
    return contents


def _envelope(task_type: str, binding: _Binding, inputs: dict[str, Any]) -> TaskEnvelope:
    """A measurement envelope: the composer reads only its task type and inputs, and the skills a
    dispatch is handed are read by its task type and agent."""
    return TaskEnvelope(
        task_id="size-preflight",
        agent_id=binding.agent_id,
        cycle_id="size-preflight",
        pulse_id="size-preflight",
        project_id="size-preflight",
        task_type=task_type,
        correlation_id="size-preflight",
        causation_id="size-preflight",
        trace_id="size-preflight",
        span_id="size-preflight",
        inputs=inputs,
    )

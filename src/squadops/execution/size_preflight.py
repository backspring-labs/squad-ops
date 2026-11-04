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
  commit and its manifest (``source_checkout.checkout_of``, ``seeded_files``), selected and capped
  by the executor's own rule (``ArtifactFilter.selects``, ``ARTIFACT_CONTENTS_LIMIT_BYTES``), its
  ``source_repository`` view (``checkout.source_repository_input``), and a repair's forwarded tree
  and failed files (``repair_forwarded_inputs``), with the first increment's resolved config
  (``launch_requests.increment_launch``);
- counted by the composer's own estimate (``prompt_without_memory_tokens``) with its completion
  reserve (``completion_reserve``), against the model's window (``get_model_spec``).

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
start as ``SIZE_UNMEASURED``, naming why. None is read as fitting.
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
from squadops.cycles.agent_config import UnservedRoleError, resolve_agent_config
from squadops.cycles.models import CycleError, resolve_config
from squadops.cycles.task_plan import (
    DISPATCHED_BY_REPAIR,
    DISPATCHED_BY_WORKLOAD,
    DispatchedStep,
    dispatched_task_steps,
)
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

    @property
    def fits(self) -> bool:
        return self.prompt_tokens + self.completion_reserve <= self.window

    def to_document(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "role": self.role,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_reserve": self.completion_reserve,
            "window": self.window,
        }

    def named(self) -> str:
        return (
            f"{self.task_type} ({self.role}, on {self.model}): its prompt is {self.prompt_tokens} "
            f"tokens and its completion reserve {self.completion_reserve}, over the "
            f"{self.window}-token window by {self.prompt_tokens + self.completion_reserve - self.window}"
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
    roster = await _squad(squad_profiles, campaign.policy.squad_profile)
    resolved = _first_increment_config(campaign, record)
    bindings = _bindings(resolved, roster)
    files, manifest = await _product(project, record, registry=registry, repository=repository)
    sizes = tuple(
        _measured(task_type, step, binding, resolved, files, manifest)
        for task_type, (step, binding) in bindings.items()
    )
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
            "window, or a smaller product)",
            gaps=[PROMPT_OVER_WINDOW],
            bindings=[s.to_document() for s in over],
        )
    return sizes


async def _squad(squad_profiles: SquadProfilePort, profile_id: str) -> SquadProfile:
    try:
        return await squad_profiles.get_profile(profile_id)
    except CycleError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't read squad profile {profile_id!r}, whose models every "
            f"task is measured on: {e}",
        ) from e


def _first_increment_config(campaign: Campaign, record: CalibrationRecord) -> dict[str, Any]:
    """The resolved config of the Campaign's first increment: the request ``increment_launch``
    builds once the record is promoted, so the tree it proposes on is the record's commit."""
    promoted = dataclasses.replace(campaign, accepted=record.accepted_tree)
    try:
        body = increment_launch(promoted, None).cycle_request["body"]
    except FileNotFoundError as e:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"the size preflight can't load proposal profile "
            f"{campaign.policy.proposal_profile!r}, whose tasks it measures: {e}",
        ) from e
    return resolve_config(body["applied_defaults"], body["execution_overrides"])


@dataclass(frozen=True)
class _Binding:
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
        bound[task_type] = (step, _Binding(spec.name, agent.config_overrides, spec.context_window))
    if unknown:
        raise CalibrationRecordRefused(
            RefusalCause.SIZE_UNMEASURED,
            f"squad profile {roster.profile_id!r} binds {', '.join(unknown)} to a model whose "
            "context window the model registry doesn't know (squadops.llm.model_registry), so "
            "the size preflight can't say whether its prompts fit: bind it to a registered model",
            unknown=unknown,
        )
    return bound


async def _product(
    project: Project, record: CalibrationRecord, *, registry: ProjectRegistryPort, repository: Any
) -> tuple[list[_File], CheckoutManifest]:
    """The checkout at the record's commit, as a run is seeded with it, or refused naming why."""
    source = project.source
    if source is None:  # a sample application's start has no record, and never reaches here
        raise ValueError(f"Project {project.project_id} has no source to measure")
    context = ProjectSourceContext(
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
            f"{record.commit} ({reason}): {e}",
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
) -> BindingSize:
    """The binding's prompt at its floor: the least over the files a plan may name (none, for a
    task that names none)."""
    base = {
        "resolved_config": dict(resolved),
        "agent_model": binding.model,
        "agent_config_overrides": dict(binding.overrides),
    }
    choices: list[tuple[str, ...]] = (
        [(path,) for path in _least_per_directory(files)] if step.names_files else []
    ) or [()]
    prompt = min(
        prompt_without_memory_tokens(_envelope(task_type, {**base, **inputs}))
        for named in choices
        for inputs in _product_inputs(step, task_type, named, files, manifest)
    )
    reserve = completion_reserve(
        task_type,
        model_name=binding.model,
        agent_model=binding.model,
        agent_overrides=binding.overrides,
    )
    return BindingSize(task_type, step.role, binding.model, prompt, reserve or 0, binding.window)


def _least_per_directory(files: Iterable[_File]) -> list[str]:
    """The smallest file of each top-level directory, the one a plan's task names when it names
    the least of that directory: ``qa.test`` is shown the top-level directories its named files
    live in (``qa_prompt_contents.package_scoped``). Root files are their own "directory" there,
    so a plan naming only a root file would be shown that file alone. That is the degenerate plan
    the floor leaves out, or every product would fit; they are read only for a product with no
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
    """The checkout's files a resolution selects, in the run's order, stopping where the
    executor's does: at the file that takes it past ``ARTIFACT_CONTENTS_LIMIT_BYTES``."""
    contents: dict[str, str] = {}
    total = 0
    for path, text, artifact_type, size in files:
        if not selection.selects(SOURCE_CHECKOUT, artifact_type):
            continue
        total += size
        if total > ARTIFACT_CONTENTS_LIMIT_BYTES:
            break
        contents[path] = text
    return contents


def _envelope(task_type: str, inputs: dict[str, Any]) -> TaskEnvelope:
    """A measurement envelope: the composer reads only its task type and inputs."""
    return TaskEnvelope(
        task_id="size-preflight",
        agent_id="size-preflight",
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

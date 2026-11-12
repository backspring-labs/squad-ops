"""A scenario criterion run at an increment's delivery (SIP-0117 R5.7; #3053).

Runner criteria are run in the sandbox (``runner_acceptance``). A scenario criterion is a frozen
declaration that a remote operation plays (#3044), so at delivery the runtime asks for that
operation on each overlay, through its own remote-execution port, and reads the result with
``acceptance.discrimination_on_scenario`` and ``acceptance.held_on_scenario``.

- **What a scenario criterion is:** one whose placed file is ``scenario_criterion_path`` of its
  id, the one place the framework puts a scenario. Its bundle is that one file, with no runner
  invocation.
- **Its frozen scenario** is rebuilt from the bundle's bytes against the cycle's kept vocabulary
  (``frozen_scenario``). A new criterion's is compared with the digest its approved change
  request froze: a declaration that differs is never run as if it were the one approved.
- **Staging:** the overlay's text files go on the request; any other is named in the reading's
  ``not_staged``. The revision is ``staged_revision`` of what was staged, so a reading binds to
  exactly the tree its operation saw.
- **Each ask** is queued under ``acceptance_task_id`` with this evaluation's dispatch id, so two
  criteria or sides never stop each other, and a re-evaluation stops the older one's.

Anything that can't be asked (no port bound, no operation supplied, no vocabulary kept) leaves
the reading absent with the reason, which the decisions read as ``not_run`` or blocked, never as
a failure or a pass.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from squadops.campaigns.acceptance import credited_outcomes
from squadops.campaigns.change_request import (
    SurfaceKind,
    load_stored_change_request,
    scenario_criterion_path,
)
from squadops.campaigns.evaluator_trees import FileTree, VerifierBundle
from squadops.remote_execution.models import (
    ReadingSide,
    RemoteOperationRequest,
    Scenario,
    acceptance_task_id,
    records_document,
)
from squadops.remote_execution.scenario import (
    ScenarioRefused,
    ScenarioVocabulary,
    canonical_text,
    frozen_scenario,
    scenario_digest,
    staged_revision,
)

if TYPE_CHECKING:
    from squadops.capabilities.operation_supply import SuppliedOperation
    from squadops.ports.remote_execution import RemoteExecutionPort


def is_scenario_criterion(criterion_id: str, path: str) -> bool:
    """Whether a placed criterion file is a scenario's: the framework places one only at
    ``scenario_criterion_path`` of its id, and the placement check holds it there (#3044)."""
    return path == scenario_criterion_path(criterion_id)


def approved_scenario_digests(change_request: str) -> dict[str, str]:
    """Each scenario criterion's digest as its approved change request froze it (#3044 §2):
    what the declaration delivered at its path must still be."""
    return {
        c.id: scenario_digest(canonical_text(c.scenario))
        for c in load_stored_change_request(change_request).criteria
        if c.surface_kind is SurfaceKind.SCENARIO and c.scenario is not None
    }


def scenario_bundle(criterion_id: str, tree: FileTree) -> VerifierBundle | None:
    """The criterion's declaration, frozen as a one-file bundle with no invocation: nothing of a
    runner's runs it, and it imports nothing. ``None`` when ``tree`` doesn't hold it."""
    path = scenario_criterion_path(criterion_id)
    content = tree.as_dict().get(path)
    if content is None:
        return None
    return VerifierBundle(criterion_id, FileTree.of({path: content}), ())


@dataclass(frozen=True)
class Reading:
    """One reading of a scenario on one overlay: the records document, and the revision of the
    tree it was staged as. ``document`` is ``None`` when nothing was asked, with ``why``."""

    side: ReadingSide
    revision: str
    document: Mapping[str, Any] | None
    why: str = ""
    #: Taken before development by the baseline step (#3044 2b) and credited here, not played.
    reused: bool = False


class ScenarioRuns:
    """The runtime's way to run a scenario at delivery: its remote-execution port, the operation
    the cycle's record says supplies a scenario, the vocabulary its kept copy holds, and who is
    asking. Any of the first three may be absent, with ``unavailable`` saying why: every reading
    is then absent with that reason."""

    def __init__(
        self,
        port: RemoteExecutionPort | None,
        *,
        operation: SuppliedOperation | None,
        vocabulary: ScenarioVocabulary | None,
        campaign_id: str,
        increment_id: str,
        dispatch_id: str,
        unavailable: str = "",
        stored_baselines: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._port = port
        self._operation = operation
        self._vocabulary = vocabulary
        self._campaign_id = campaign_id
        self._increment_id = increment_id
        self._dispatch_id = dispatch_id
        self._unavailable = unavailable
        self._stored_baselines = stored_baselines or {}

    def scenario(
        self, bundle: VerifierBundle, approved_digest: str | None = None
    ) -> tuple[Scenario | None, str]:
        """The frozen scenario the bundle holds, or ``None`` and why it can't be read: no
        vocabulary kept, a declaration the reader refuses, or (for a new criterion) one whose
        digest isn't the one its change request froze."""
        if self._vocabulary is None:
            return None, self._unavailable or "this cycle keeps no scenario reader's vocabulary"
        [(path, content)] = bundle.files.as_dict().items()
        try:
            scenario = frozen_scenario(json.loads(content), self._vocabulary)
        except (ValueError, ScenarioRefused) as e:
            return None, f"the scenario at {path} can't be read: {e}"
        if approved_digest is not None and scenario.digest != approved_digest:
            return None, (
                f"the scenario at {path} is {scenario.digest}, and its approved change request "
                f"froze {approved_digest}"
            )
        return scenario, ""

    def credited_baseline(
        self, criterion_id: str, overlay: FileTree, scenario: Scenario
    ) -> Reading | None:
        """The baseline step's stored reading of this criterion (#3044 2b), when one is credited
        for this overlay: the frozen digest, the baseline side, and the revision this overlay
        stages as (``baseline_scenario_overlay`` builds the step's from the same rule). ``None``
        when none is, and the baseline is then played here."""
        revision = staged_revision(_staged(overlay)[0])
        for document in self._stored_baselines.get(criterion_id, ()):
            outcomes, _ = credited_outcomes(document, scenario, revision, ReadingSide.BASELINE)
            if outcomes is not None:
                return Reading(ReadingSide.BASELINE, revision, document, reused=True)
        return None

    async def read(
        self,
        criterion_id: str,
        side: ReadingSide,
        overlay: FileTree,
        scenario: Scenario,
    ) -> Reading:
        """``scenario`` played on ``overlay`` for ``side``, as the records document."""
        staged, not_staged = _staged(overlay)
        revision = staged_revision(staged)
        if self._port is None or self._operation is None:
            why = self._unavailable or "this runtime binds no remote execution"
            return Reading(side, revision, None, why)
        operation = self._operation
        request = RemoteOperationRequest(
            contract=operation.contract,
            mode=operation.mode,
            provider=operation.provider,
            operation=operation.operation,
            location=operation.location,
            source_revision=revision,
            source_files=staged,
            scenario=scenario,
            task_id=acceptance_task_id(self._campaign_id, self._increment_id, criterion_id, side),
            dispatch_id=self._dispatch_id,
        )
        result = await self._port.run_operation(request)
        document = records_document(
            request,
            result,
            side,
            not_staged=not_staged,
            skillset=operation.skillset,
            skillset_digest=operation.skillset_digest,
        )
        return Reading(side, revision, document)


def _staged(overlay: FileTree) -> tuple[dict[str, str], tuple[str, ...]]:
    """The overlay's text files, and the paths of every other file (the wire stages text)."""
    staged: dict[str, str] = {}
    left: list[str] = []
    for path, content in overlay.as_dict().items():
        try:
            staged[path] = content.decode("utf-8") if isinstance(content, bytes) else content
        except UnicodeDecodeError:
            left.append(path)
    return staged, tuple(sorted(left))

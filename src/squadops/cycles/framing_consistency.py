"""Manifest↔plan consistency and completeness validation (#1013).

The two framing-internal defect species that cost V38 counted rolls, both invisible
to every prior gate because each artifact was *individually* coherent:

- **Contradiction** (roll 1, ``cyc_02e9af402c82``): the manifest declared
  ``success_status: 201`` for create while the plan's dev criterion said
  *"returns 200"*. The dev built the plan faithfully; the contract judged the
  manifest. Nothing compared the two documents.
- **Omission** (slot 6, ``cyc_cac1e479a462``): the manifest declared join
  ``success_status: 201`` — and the plan never stated it anywhere. The dev
  defaulted to 200; the derived probe enforced 201; three repair rounds and the
  roll died on a fact the implementer was never given. The same class recurred
  as a *shape* omission on the 1.6.1 shakedown (that half is #913's, not ours).

Both checks are pure functions over the two parsed artifacts, deterministic, and
land on the inter-workload plan-validation seam — a rejection there re-rolls
framing for free (#522) instead of spending an implementation run to be caught
at the verdict.

Status semantics mirror the contract deriver EXACTLY (``scaffold_contract``:
collection POST defaults to 201, child-action POST to 200, GET derives no
status probe): the checks compare the plan against what the probes will
*enforce*, not merely what the manifest *declares* — the pf-39 class, where an
undeclared collection-POST status silently becomes an enforced 201, is a
contradiction here the moment the plan says 200.

Deliberately narrow, both directions:

- Only **success-family** tokens (200/201/202/204) participate. Error-status
  teaching (the 409-duplicate story) varies with prose vagueness the window
  showed is not deterministic to judge; extending there is future work, not
  this gate.
- A plan line binds to an endpoint only when it contains a recognizable form of
  that endpoint's **path**. Pathless prose ("create returns 200") is never
  matched — at a rejection gate, a false negative costs a roll we were already
  losing; a false positive rejects a good framing, which is worse.
- A matched line that contains the enforced status among its success tokens is
  consistent, whatever else it mentions — multi-endpoint summary lines must not
  flag on their neighbors' statuses.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.capabilities.scaffold import Endpoint, InterfaceManifest
    from squadops.cycles.implementation_plan import ImplementationPlan

#: Success-family tokens the checks reason about. 3-digit tokens outside this
#: set (400/404/409/422/...) are error vocabulary and never participate.
_SUCCESS_STATUSES = frozenset({200, 201, 202, 204})

_STATUS_TOKEN_RE = re.compile(r"\b(2\d\d)\b")

_METHOD_TOKEN_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b")


def _enforced_success_status(ep: Endpoint) -> int | None:
    """The status the derived contract will actually assert for *ep*.

    Mirrors ``scaffold_contract``'s derivation (collection POST → 201, child
    POST → 200; see the deriver's ``ep.success_status or 201`` /
    ``child.success_status or 200`` sites) — declared wins, defaults follow.
    GETs derive no status probe, so there is nothing to enforce and nothing to
    contradict.
    """
    if ep.method.upper() != "POST":
        return ep.success_status  # declared-only for non-POST; None = unchecked
    if ep.success_status is not None:
        return ep.success_status
    return 201 if "{" not in ep.path else 200


def _path_pattern(path: str) -> re.Pattern[str]:
    """A conservative regex recognizing *path* in plan prose.

    ``{run_id}`` segments match any single non-space segment, so
    ``/api/runs/{run_id}/join``, ``/api/runs/:id/join`` and
    ``/api/runs/[run_id]/join`` prose forms all bind. Literal segments match
    exactly; nothing shorter than the full path binds.
    """
    parts = [seg for seg in path.split("/") if seg]
    rendered = [
        r"[^/\s]+" if seg.startswith("{") and seg.endswith("}") else re.escape(seg) for seg in parts
    ]
    return re.compile("/" + "/".join(rendered) + r"(?![\w/])")


def _plan_text_lines(plan: ImplementationPlan) -> list[str]:
    """Every prose line an implementer's brief is assembled from.

    Task ``focus``/``description`` lines plus string acceptance criteria —
    the same fields the dispatch path renders into dev briefs. TypedCheck
    entries are machine-shaped and excluded; their consistency is the typed
    seam's own concern.
    """
    lines: list[str] = []
    for task in plan.tasks:
        if task.focus:
            lines.extend(task.focus.splitlines())
        if task.description:
            lines.extend(task.description.splitlines())
        for criterion in task.acceptance_criteria:
            if isinstance(criterion, str):
                lines.extend(criterion.splitlines())
    return [ln for ln in (ln.strip() for ln in lines) if ln]


def validate_manifest_plan_consistency(
    manifest: InterfaceManifest,
    plan: ImplementationPlan,
) -> list[str]:
    """The #1013 gate: contradiction and completeness, per endpoint.

    Returns error strings in the plan-validation vocabulary (empty = pass).
    """
    from squadops.capabilities.scaffold import (
        brief_carries_success_status_for,
        skeleton_pins_success_status_for,
    )

    errors: list[str] = []
    lines = _plan_text_lines(plan)
    # The omission half fires only where plan prose is the sole channel carrying the
    # status to the implementer. FastAPI's skeleton pins a declared status in the FROZEN
    # route decorator (pf-39's fix) — the fill inherits it mechanically and prose silence
    # is harmless. The Next.js skeleton writes it only as a TODO comment inside the fill
    # body, which the fill replaces — slot 6 proved the comment does not survive.
    #
    # #1049: there are now TWO deterministic channels and the check must fire only when
    # NEITHER carries the fact. The sentence that stood here — "the typed channel never
    # carries this fact to the implementer in EITHER authoring mode" — was true when
    # written and #1042 made it false: the declared status is threaded onto the dev
    # brief's response surface. Left as-is this check taxed a re-roll per cycle to
    # enforce a prose restatement of a fact that can no longer be forgotten, and its own
    # rejection text ("the implementer will default to 200") had become the false part.
    # Five identical rejections across three cycles, two of them consuming both re-rolls
    # of one cycle, which is a dead-ended run on a framing that was correct.
    #
    # The contradiction half stays active regardless: prose that contradicts the
    # contract misleads the implementer whatever any other channel says.
    status_reaches_implementer = skeleton_pins_success_status_for(
        manifest.stack
    ) or brief_carries_success_status_for(manifest.stack)

    for ep in manifest.api.endpoints:
        enforced = _enforced_success_status(ep)
        if enforced is None:
            continue
        pattern = _path_pattern(ep.path)
        # Method-aware binding: a line naming HTTP methods binds only endpoints
        # whose method it names ("GET /api/runs returns 200" is about the GET,
        # not the collection POST sharing the path). Methodless pathful lines
        # bind by path alone.
        matched_lines = [
            ln
            for ln in lines
            if pattern.search(ln)
            and (not (methods := set(_METHOD_TOKEN_RE.findall(ln))) or ep.method.upper() in methods)
        ]

        stated_anywhere = False
        for ln in matched_lines:
            tokens = {
                int(tok) for tok in _STATUS_TOKEN_RE.findall(ln) if int(tok) in _SUCCESS_STATUSES
            }
            if not tokens:
                continue
            if enforced in tokens:
                stated_anywhere = True
                continue
            errors.append(
                f"manifest↔plan contradiction on {ep.method} {ep.path}: the contract "
                f"will enforce success {enforced} "
                f"({'declared' if ep.success_status is not None else 'derived default'}) "
                f'but the plan states {sorted(tokens)} — "{ln[:120]}". The implementer '
                f"builds the plan; the contract judges the manifest. REMOVE the status "
                f"from the plan: the developer's brief already carries the derived "
                f"status, so the plan restating it adds only the chance of this "
                f"disagreement (#1070)."
            )

        # Completeness: an enforced non-200 success is exactly the fact the dev will
        # not default to — slot 6's roll died on it. It must be STATED in the plan's
        # prose near the endpoint, or the implementer never sees it.
        #
        # #1070 part A: the plan-authoring rule now tells authors NOT to state statuses,
        # which reads as a contradiction with this check and is not one. This fires only
        # where `status_reaches_implementer` is false — a stack whose skeleton does not
        # pin the status AND whose dev capability renders no appendix — and there prose
        # genuinely is the sole carrier, so the specific instruction in this finding
        # correctly overrides the general rule. No REGISTERED stack reaches it today
        # (fastapi pins structurally, nextjs carries the appendix); it is here for the
        # third stack, and its message states what to do.
        if enforced != 200 and not stated_anywhere and not status_reaches_implementer:
            already_contradicted = any(f"on {ep.method} {ep.path}:" in e for e in errors)
            if not already_contradicted:
                errors.append(
                    f"manifest↔plan omission on {ep.method} {ep.path}: the contract will "
                    f"enforce success {enforced} but no plan line states it for this "
                    f"endpoint — the implementer will default to 200 and the probe will "
                    f"reject a faithful build. State the status in the owning task's "
                    f"description or acceptance criteria."
                )

    return errors

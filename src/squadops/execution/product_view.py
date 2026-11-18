"""The repository-backed product a cycle's tools are checked against at creation (SIP-0116 §17n,
#3042).

A provider's authority may rule on the product itself (for a game editor's provider, the product's
eligibility rules).
At creation it's given a ``ProductView``: the tree at the cycle's pinned commit, read once through
the checkout a run is seeded from (``source_checkout.checkout_of`` and ``seeded_files``), so
creation sees what the run would be handed, with the same filter and the same limits. There is no
second tree read.

What it never does is fall back. A product whose tree or ruled change request can't be read refuses
creation, naming why. It is never a view of nothing, nor a cycle with no footprint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.campaigns.change_request import is_scenario_path
from squadops.campaigns.increment_tree import approved_footprint, forwarded_change_request
from squadops.execution.source_checkout import SourceCheckoutRefused, checkout_of, seeded_files
from squadops.ports.tool_authority import ProductView
from squadops.projects.checkout import CheckoutTooLarge
from squadops.projects.models import SourceUnavailable
from squadops.projects.source_context import ProjectSourceContext


class ProductUnreadable(RuntimeError):
    """The cycle's product couldn't be read for its tools' authorities; the message says why."""


class _Bound:
    """A cycle-to-be as ``forwarded_change_request`` reads it: its execution overrides."""

    def __init__(self, execution_overrides: Mapping[str, Any]) -> None:
        self.execution_overrides = execution_overrides


async def product_view(
    context: ProjectSourceContext,
    *,
    execution_overrides: Mapping[str, Any],
    repository: Any,
    registry: Any,
    vault: Any,
) -> ProductView:
    """The product at ``context``'s pinned commit, with the footprint of the change request the
    cycle carries (a repair's or a retry's, in its ``plan_artifact_refs``), or none when it carries
    none yet.

    Raises:
        ProductUnreadable: the tree can't be read as a run would be seeded with it, or the cycle
            carries a change request that can't be read.
    """
    commit = context.pinned_commit
    try:
        tree, manifest = await checkout_of(
            context.project_id, context, repository=repository, registry=registry
        )
    except (SourceUnavailable, SourceCheckoutRefused, CheckoutTooLarge) as e:
        raise ProductUnreadable(
            f"Project {context.project_id}'s tree at {commit} can't be read as a run is seeded "
            f"with it: {e}"
        ) from e
    seeded = {path: content for path, content, _type, _media in seeded_files(tree, manifest)}
    try:
        document = (
            await forwarded_change_request(vault, _Bound(execution_overrides))
            if vault is not None
            else None
        )
    except Exception as e:  # noqa: BLE001 — any failure to read it refuses, naming it
        raise ProductUnreadable(
            f"the change request this cycle carries can't be read: {type(e).__name__}: {e}"
        ) from e
    if document is None and (execution_overrides.get("plan_artifact_refs") and vault is None):
        raise ProductUnreadable("this cycle carries plan artifacts and no vault reads them")

    async def read(path: str) -> str:
        return seeded[path].decode("utf-8", errors="replace")

    return ProductView(
        project_id=context.project_id,
        commit=commit,
        paths=tuple(sorted(seeded)),
        footprint=squad_footprint(document) if document is not None else None,
        _read=read,
    )


def squad_footprint(change_request: str) -> tuple[str, ...]:
    """What the ruled change request lets the squad's change touch: its approved footprint
    without the files the framework itself writes for the increment (#3173).

    A scenario criterion's declaration (``change_request.scenario_criterion_path``, #3044) is in
    the approved footprint so a build may hold it, and the framework lays it from the frozen
    change request. No task writes it and no provider carries it, so a provider's rule about what
    a change may carry is never asked about it. A criterion's own test file stays: the framework
    chooses its path, and the squad's QA writes it."""
    return tuple(p for p in approved_footprint(change_request) if not is_scenario_path(p))

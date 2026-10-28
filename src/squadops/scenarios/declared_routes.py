"""A repository-backed product's client routes, rendered in the sandbox from its declared start, at
its increment's acceptance (SIP-0109 §24co, §24bv point 3, §8.3).

A sample application's routes are rendered in the qa role's container, from its stack's probe and
render profiles (``route_rendering.render_routes``). A product made from a blueprint names its
routes in its derived profile (SIP-0112 H.7's ``client_routes``), and its toolchain exists only in
the sandbox. So the candidate is started there from the product's own start declaration (contract
7), in a disposable copy (X-3b), by the scenario runner (SIP-0113 §4.1), and each route's page is
read by the evaluator image's Chromium, with the flags the qa role reads with. The decision is the
sample application's (``acceptance.route_rendering``): a route renders when its view's root anchor
is on the page.

- **The routes** are the profile's. Their anchors and seeds are the approved manifest's, the one
  the profile's routes were read from (H.7): its routes' test ids, the first of each the view's
  root (#659), and ``increment_tree.route_seeds``.
- **The start** is the Development Configuration's, at the revision the cycle pinned, read as the
  cycle-end hook reads it (``runner.configured_start``).
- **The tree** is the candidate delivery verified: its revision is checked against the one
  delivery cut, or nothing is read (``CandidateNotDelivered``).

What blocks every route, never passing one (SIP-0096), each with contract 7's or SIP-0113 §4.1's
reason: no start declaration, one the runner can't read, a declared evaluation secret (none is
resolved before #2421's approval record), no runner, or a start that failed. A route whose view
declares no anchor is blocked too: nothing on its page could show its view rendered.

Nothing here reads a suite or a scenario's steps: the runner is asked to run none.
"""

from __future__ import annotations

from typing import Any

import yaml

from squadops.campaigns.acceptance import Held, RouteResult, route_rendering
from squadops.campaigns.increment_tree import declared_routes, route_seeds, unseeded_routes
from squadops.campaigns.product_routes import (
    NO_ANCHOR,
    NO_MANIFEST,
    NO_RUNNER,
    NO_START_DECLARATION,
    SECRET_NOT_AVAILABLE,
    START_FAILED,
    ProductRoutes,
    route_record,
    routes_blocked,
)
from squadops.campaigns.runner_acceptance import CandidateNotDelivered, SandboxTree
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    RouteRequest,
    RunnerUnavailable,
    SecretUnavailable,
    StartUndeclared,
    configured_start,
)
from squadops.stacks.scaffold import InterfaceManifest


def _manifest(initialization: Any) -> InterfaceManifest | None:
    if initialization is None:
        return None
    try:
        return InterfaceManifest.from_yaml(initialization.manifest)
    except (ValueError, TypeError, KeyError, yaml.YAMLError):
        return None


def product_start(configuration: Any) -> tuple[DeclaredStart | None, str | None]:
    """The Project's start as the scenario runner runs it (``runner.configured_start``, the
    cycle-end hook's own), or why there is none: contract 7's reasons, and §4.1's for a readiness
    no runner checks. A declared evaluation secret is never resolved before the owner's approval
    record (#2421), so a start that declares one is ``secret not available``."""
    try:
        return configured_start(configuration), None
    except StartUndeclared as e:
        return None, f"{NO_START_DECLARATION}: {e}"
    except SecretUnavailable as e:
        return None, f"{SECRET_NOT_AVAILABLE}: {e}"
    except ReadinessUnsupported as e:
        return None, f"{NO_RUNNER}: {e}"


class DeclaredStartRoutes:
    """Renders a product's client routes on its candidate, started by ``runner`` from the
    product's declaration (a ``campaigns.product_routes.RouteRenderer``). ``runner`` is ``None``
    on a deploy that runs none: every route the profile names then reads ``no runner``."""

    def __init__(self, runner: Any) -> None:
        self._runner = runner

    async def render(
        self,
        *,
        profile: Any,
        configuration: Any,
        initialization: Any,
        candidate: SandboxTree,
        verified_candidate_revision: str | None,
    ) -> ProductRoutes:
        """Each route the profile names, rendered on the candidate started from its declaration,
        and judged as a sample application's is (§8.3). A profile that names none has no routes:
        not applicable (§24bv point 3).

        Raises:
            CandidateNotDelivered: The candidate's content isn't the revision delivery verified.
        """
        named = tuple(profile.client_routes or ())
        if not named:
            return ProductRoutes((), None)
        manifest = _manifest(initialization)
        if manifest is None:
            return routes_blocked(named, NO_MANIFEST)
        anchors = {r: declared_routes(manifest).get(r, ()) for r in named}
        seeds = {r: s for r, s in route_seeds(manifest).items() if r in anchors}
        start, unstartable = product_start(configuration)
        if unstartable is not None or start is None:
            return routes_blocked(named, unstartable or NO_START_DECLARATION)
        if self._runner is None:
            return routes_blocked(named, f"{NO_RUNNER}: this runtime runs no scenario runner")
        # deferred (pair): squadops.sandbox imports campaigns at load, as runner_acceptance's do
        from squadops.sandbox.models import compute_revision_id

        content = candidate.content
        executable = candidate.executable & content.keys()
        revision = compute_revision_id(content, executable)
        if verified_candidate_revision is not None and revision != verified_candidate_revision:
            raise CandidateNotDelivered(
                f"the candidate's content is revision {revision}, and delivery verified "
                f"{verified_candidate_revision}: the routes would be read on another tree"
            )
        identity = candidate.file_tree.identity
        try:
            evaluation = await self._runner.evaluate_tree(
                tree=content,
                tree_identity=identity,
                executable=sorted(executable),
                stack=None,
                declared=start,
                scenarios=[],
                environment={},
                pages=[],
                routes=[RouteRequest(r, seeds.get(r)) for r in named],
            )
        except RunnerUnavailable as e:
            return routes_blocked(named, f"{NO_RUNNER}: {e}")
        started = {
            "tree_identity": identity,
            "configuration_revision": configuration.revision,
            "started": evaluation.started,
            "detail": evaluation.start_detail,
        }
        if not evaluation.started:
            return routes_blocked(named, f"{START_FAILED}: {evaluation.start_detail}", started)
        read = {r.route: r for r in evaluation.routes}
        judged = {
            r.path: r
            for r in route_rendering(
                {r: a for r, a in anchors.items() if a},
                {r: read[r].testids if r in read else None for r in named},
                unseeded=unseeded_routes(named, seeds),
            )
        }
        results = []
        for route in sorted(named):
            if not anchors[route]:
                results.append(RouteResult(route, Held.BLOCKED_UNVERIFIED, detail=NO_ANCHOR))
                continue
            result = judged[route]
            if result.held is Held.BLOCKED_UNVERIFIED and not result.unseeded:
                reading = read.get(route)
                why = (
                    reading.detail
                    if reading is not None and reading.detail
                    else "the runner returned no reading of it"
                )
                result = RouteResult(route, result.held, detail=why)
            results.append(result)
        return ProductRoutes(tuple(results), route_record(results, anchors, read, started))


__all__ = ["DeclaredStartRoutes", "product_start"]

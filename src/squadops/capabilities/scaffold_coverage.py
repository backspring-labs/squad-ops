"""What the deterministic layer actually covers, per manifest (#951).

The verification scaffold covers a **derived subset** of the behaviours a manifest
declares. That is a defensible engineering constraint — a probe cannot be synthesized
for every shape without inventing request values a correct application would reject.
The defect is that the difference was never recorded, so **silence read as coverage.**

Window roll 2 (``cyc_2f63e2d841eb``) banked green with join and leave — the entire
point of the application — untouched by every deterministic layer: five scaffold slots
covering create, blank-rejection, list, detail and detail-404; two probes, both
``POST /api/runs``; a boot audit that fires those same two probes. The feature was
verified only by a freely-authored additive suite, which happened to be a good one.
Nothing required that and nothing would have reported its absence.

The scaffold's coverage is defined by **what it can derive**, not by what the manifest
**declares**. This module makes that gap legible: for every declared endpoint, whether
a probe and/or a scaffold slot reaches it.

Deliberately a *report*, not a gate. Whether an uncovered endpoint should block is a
separate ruling (SIP-0096 already has ``blocked_unverified`` if it should); being
**recorded** should not wait on that decision. It is also read-only with respect to
emission: no shell byte changes, so SIP-0104's Gate 1 pins and ``GENERATOR_VERSION``
are untouched by adding it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from squadops.capabilities.scaffold import InterfaceManifest

#: A probe's path carries capture placeholders (``/api/runs/{created_id}/join``) while the
#: manifest declares its own parameter names (``/api/runs/{run_id}/join``). Coverage is a
#: question about the route, not about whose name for the parameter won, so both sides are
#: reduced to the same shape before comparison.
_PARAM = re.compile(r"\{\w*\}")


def _route_key(method: str, path: str) -> tuple[str, str]:
    return method.upper(), _PARAM.sub("{}", path)


@dataclass(frozen=True)
class EndpointCoverage:
    """One declared endpoint and the deterministic layers that reach it."""

    method: str
    path: str
    probe_ids: tuple[str, ...] = ()
    slot_ids: tuple[str, ...] = ()

    @property
    def covered(self) -> bool:
        return bool(self.probe_ids or self.slot_ids)

    def describe(self) -> str:
        if not self.covered:
            return f"{self.method} {self.path}: NO deterministic coverage"
        layers = []
        if self.slot_ids:
            layers.append(f"{len(self.slot_ids)} slot(s)")
        if self.probe_ids:
            layers.append(f"{len(self.probe_ids)} probe(s)")
        return f"{self.method} {self.path}: {', '.join(layers)}"


@dataclass(frozen=True)
class ScaffoldCoverage:
    """The per-manifest delta between what was declared and what is verified."""

    endpoints: tuple[EndpointCoverage, ...]

    @property
    def declared(self) -> int:
        return len(self.endpoints)

    @property
    def covered(self) -> tuple[EndpointCoverage, ...]:
        return tuple(e for e in self.endpoints if e.covered)

    @property
    def uncovered(self) -> tuple[EndpointCoverage, ...]:
        return tuple(e for e in self.endpoints if not e.covered)

    def summary(self) -> str:
        """One line for the log, naming the uncovered routes rather than counting them.

        A count invites the reading "3 of 4, close enough". The names invite the only
        question worth asking, which is whether the one left out is the feature.
        """
        n = len(self.covered)
        if not self.uncovered:
            return f"scaffold coverage: {n}/{self.declared} declared endpoints, none uncovered"
        missing = ", ".join(f"{e.method} {e.path}" for e in self.uncovered)
        return (
            f"scaffold coverage: {n}/{self.declared} declared endpoints; "
            f"NO deterministic coverage for {missing}"
        )

    def as_dict(self) -> dict:
        """Evidence shape — banked so the delta is recoverable after the fact."""
        return {
            "declared": self.declared,
            "covered": len(self.covered),
            "uncovered": [{"method": e.method, "path": e.path} for e in self.uncovered],
            "endpoints": [
                {
                    "method": e.method,
                    "path": e.path,
                    "probe_ids": list(e.probe_ids),
                    "slot_ids": list(e.slot_ids),
                }
                for e in self.endpoints
            ],
        }


def summarize_coverage(
    declared: Sequence[tuple[str, str]],
    probe_routes: Sequence[tuple[str, str, str]],
    slot_routes: Sequence[tuple[str, str, str]],
) -> ScaffoldCoverage:
    """Map declared ``(method, path)`` routes to the probe and slot ids that reach them.

    Takes routes rather than a manifest so it stays stack-neutral: a second scaffold
    stack derives its behaviours its own way and reports through the same function,
    the way ``_EMITTERS`` keeps emission itself stack-neutral. Declaration order is
    preserved, so the report reads in the order of the manifest it is about.
    """
    by_probe: dict[tuple[str, str], list[str]] = {}
    for method, path, probe_id in probe_routes:
        by_probe.setdefault(_route_key(method, path), []).append(probe_id)

    by_slot: dict[tuple[str, str], list[str]] = {}
    for method, path, slot_id in slot_routes:
        by_slot.setdefault(_route_key(method, path), []).append(slot_id)

    return ScaffoldCoverage(
        endpoints=tuple(
            EndpointCoverage(
                method=method,
                path=path,
                probe_ids=tuple(by_probe.get(_route_key(method, path), ())),
                slot_ids=tuple(by_slot.get(_route_key(method, path), ())),
            )
            for method, path in declared
        )
    )


def derive_scaffold_coverage(manifest: InterfaceManifest) -> ScaffoldCoverage:
    """Coverage for a manifest, deriving the behaviours the emitter would emit.

    The convenience form, for tooling and tests. The emitter itself calls
    ``summarize_coverage`` directly with the behaviours it already holds rather than
    paying for a second derivation.
    """
    from squadops.capabilities.stack_nextjs_ts_tests import derive_scaffold_behaviors

    behaviors, probes = derive_scaffold_behaviors(manifest)
    return summarize_coverage(
        [(ep.method, ep.path) for ep in manifest.api.endpoints],
        probe_routes(probes),
        slot_routes(behaviors),
    )


def probe_routes(probes: Sequence[dict]) -> list[tuple[str, str, str]]:
    """``(method, path, probe_id)`` for each derived probe."""
    rows = []
    for probe in probes:
        request = probe.get("request", {})
        rows.append(
            (
                str(request.get("method", "GET")),
                str(request.get("path", "")),
                str(probe.get("id", "")),
            )
        )
    return rows


def slot_routes(behaviors: Sequence) -> list[tuple[str, str, str]]:
    """``(method, path, slot_id)`` for each emitted behaviour.

    The **final** step is what a behaviour asserts on. Prerequisites are setup — a
    create replayed in order to reach a join is not coverage of the create, and
    counting it would inflate exactly the number this report exists to deflate.
    """
    return [(b.final.method, b.final.url_path, f"slot-{b.behavior_id}") for b in behaviors]

"""A failed or blocked page step's evidence (SIP-0113 §10p ruling 8; #2564 build step 4).

The browser keeps it for the first step or check of a segment that didn't end as it should
(``infra/evaluator/browser.mjs``): a viewport screenshot, the target role's nodes and their names,
the page's errors (the driver's own failure first), and its failed requests. A screenshot of a
filled form shows a step's values, so the evidence is held out like the steps: kept in the scenario
store's own table, read under ``scenarios:approve`` alone, and never in an outcome, a detail, the
artifact vault or a package.

Pure: the sandbox caps and redacts it before it leaves (``kept``), and the store keeps what
arrives.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

#: §10p ruling 8's caps.
SCENARIO_CAP = 512 * 1024
EVALUATION_CAP = 4 * 1024 * 1024


@dataclass(frozen=True)
class ScenarioEvidence:
    """One scenario's evidence, for the step it names. ``withheld`` says what was dropped, and
    why: a screenshot an evaluation's secret could show, or one over a cap."""

    scenario_id: str
    step: int
    screenshot: bytes | None = None
    role: str | None = None
    nodes: tuple[Mapping[str, Any], ...] = ()
    errors: tuple[str, ...] = ()
    failed_requests: tuple[str, ...] = ()
    withheld: tuple[str, ...] = field(default=())

    def details(self) -> dict[str, Any]:
        """Everything but the screenshot, as stored beside it."""
        return {
            "role": self.role,
            "nodes": [dict(n) for n in self.nodes],
            "errors": list(self.errors),
            "failed_requests": list(self.failed_requests),
            "withheld": list(self.withheld),
        }

    @property
    def size(self) -> int:
        return len(self.screenshot or b"") + len(_canonical(self.details()))

    @property
    def sha256(self) -> str:
        digest = hashlib.sha256(self.screenshot or b"")
        digest.update(_canonical(self.details()))
        return digest.hexdigest()

    def to_wire(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "png_b64": base64.b64encode(self.screenshot).decode() if self.screenshot else None,
            **self.details(),
        }

    @classmethod
    def from_wire(cls, scenario_id: str, d: Mapping[str, Any]) -> ScenarioEvidence:
        """The evidence a run carries: the sandbox's, or the browser's own (the same shape, with
        no ``withheld``). A screenshot that isn't base64 is withheld, never guessed at."""
        withheld = tuple(d.get("withheld") or ())
        screenshot = None
        if d.get("png_b64"):
            try:
                screenshot = base64.b64decode(d["png_b64"], validate=True)
            except (binascii.Error, ValueError):
                withheld = (*withheld, "screenshot: not base64")
        return cls(
            scenario_id=scenario_id,
            step=int(d["step"]),
            screenshot=screenshot,
            role=d.get("role"),
            nodes=tuple(dict(n) for n in d.get("nodes") or ()),
            errors=tuple(str(e) for e in d.get("errors") or ()),
            failed_requests=tuple(str(r) for r in d.get("failed_requests") or ()),
            withheld=withheld,
        )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def kept(
    items: Sequence[ScenarioEvidence],
    *,
    scrub: Callable[[str], str],
    secret_resolved: bool,
) -> tuple[ScenarioEvidence, ...]:
    """What leaves the sandbox: each item's text scrubbed of the evaluation's secrets (``scrub``),
    no screenshot when the evaluation resolved a secret (Q40: a secret is never written to a
    record, and a page can show one), and the caps: an item over its scenario's cap loses its
    screenshot, then its nodes, and once the evaluation's cap is reached, later items keep their
    text and lose their screenshots."""
    out: list[ScenarioEvidence] = []
    total = 0
    for item in items:
        item = replace(
            item,
            nodes=tuple(
                {k: scrub(v) if isinstance(v, str) else v for k, v in n.items()} for n in item.nodes
            ),
            errors=tuple(scrub(e) for e in item.errors),
            failed_requests=tuple(scrub(r) for r in item.failed_requests),
        )
        if secret_resolved and item.screenshot is not None:
            item = _without_screenshot(item, "screenshot: the evaluation resolved a secret")
        if item.size > SCENARIO_CAP and item.screenshot is not None:
            item = _without_screenshot(item, "screenshot: over the scenario's cap")
        if item.size > SCENARIO_CAP:
            item = replace(
                item, nodes=(), withheld=(*item.withheld, "nodes: over the scenario's cap")
            )
        if total + item.size > EVALUATION_CAP and item.screenshot is not None:
            item = _without_screenshot(item, "screenshot: over the evaluation's cap")
        total += item.size
        out.append(item)
    return tuple(out)


def _without_screenshot(item: ScenarioEvidence, why: str) -> ScenarioEvidence:
    return replace(item, screenshot=None, withheld=(*item.withheld, why))

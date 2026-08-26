"""The fill-mode brief — one composition seam for every qa-role dispatch (#969).

``qa.test`` (initial authoring), its self-eval pass (#947) and ``qa.test_repair`` (#970)
all author against the same frozen scaffold, so they read one description of the slot
protocol, the store vocabulary, the error envelope and the in-process execution model.
#969 counted three instances of a protocol taught to the primary path while a sibling
path silently kept the old behaviour; the answer to its question — a fourth appendix, or
one seam — is this module. Every instruction lives in the managed assets (#448); the
functions here derive the data the assets render.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

FILL_MODE_TEMPLATE = "request.qa_test_fill_mode_appendix"
SELF_EVAL_FILL_TEMPLATE = "request.qa_test_self_eval_fill_appendix"
REPAIR_FILL_TEMPLATE = "request.qa_test_repair_fill_appendix"


async def render_fill_mode_section(
    renderer: Any, scaffold_input: dict[str, Any] | None, additive_files: Sequence[str] | None
) -> str:
    """The FILL MODE block for a scaffold-carrying envelope, or "".

    SIP-0104 §4.5: the author receives the shells (read-only) and the coverage
    inventory — data derived from the slot table by the fill module. Coverage
    inventory only: no generated coaching (SIP §12 keeps richer briefs as follow-on).
    """
    scaffold_input = scaffold_input or {}
    manifest_dict = scaffold_input.get("manifest")
    files = scaffold_input.get("files") or []
    if renderer is None or not manifest_dict or not files:
        return ""
    from squadops.capabilities.scaffold import error_envelope_lines
    from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
    from squadops.capabilities.verification_scaffold_fill import coverage_inventory_lines

    record = VerificationScaffoldManifest.from_dict(manifest_dict)
    slot_lines = "\n".join(f"- {line}" for line in coverage_inventory_lines(record))
    shell_parts = [f"**{f['name']}:**\n```typescript\n{f['content']}\n```" for f in files]
    # #911: half the slots are error behaviors and nothing showed the author the
    # envelope, so it invented `body.error_code` on two consecutive window rolls.
    # Keyed on the scaffold record's own stack — the fact is the stack's, not the run's.
    envelope = "\n".join(f"- {line}" for line in error_envelope_lines(record.stack))
    # #933: the plan's authored deliverable, reframed as additive by the asset that
    # owns the emission contract.
    additive = "\n".join(f"- `{f}`" for f in (additive_files or []))
    rendered = await renderer.render(
        FILL_MODE_TEMPLATE,
        {
            "slot_lines": slot_lines,
            "shell_files": "\n\n".join(shell_parts),
            "error_envelope": envelope,
            "additive_files": additive,
        },
    )
    return rendered.content


def _disposition_lines(
    dispositions: Sequence[dict[str, Any]], *, exclude: str | None = "filled"
) -> list[str]:
    return [
        f"- `{d['slot_id']}` — {d['disposition']}" + (f": {d['detail']}" if d.get("detail") else "")
        for d in dispositions
        if d.get("disposition") != exclude
    ]


async def render_self_eval_fill_section(
    renderer: Any, fill_merge_evidence: dict[str, Any] | None
) -> str:
    """The fill-mode addendum to the self-eval prompt (#947), or "".

    Names the slots whose disposition is not ``filled`` — data from the merge record.
    """
    if renderer is None:
        return ""
    unfilled = _disposition_lines((fill_merge_evidence or {}).get("dispositions", []))
    rendered = await renderer.render(
        SELF_EVAL_FILL_TEMPLATE, {"unfilled_slot_lines": "\n".join(unfilled) or "(none)"}
    )
    return rendered.content


async def render_repair_fill_section(
    renderer: Any, repair_slots: Sequence[dict[str, Any]] | None
) -> str:
    """The fill-mode addendum to a qa repair prompt (#970), or "".

    Names the slots whose fills failed (the runner threads them from the scaffold
    evidence's fill-layer observations) with the runner's own failure detail.
    """
    if renderer is None or not repair_slots:
        return ""
    lines = [
        f"- `{r['slot_id']}` in `{r.get('file', '')}`"
        + (f" — {r['detail']}" if r.get("detail") else "")
        for r in repair_slots
        if r.get("slot_id")
    ]
    if not lines:
        return ""
    rendered = await renderer.render(REPAIR_FILL_TEMPLATE, {"failed_slot_lines": "\n".join(lines)})
    return rendered.content

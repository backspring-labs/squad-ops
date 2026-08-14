"""The fill protocol — SIP-0104 P3, the bounded agent surface (Gate 3).

This module is the **merge contract**, defined before any consumer exists (the plan's P3
ordering rule — otherwise the fill layer becomes another mini code-generation pipeline):
what a fill IS, how it is addressed, what it may contain, and how it merges. The qa
author's entire mechanical surface in fill mode is what this module accepts.

## Addressing (normative)

**Slot id is the only addressing mechanism.** A fill is emitted as a fenced block whose
info string names the slot::

    ```fill:slot-vc-probe-api-runs
        expect(body.id).toBeTruthy()
        expect(all('runs')).toHaveLength(1)
    ```

No file paths, no line numbers, no diffs. One fill per slot; a slot filled twice is
rejected (both occurrences — picking a winner would make the emission's meaning depend on
ordering the author never sees). A fill addressing a slot the scaffold does not declare is
rejected as misaddressed. The **explicit not-applicable disposition** is a directive body::

    ```fill:slot-vs-get-api-runs
    not_applicable: the status assertion fully covers this behavior; no state to assert
    ```

## Containment (normative — SIP §4.5's "a bad fill degrades one slot, not the suite")

A fill body may contain domain assertions and nothing structural:

- **no slot-marker vocabulary** — a body mentioning ``[scaffold-slot:`` could forge or
  terminate regions and escape its slot;
- **no imports or dependency loads** — ``import``/``require(`` belong to the frozen spine
  (SIP §4.2); a fill needing a symbol the spine does not import is asking to widen the
  spine, which is a scaffold change, not a fill;
- **no live-server access** — ``fetch(``/``XMLHttpRequest``/``WebSocket`` are the #877
  class the execution model prohibits;
- **bounded size** — a runaway emission must not bloat one slot into a de facto file.

Validation findings are deterministic rejections: cheaper than a qa repair round, and a
rejected fill degrades exactly its own slot (the merge renders the slot as a failing
state; ``merge`` module section below).

## Merge semantics (normative)

Merge replaces slot *bodies* only, in scaffold order, deterministically: same scaffold +
same fills ⇒ byte-identical output, and the merged file's **spine hash must equal the
scaffold's** — containment is verified, not assumed. Per-slot dispositions:

- ``filled`` — a valid fill's body lines replace the seed body verbatim;
- ``not_applicable`` — recorded with its reason; the body becomes a comment carrying it;
- ``rejected`` — a containment/duplicate violation; recorded with the finding;
- ``missing`` — no fill and no disposition.

**A missing or rejected required slot is never silent success**: its body becomes a
deterministic failing assertion naming the slot and the fill layer, shaped as an
``expect().toBe`` mismatch so the execution gate classifies it as an assertion failure
(the fill layer's failing state), never as a mechanical crash (the generator's).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from squadops.capabilities.verification_scaffold import (
    ScaffoldValidationError,
    VerificationScaffoldManifest,
    parse_slot_regions,
    spine_hash,
)

#: Size bounds for one fill body. Generous for domain assertions, prohibitive for a file.
MAX_FILL_LINES = 120
MAX_FILL_BYTES = 8_000

_FILL_FENCE_RE = re.compile(
    r"^```fill:(?P<slot_id>slot-[a-z0-9][a-z0-9-]*)[ \t]*\n(?P<body>.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
_NOT_APPLICABLE_RE = re.compile(r"^\s*not_applicable:\s*(?P<reason>\S.*)$")
_IMPORT_RE = re.compile(r"^\s*import\s", re.MULTILINE)

#: Disposition vocabulary (the P5 evidence layer consumes these).
DISPOSITION_FILLED = "filled"
DISPOSITION_NOT_APPLICABLE = "not_applicable"
DISPOSITION_REJECTED = "rejected"
DISPOSITION_MISSING = "missing"


@dataclass(frozen=True)
class Fill:
    """One parsed fill block: a body for its slot, or an explicit NA disposition."""

    slot_id: str
    body: str = ""
    not_applicable_reason: str = ""

    @property
    def is_not_applicable(self) -> bool:
        return bool(self.not_applicable_reason)


@dataclass(frozen=True)
class FillEmission:
    """Everything fill-shaped in one authored emission, plus what was malformed."""

    fills: tuple[Fill, ...] = ()
    #: slot ids that appeared in more than one fill block (all occurrences rejected).
    duplicates: tuple[str, ...] = ()


def parse_fill_emission(text: str) -> FillEmission:
    """Extract fill blocks from an authored emission.

    Only ``fill:slot-…`` fences are this protocol's; everything else (additive test
    files as ordinary path-addressed fences, prose) is deliberately left for the
    existing emission pipeline — the two surfaces must not compete for the same bytes.
    """
    fills: list[Fill] = []
    seen: dict[str, int] = {}
    for match in _FILL_FENCE_RE.finditer(text):
        slot_id = match.group("slot_id")
        body = match.group("body")
        seen[slot_id] = seen.get(slot_id, 0) + 1
        stripped = [line for line in body.strip("\n").split("\n") if line.strip()]
        na = _NOT_APPLICABLE_RE.match(stripped[0]) if len(stripped) == 1 else None
        if na:
            fills.append(Fill(slot_id=slot_id, not_applicable_reason=na.group("reason").strip()))
        else:
            fills.append(Fill(slot_id=slot_id, body=body.strip("\n")))
    duplicates = tuple(sorted(slot_id for slot_id, count in seen.items() if count > 1))
    return FillEmission(fills=tuple(fills), duplicates=duplicates)


#: ``(pattern, human reason)`` — each is a containment rule from the module docstring.
_FORBIDDEN: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(re.escape("[scaffold-slot:")),
        "mentions the slot-marker vocabulary — a fill must not forge or terminate regions",
    ),
    (
        _IMPORT_RE,
        "contains an import — imports belong to the frozen spine (SIP-0104 §4.2); a fill "
        "needing a new symbol is a scaffold change, not a fill",
    ),
    (
        re.compile(r"\brequire\("),
        "loads a dependency with require() — dependencies belong to the frozen spine",
    ),
    (
        re.compile(r"\bfetch\("),
        "calls fetch() — no live-server access in the in-process execution model (#877)",
    ),
    (
        re.compile(r"\bXMLHttpRequest\b"),
        "uses XMLHttpRequest — no live-server access (#877)",
    ),
    (
        re.compile(r"\bWebSocket\b"),
        "uses WebSocket — no live-server access (#877)",
    ),
)


def fill_findings(fill: Fill) -> list[str]:
    """Every containment rule this fill violates; empty for a valid fill or explicit NA."""
    if fill.is_not_applicable:
        return []
    if not fill.body.strip():
        return [
            "empty fill body — supply domain assertions, or declare "
            "`not_applicable: <reason>` explicitly; an empty fill is silent non-coverage"
        ]
    findings: list[str] = []
    lines = fill.body.split("\n")
    if len(lines) > MAX_FILL_LINES or len(fill.body.encode("utf-8")) > MAX_FILL_BYTES:
        findings.append(
            f"oversized ({len(lines)} lines / {len(fill.body.encode('utf-8'))} bytes; "
            f"bounds {MAX_FILL_LINES} lines / {MAX_FILL_BYTES} bytes) — a fill is domain "
            f"assertions, not a file"
        )
    for pattern, reason in _FORBIDDEN:
        if pattern.search(fill.body):
            findings.append(reason)
    return findings


@dataclass(frozen=True)
class SlotDisposition:
    """What happened to one slot at merge time — the fill layer's per-slot evidence."""

    slot_id: str
    disposition: str
    detail: str = ""


@dataclass(frozen=True)
class MergedFile:
    path: str
    content: str
    content_hash: str
    spine_hash: str


@dataclass(frozen=True)
class FillMergeRecord:
    """The merge's evidence: merged bytes pinned, every slot's disposition explicit."""

    files: tuple[MergedFile, ...] = ()
    dispositions: tuple[SlotDisposition, ...] = ()
    #: fills addressing slot ids the scaffold does not declare (nothing to degrade —
    #: recorded so a misaddressed fill is visible, not silently dropped).
    misaddressed: tuple[SlotDisposition, ...] = ()

    def disposition_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.dispositions:
            counts[d.disposition] = counts.get(d.disposition, 0) + 1
        return counts

    def by_slot(self) -> dict[str, SlotDisposition]:
        return {d.slot_id: d for d in self.dispositions}


def _failing_state(slot_id: str, why: str) -> list[str]:
    """The deterministic failing assertion for a missing/rejected slot.

    Shaped as an expect().toBe mismatch so the execution gate (P2) classifies it as an
    assertion failure attributed to the FILL layer — never a mechanical crash, which
    would misattribute it to the generator.
    """
    safe = why.replace("\\", "").replace("'", "")
    return [
        f"    // fill layer: {safe}",
        f"    expect('fill layer: {slot_id}: {safe}').toBe('a valid fill or an explicit "
        f"not_applicable disposition')",
    ]


def _merged_body(
    slot_id: str, fill: Fill | None, findings: list[str]
) -> tuple[list[str], SlotDisposition]:
    if fill is None:
        return (
            _failing_state(slot_id, "no fill and no disposition received"),
            SlotDisposition(slot_id, DISPOSITION_MISSING, "no fill and no disposition"),
        )
    if findings:
        detail = "; ".join(findings)
        return (
            _failing_state(slot_id, f"fill rejected: {detail}"),
            SlotDisposition(slot_id, DISPOSITION_REJECTED, detail),
        )
    if fill.is_not_applicable:
        return (
            [f"    // not_applicable (qa): {fill.not_applicable_reason}"],
            SlotDisposition(slot_id, DISPOSITION_NOT_APPLICABLE, fill.not_applicable_reason),
        )
    return (
        fill.body.split("\n"),
        SlotDisposition(slot_id, DISPOSITION_FILLED, ""),
    )


def merge_fills(
    scaffold_files: list[dict[str, str]],
    record: VerificationScaffoldManifest,
    emission: FillEmission,
) -> FillMergeRecord:
    """Merge an authored fill emission into the scaffold, deterministically.

    Slot-body replacement only, in scaffold order. Every declared slot ends in exactly
    one disposition; the merged spine is re-hashed and must equal the scaffold record's —
    containment is *verified* on every merge, never assumed (a violation here is a bug in
    this module, raised as ``AssertionError`` rather than shipped).
    """
    from squadops.capabilities.verification_scaffold import _sha256

    declared = {slot.slot_id for f in record.files for slot in f.slots}
    duplicate_set = set(emission.duplicates)
    fills_by_slot = {f.slot_id: f for f in emission.fills if f.slot_id not in duplicate_set}
    misaddressed = tuple(
        SlotDisposition(
            f.slot_id,
            DISPOSITION_REJECTED,
            "addresses a slot the scaffold does not declare",
        )
        for f in emission.fills
        if f.slot_id not in declared
    )

    scaffold_by_path = {f["name"]: f["content"] for f in scaffold_files}
    merged_files: list[MergedFile] = []
    dispositions: list[SlotDisposition] = []
    for file_record in record.files:
        content = scaffold_by_path[file_record.path]
        lines = content.split("\n")
        regions = {r.slot_id: r for r in parse_slot_regions(content)}
        out: list[str] = []
        cursor = 1
        for slot in sorted(file_record.slots, key=lambda s: regions[s.slot_id].begin_line):
            region = regions[slot.slot_id]
            out.extend(lines[cursor - 1 : region.begin_line])
            if slot.slot_id in duplicate_set:
                body, disposition = (
                    _failing_state(slot.slot_id, "fill rejected: slot filled more than once"),
                    SlotDisposition(
                        slot.slot_id,
                        DISPOSITION_REJECTED,
                        "slot filled more than once — one fill per slot",
                    ),
                )
            else:
                fill = fills_by_slot.get(slot.slot_id)
                body, disposition = _merged_body(
                    slot.slot_id, fill, fill_findings(fill) if fill else []
                )
            out.extend(body)
            out.append(lines[region.end_line - 1])
            cursor = region.end_line + 1
            dispositions.append(disposition)
        out.extend(lines[cursor - 1 :])
        merged = "\n".join(out)
        merged_spine = spine_hash(merged)
        if merged_spine != file_record.spine_hash:
            raise ScaffoldValidationError(
                f"{file_record.path}: merge moved the spine "
                f"({merged_spine} != {file_record.spine_hash}) — a defect in merge_fills "
                f"itself; the merged output must not become the run's qa artifact"
            )
        merged_files.append(
            MergedFile(
                path=file_record.path,
                content=merged,
                content_hash=_sha256(merged),
                spine_hash=merged_spine,
            )
        )
    return FillMergeRecord(
        files=tuple(merged_files),
        dispositions=tuple(dispositions),
        misaddressed=misaddressed,
    )


def strip_fill_blocks(text: str) -> str:
    """The emission with every fill fence removed — what the file extractor may see.

    The fenced-file parser reads ``<language>:<path>`` info strings, so a ``fill:slot-…``
    fence left in place would extract as a file named ``slot-…`` and the protocol's blocks
    would compete with the additive-file surface for the same bytes.
    """
    return _FILL_FENCE_RE.sub("", text)


def coverage_inventory_lines(record: VerificationScaffoldManifest) -> list[str]:
    """The deterministic layer's coverage, one line per slot — the semantic brief's data.

    Coverage inventory ONLY (SIP §4.5): what is already covered, derived from the slot
    table. No generated coaching, no semantic planning — the instruction prose around
    these lines is a managed prompt asset (#448), and richer inference-generated briefs
    are named follow-on work (SIP §12).
    """
    lines: list[str] = []
    for file_record in record.files:
        for slot in file_record.slots:
            bound = f" (mirrors probe {slot.probe_id})" if slot.probe_id else ""
            lines.append(f"{slot.slot_id} — {slot.behavior}{bound}")
    return lines

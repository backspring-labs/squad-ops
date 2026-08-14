"""The test-scaffold contract — SIP-0104 Phase 1, the artifact's definition (not its generator).

This module is the **scaffold contract**: the schema of the test-scaffold manifest, the slot
marker grammar, the frozen-spine hash canonicalization, and the derivation-source precedence.
It deliberately lands before any emission code exists, so the generator is written *against*
a contract rather than becoming the de facto specification (the SIP-0104 plan's Phase 1
ordering rule).

Placement: capabilities, beside ``scaffold_contract`` — the emission surface. The cycles
domain (region enforcement, P4; evidence, P5) imports *this* module for the canonicalization,
the same direction ``bound_scaffold_record`` already imports ``scaffold``. Nothing here
imports the cycles domain.

## Vocabulary

- **Behavior shell**: one deterministic unit of required coverage — the invocation mechanics
  and contract-derived status assertion for one behavior, pre-written and frozen (SIP §4.1).
- **Fill slot**: the single mutable region inside a shell, delimited by slot markers, where
  the qa author supplies domain assertions. Distinct from the dev-side ``fill_slots`` of
  ``ScaffoldStack`` (whole files a dev fills); a test-scaffold slot is a *region*.
- **Spine**: everything in a scaffold file that is not a slot body — including the marker
  lines themselves. The spine is frozen; slot bodies are mutable.

## Slot marker grammar (normative)

A slot is delimited by two full lines (leading whitespace permitted, nothing else on the
line)::

    // [scaffold-slot:begin slot-<id>]
    ... mutable body lines ...
    // [scaffold-slot:end slot-<id>]

``slot-<id>`` must match ``slot-[a-z0-9][a-z0-9-]*``. Structure rules, enforced by
:func:`parse_slot_regions`: begin/end ids must match; no nesting; no duplicate slot id in a
file (cross-file uniqueness is :meth:`VerificationScaffoldManifest.lint`'s job); no unclosed region.
A line that *mentions* ``[scaffold-slot:`` without being a well-formed marker is an error,
not spine text — a typo'd marker silently frozen into the spine would freeze the author's
slot shut.

## Frozen-spine hash canonicalization (normative)

1. Scaffold files are UTF-8 with ``\\n`` newlines only; a CRLF rewrite is a spine mutation.
2. A slot *body* is the lines strictly between a begin marker line and its end marker line.
3. The spine text is the file's lines with every slot body's lines removed, all other lines
   (markers included) kept verbatim in order, joined with ``\\n``.
4. ``spine_hash`` is the SHA-256 hex digest of the spine text encoded as UTF-8.
5. A file whose slot structure does not parse has **no** spine hash — malformed structure is
   a violation in itself, never hashed around.

Consequence: editing a slot body never moves the spine hash; moving/removing a marker,
enlarging a region, injecting a statement outside a slot, or editing an import all do. This
is the v1 hash-sufficiency mechanism; AST-level verification is the named escalation on
evidence that the adversarial corpus (P4) shows hashing misses (SIP §4.3).

## Derivation-source precedence (normative)

Every frozen element derives from authoritative facts in this precedence::

    interface manifest  →  criteria pack  →  expanded tree

The generator never reconciles a disagreement between sources by inference: a manifest that
declares a behavior whose implementation surface the expanded tree lacks fails generation as
a :class:`ScaffoldDerivationError` naming both sides (SIP §7). An element no source can
derive is demoted to fill content, never frozen as a guess (SIP §4.1, #874).

## Attribution (why the manifest carries what it carries)

A later hash mismatch must be attributable, not just detectable (plan §P1). The manifest
therefore records the structural facts diagnosis needs: ``generator_version`` +
``interface_manifest_hash`` (regenerate and compare → **generator drift**),
``expanded_tree_hash`` (the tree imports were resolved against → **workspace mutation**),
and per-file ``content_hash``/``spine_hash`` with slot region bounds (stored emission vs.
record → **producer edit**, and *which region*).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

#: Schema version of the test-scaffold manifest this module defines. Bumped when the
#: manifest's shape changes; the generator's own version lives with the generator.
SCAFFOLD_MANIFEST_VERSION = 1

#: The order authoritative sources are consulted, and the order disagreements are named in.
DERIVATION_PRECEDENCE = ("interface_manifest", "criteria_pack", "expanded_tree")

_SLOT_ID_RE = re.compile(r"^slot-[a-z0-9][a-z0-9-]*$")
_MARKER_RE = re.compile(
    r"^\s*// \[scaffold-slot:(?P<kind>begin|end) (?P<slot_id>slot-[a-z0-9][a-z0-9-]*)\]\s*$"
)
#: Near-miss detector: any mention of the marker vocabulary that is not a well-formed marker.
_MARKER_MENTION = "[scaffold-slot:"


class ScaffoldSpineError(Exception):
    """A scaffold file's slot structure is malformed (unparseable markers, nesting, dupes)."""


class ScaffoldDerivationError(Exception):
    """Authoritative sources disagree, or a required source is missing — generation refuses.

    Never raised for an element that is merely *underivable*: those are demoted to fill
    content. Raised when sources *contradict* (manifest declares a surface the tree lacks),
    which per SIP §7 implies generator-version drift or a mutated workspace — the message
    names which sources disagree.
    """


class ScaffoldValidationError(Exception):
    """An emitted scaffold does not match its own manifest — a generator defect, caught
    before the scaffold can become the run's qa artifact (scaffold-invalid, SIP §5)."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slot_begin_marker(slot_id: str) -> str:
    """The exact begin-marker line for ``slot_id`` (no indentation, no trailing newline)."""
    _require_slot_id(slot_id)
    return f"// [scaffold-slot:begin {slot_id}]"


def slot_end_marker(slot_id: str) -> str:
    """The exact end-marker line for ``slot_id``."""
    _require_slot_id(slot_id)
    return f"// [scaffold-slot:end {slot_id}]"


def _require_slot_id(slot_id: str) -> None:
    if not _SLOT_ID_RE.match(slot_id):
        raise ValueError(
            f"invalid slot id {slot_id!r}: must match {_SLOT_ID_RE.pattern!r} "
            f"(kebab-case, 'slot-' prefix)"
        )


@dataclass(frozen=True)
class SlotRegion:
    """One parsed slot region: 1-indexed line numbers of the two marker lines."""

    slot_id: str
    begin_line: int
    end_line: int


def parse_slot_regions(text: str) -> tuple[SlotRegion, ...]:
    """Parse the slot regions of a scaffold file, or raise :class:`ScaffoldSpineError`.

    Enforces the structure rules of the marker grammar (module docstring). Line numbers
    are 1-indexed and name the *marker* lines, matching how region bounds are recorded in
    the manifest.
    """
    regions: list[SlotRegion] = []
    seen: set[str] = set()
    open_id: str | None = None
    open_line = 0
    for lineno, line in enumerate(text.split("\n"), start=1):
        match = _MARKER_RE.match(line)
        if match is None:
            if _MARKER_MENTION in line:
                raise ScaffoldSpineError(
                    f"line {lineno} mentions {_MARKER_MENTION!r} but is not a well-formed "
                    f"slot marker: {line.strip()!r}. A malformed marker must fail, not be "
                    f"frozen into the spine."
                )
            continue
        kind, slot_id = match.group("kind"), match.group("slot_id")
        if kind == "begin":
            if open_id is not None:
                raise ScaffoldSpineError(
                    f"line {lineno}: begin marker for {slot_id!r} while {open_id!r} "
                    f"(opened line {open_line}) is still open — slots cannot nest."
                )
            if slot_id in seen:
                raise ScaffoldSpineError(
                    f"line {lineno}: duplicate slot id {slot_id!r} in one file."
                )
            open_id, open_line = slot_id, lineno
        else:
            if open_id is None:
                raise ScaffoldSpineError(
                    f"line {lineno}: end marker for {slot_id!r} with no open slot."
                )
            if slot_id != open_id:
                raise ScaffoldSpineError(
                    f"line {lineno}: end marker for {slot_id!r} does not match open slot "
                    f"{open_id!r} (opened line {open_line})."
                )
            regions.append(SlotRegion(slot_id=slot_id, begin_line=open_line, end_line=lineno))
            seen.add(slot_id)
            open_id = None
    if open_id is not None:
        raise ScaffoldSpineError(f"slot {open_id!r} (opened line {open_line}) is never closed.")
    return tuple(regions)


def elide_slot_bodies(text: str) -> str:
    """The canonical spine text: every slot body removed, markers and all else kept.

    Raises :class:`ScaffoldSpineError` on malformed structure — a file that does not parse
    has no spine (canonicalization rule 5).
    """
    regions = parse_slot_regions(text)
    body_lines: set[int] = set()
    for region in regions:
        body_lines.update(range(region.begin_line + 1, region.end_line))
    kept = [
        line for lineno, line in enumerate(text.split("\n"), start=1) if lineno not in body_lines
    ]
    return "\n".join(kept)


def spine_hash(text: str) -> str:
    """SHA-256 of the canonical spine text (canonicalization rules 1–5)."""
    return _sha256(elide_slot_bodies(text))


def expanded_tree_hash(files: Iterable[Mapping[str, str]]) -> str:
    """Identity of an expanded skeleton: SHA-256 over sorted ``path:sha256(content)`` lines.

    Sorted by path so the hash names the tree as a *set* of files, independent of emission
    order. Recorded in the manifest as the tree imports were resolved against, so a later
    disagreement is attributable to workspace mutation vs. generator drift.
    """
    lines = sorted(f"{f['name']}:{_sha256(f['content'])}" for f in files)
    return _sha256("\n".join(lines))


@dataclass(frozen=True)
class BehaviorSlot:
    """One behavior shell's identity and its fill slot's provenance + region bounds.

    ``probe_id`` binds the shell to the contract probe it mirrors (``""`` for shells the
    generator mints beyond the probe set — their identity is the slot id itself);
    ``criterion_ids`` carry any bound contract criteria. Region bounds are 1-indexed marker
    lines in the *emitted* (empty-fill) file.
    """

    slot_id: str
    behavior: str
    probe_id: str = ""
    criterion_ids: tuple[str, ...] = ()
    begin_line: int = 0
    end_line: int = 0

    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "behavior": self.behavior,
            "probe_id": self.probe_id,
            "criterion_ids": list(self.criterion_ids),
            "begin_line": self.begin_line,
            "end_line": self.end_line,
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> BehaviorSlot:
        return cls(
            slot_id=d["slot_id"],
            behavior=d["behavior"],
            probe_id=d.get("probe_id", ""),
            criterion_ids=tuple(d.get("criterion_ids", ())),
            begin_line=d.get("begin_line", 0),
            end_line=d.get("end_line", 0),
        )


@dataclass(frozen=True)
class VerificationScaffoldFile:
    """One emitted scaffold file: full-content hash, spine hash, and its slots."""

    path: str
    content_hash: str
    spine_hash: str
    slots: tuple[BehaviorSlot, ...] = ()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "content_hash": self.content_hash,
            "spine_hash": self.spine_hash,
            "slots": [s.to_dict() for s in self.slots],
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> VerificationScaffoldFile:
        return cls(
            path=d["path"],
            content_hash=d["content_hash"],
            spine_hash=d["spine_hash"],
            slots=tuple(BehaviorSlot.from_dict(s) for s in d.get("slots", ())),
        )


def build_scaffold_file(
    path: str, content: str, slots: tuple[BehaviorSlot, ...]
) -> VerificationScaffoldFile:
    """Pin one emitted file: hashes computed here so generator and validator cannot drift.

    ``slots`` supply provenance (behavior, probe/criterion bindings); their region bounds
    are *recomputed from the content* and must agree with the parsed structure — a slot the
    content lacks, or a parsed region no slot claims, is a :class:`ScaffoldValidationError`.
    """
    regions = {r.slot_id: r for r in parse_slot_regions(content)}
    declared = {s.slot_id for s in slots}
    if set(regions) != declared:
        raise ScaffoldValidationError(
            f"{path}: declared slots {sorted(declared)} != parsed regions {sorted(regions)} — "
            f"the generator's slot table and its emitted content disagree."
        )
    bounded = tuple(
        BehaviorSlot(
            slot_id=s.slot_id,
            behavior=s.behavior,
            probe_id=s.probe_id,
            criterion_ids=s.criterion_ids,
            begin_line=regions[s.slot_id].begin_line,
            end_line=regions[s.slot_id].end_line,
        )
        for s in slots
    )
    return VerificationScaffoldFile(
        path=path,
        content_hash=_sha256(content),
        spine_hash=spine_hash(content),
        slots=bounded,
    )


@dataclass(frozen=True)
class VerificationScaffoldManifest:
    """The scaffold manifest: what the generator emitted, pinned for diagnosis (SIP §4.3).

    Everything violation attribution needs (module docstring), nothing more. Aggregates are
    derived from per-file hashes and exposed as methods rather than stored fields — a stored
    aggregate is one more thing a hand edit can make disagree with itself.
    """

    scaffold_manifest_version: int
    generator_version: int
    stack: str
    interface_manifest_hash: str
    criteria_pack: str
    expanded_tree_hash: str
    files: tuple[VerificationScaffoldFile, ...] = field(default=())

    def aggregate_spine_hash(self) -> str:
        """SHA-256 over sorted ``path:spine_hash`` lines — the frozen spine's identity."""
        return _sha256("\n".join(sorted(f"{f.path}:{f.spine_hash}" for f in self.files)))

    def scaffold_hash(self) -> str:
        """SHA-256 over sorted ``path:content_hash`` lines — the whole emission's identity."""
        return _sha256("\n".join(sorted(f"{f.path}:{f.content_hash}" for f in self.files)))

    def slot_ids(self) -> tuple[str, ...]:
        return tuple(s.slot_id for f in self.files for s in f.slots)

    def find_slot(self, slot_id: str) -> tuple[VerificationScaffoldFile, BehaviorSlot] | None:
        for f in self.files:
            for s in f.slots:
                if s.slot_id == slot_id:
                    return f, s
        return None

    def lint(self) -> list[str]:
        """Cross-file structural findings; empty when clean.

        Catches what per-file parsing cannot: a slot id claimed by two files (the merge
        layer addresses fills by slot id alone — P3 — so a duplicate would make addressing
        ambiguous), a file with no slots (a shell-less scaffold file has no author surface
        and no reason to exist), and a version this schema does not define.
        """
        findings: list[str] = []
        if self.scaffold_manifest_version != SCAFFOLD_MANIFEST_VERSION:
            findings.append(
                f"scaffold_manifest_version {self.scaffold_manifest_version} != "
                f"{SCAFFOLD_MANIFEST_VERSION} (this schema)"
            )
        seen: dict[str, str] = {}
        for f in self.files:
            if not f.slots:
                findings.append(f"{f.path}: scaffold file with no behavior slots")
            for s in f.slots:
                if s.slot_id in seen:
                    findings.append(
                        f"duplicate slot id {s.slot_id!r} in {f.path} and {seen[s.slot_id]}"
                    )
                else:
                    seen[s.slot_id] = f.path
        return findings

    def to_dict(self) -> dict:
        return {
            "scaffold_manifest_version": self.scaffold_manifest_version,
            "generator_version": self.generator_version,
            "stack": self.stack,
            "interface_manifest_hash": self.interface_manifest_hash,
            "criteria_pack": self.criteria_pack,
            "expanded_tree_hash": self.expanded_tree_hash,
            "aggregate_spine_hash": self.aggregate_spine_hash(),
            "scaffold_hash": self.scaffold_hash(),
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> VerificationScaffoldManifest:
        """Load a stored manifest. Stored aggregates are *verified*, not trusted: a record
        whose derived hashes disagree with its own file table has been hand-edited, and
        loading it quietly would launder the edit into an authority."""
        manifest = cls(
            scaffold_manifest_version=d["scaffold_manifest_version"],
            generator_version=d["generator_version"],
            stack=d["stack"],
            interface_manifest_hash=d["interface_manifest_hash"],
            criteria_pack=d["criteria_pack"],
            expanded_tree_hash=d["expanded_tree_hash"],
            files=tuple(VerificationScaffoldFile.from_dict(f) for f in d.get("files", ())),
        )
        for key, derived in (
            ("aggregate_spine_hash", manifest.aggregate_spine_hash()),
            ("scaffold_hash", manifest.scaffold_hash()),
        ):
            stored = d.get(key)
            if stored is not None and stored != derived:
                raise ScaffoldValidationError(
                    f"stored {key} {stored!r} disagrees with the manifest's own file table "
                    f"({derived!r}) — the record has been mutated."
                )
        return manifest

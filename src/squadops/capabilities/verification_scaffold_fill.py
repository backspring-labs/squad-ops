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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.core.hashing import text_sha256
from squadops.cycles.revision_transaction import (
    Revision,
    RevisionOperation,
    RevisionTransaction,
    base_revision_id,
    resolve_and_apply,
)
from squadops.cycles.task_outcome import FailureClassification
from squadops.cycles.write_authorization import WriteGrant
from squadops.stacks.slot_subject import (
    LOOSER_THAN_VALUE,
    AssertionSubject,
    MatcherClass,
    SlotAssertion,
    SubjectSurface,
)
from squadops.stacks.verification_scaffold import (
    ScaffoldSpineError,
    ScaffoldValidationError,
    VerificationScaffoldManifest,
    parse_slot_regions,
    slot_body_span,
    spine_hash,
)
from squadops.stacks.verification_scaffold_emission import slot_assertion_reader
from squadops.tasks.task_types import TaskType

#: Size bounds for one fill body. Generous for domain assertions, prohibitive for a file.
MAX_FILL_LINES = 120
MAX_FILL_BYTES = 8_000

#: A fill fence, with the language prefix an author reflexively adds made optional (#987).
#:
#: The brief teaches ```` ```fill:slot-<id> ````, and an author writing markdown all day
#: writes ```` ```typescript:fill:slot-<id> ```` anyway. Under the exact-form pattern that
#: cost a whole pre-V7 shakedown: the fence did not match here, `strip_fill_blocks` left it
#: in the text, and the file extractor — which reads ``<language>:<path>`` info strings —
#: took it for a file named ``fill:slot-<id>``. All six fills vanished, and nothing said so.
#:
#: The prefixed form is unambiguous, so accepting it loses nothing. It is still *recorded*
#: (see ``language_prefixed``) rather than silently normalised, because a brief the author
#: keeps departing from is worth knowing about.
_FILL_FENCE_RE = re.compile(
    r"^```(?:(?P<lang>[A-Za-z][\w+.-]*):)?"
    r"fill:(?P<slot_id>slot-[a-z0-9][a-z0-9-]*)[ \t]*\n(?P<body>.*?)^```[ \t]*$",
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
    #: slot ids whose fence carried a language prefix (``typescript:fill:slot-…``). Accepted,
    #: but counted: it measures how far the emission drifts from the form the brief teaches.
    language_prefixed: tuple[str, ...] = ()


#: Symbols ``lib/store.ts`` exports. A fill referencing one of these is asserting on
#: persisted state; a fill referencing none is asserting only on the response it was handed.
_STORE_SYMBOLS = ("all", "insert", "find", "reset", "TABLES", "nextId")


def measure_assertion_strength(emission: FillEmission) -> dict:
    """How much the fills assert, and whether any of it is about the store (#980).

    **Why this is measured rather than assumed.** The pre-V7 shakedown finished `accepted`
    with 14 of 14 criteria after its qa author retreated: attempt 1 emitted 4,896 completion
    tokens of fills asserting response values *and* store effects; attempt 3 emitted 711
    tokens asserting `body.id`, `body.title` and `body.datetime` and touching the store
    nowhere. Both were recorded identically as "8 of 8 fills on the first attempt", because
    the record counted slots and not what the slots say.

    So a roll that retreated was indistinguishable from a roll that was right first time.
    This does not gate anything — an author may legitimately have nothing to say about the
    store for a given behaviour — but the closing claim of a measurement window cannot
    describe assertion strength it never recorded.

    ``store_slots`` is the load-bearing field. ``body_chars`` is the cheap corroborator: the
    7x drop between those two attempts was visible in data already logged and read by nobody.
    """
    bodies = {f.slot_id: f.body for f in emission.fills if not f.is_not_applicable}
    store_slots = sorted(
        slot
        for slot, body in bodies.items()
        if any(re.search(rf"\b{sym}\s*[(.]", body) for sym in _STORE_SYMBOLS)
    )
    used = sorted(
        {
            sym
            for body in bodies.values()
            for sym in _STORE_SYMBOLS
            if re.search(rf"\b{sym}\s*[(.]", body)
        }
    )
    return {
        "filled_slots": len(bodies),
        "not_applicable_slots": sum(1 for f in emission.fills if f.is_not_applicable),
        "body_chars": sum(len(b) for b in bodies.values()),
        "store_slots": store_slots,
        "store_symbols_used": used,
        "any_fill_touches_the_store": bool(store_slots),
        # #987: accepted-but-noted fence drift. Non-empty means the brief's taught form
        # and the author's habit disagree, which is worth seeing before it costs a roll.
        "language_prefixed_fences": list(emission.language_prefixed),
    }


def parse_fill_emission(text: str) -> FillEmission:
    """Extract fill blocks from an authored emission.

    Only ``fill:slot-…`` fences are this protocol's; everything else (additive test
    files as ordinary path-addressed fences, prose) is deliberately left for the
    existing emission pipeline — the two surfaces must not compete for the same bytes.
    """
    fills: list[Fill] = []
    seen: dict[str, int] = {}
    prefixed: list[str] = []
    for match in _FILL_FENCE_RE.finditer(text):
        slot_id = match.group("slot_id")
        body = match.group("body")
        if match.group("lang"):
            prefixed.append(slot_id)
        seen[slot_id] = seen.get(slot_id, 0) + 1
        stripped = [line for line in body.strip("\n").split("\n") if line.strip()]
        na = _NOT_APPLICABLE_RE.match(stripped[0]) if len(stripped) == 1 else None
        if na:
            fills.append(Fill(slot_id=slot_id, not_applicable_reason=na.group("reason").strip()))
        else:
            fills.append(Fill(slot_id=slot_id, body=body.strip("\n")))
    duplicates = tuple(sorted(slot_id for slot_id, count in seen.items() if count > 1))
    return FillEmission(
        fills=tuple(fills),
        duplicates=duplicates,
        language_prefixed=tuple(sorted(set(prefixed))),
    )


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


#: A store table reference in a fill body — ``TABLES.Run`` (#1087).
_TABLE_REF_RE = re.compile(r"\bTABLES\.(\w+)")


#: A matcher applied to a collection field — ``.participants).toContain(`` and kin — with
#: the first significant character of its argument captured, which is all the kind check
#: needs: a quote or digit is a primitive, ``{`` is an object, ``[`` opens an array whose
#: first element is inspected the same way (#1094).
_COLLECTION_MATCHER_RE = re.compile(
    r"\.(?P<field>\w+)\)\s*(?:\.not)?\s*\.to(?:Contain|ContainEqual|Equal|StrictEqual)"
    r"\(\s*(?P<arg>\[\s*[^\s\]]|[^\s)])"
)
#: Property access on an element of a collection field — ``.participants[0].name`` — which
#: asserts the element is an object.
_ELEMENT_PROPERTY_RE = re.compile(r"\.(?P<field>\w+)\[\d+\]\.\w+")


def _argument_kind(arg: str) -> str | None:
    """``"primitive"`` / ``"object"`` for a matcher argument's first significant char(s);
    ``None`` when the argument's kind cannot be read (an identifier, an empty array)."""
    head = arg.strip()
    if head.startswith("["):
        head = head[1:].strip()
        if not head:
            return None  # `toEqual([])` — emptiness, not a kind
    if head[:1] in ("'", '"', "`") or head[:1].isdigit():
        return "primitive"
    if head[:1] == "{":
        return "object"
    return None


def element_kind_findings(body: str, element_kinds: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Every collection-field assertion in ``body`` whose element kind contradicts the
    declared one (#1094). Narrow by design: only a matcher argument or element access
    whose kind is readable from the text; whether an assertion is *good* is not this
    function's question.

    Roll 5 of the 1.6.3 set: the manifest declared ``participants: list[Participant]``,
    the frozen floor asserted each element carries ``name``, and the fill asserted
    ``expect(body.participants).toContain('sample')`` — strings. A repair that returned
    the declared objects passed the floor and failed the fill, was rejected, and the
    loop discarded it. The floor and the fill were contradicting each other inside one
    test, and the fill won because it ran second.
    """
    findings: list[str] = []
    for m in _COLLECTION_MATCHER_RE.finditer(body):
        declared = element_kinds.get(m.group("field"))
        if not declared:
            continue
        asserted = _argument_kind(m.group("arg"))
        if asserted and asserted != declared.get("kind"):
            findings.append(_kind_finding(m.group("field"), declared, asserted))
    for m in _ELEMENT_PROPERTY_RE.finditer(body):
        declared = element_kinds.get(m.group("field"))
        if declared and declared.get("kind") == "primitive":
            findings.append(_kind_finding(m.group("field"), declared, "object"))
    return list(dict.fromkeys(findings))


def _kind_finding(field: str, declared: Mapping[str, Any], asserted: str) -> str:
    if declared.get("kind") == "object":
        fields = ", ".join(f"`{f}`" for f in declared.get("required_fields", []))
        return (
            f"asserts {asserted} elements on `{field}`, which the manifest declares as a list "
            f"of objects each carrying {fields} — the shell's frozen floor above the slot "
            f"asserts exactly that, so this assertion cannot pass against a correct "
            f"application; assert on `{field}[i].<field>` instead (#1094)"
        )
    return (
        f"asserts object elements on `{field}`, which the manifest declares as a list of "
        f"`{declared.get('typeof', 'primitive')}` values — the shell's frozen floor above the "
        f"slot asserts exactly that; assert on the values, not on element properties (#1094)"
    )


def fill_findings(
    fill: Fill,
    store_tables: Sequence[str] | None = None,
    element_kinds: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[str]:
    """Every containment rule this fill violates; empty for a valid fill or explicit NA.

    ``store_tables`` is the frozen store's exported table set, when the stack has one. A
    fill asserting on a table outside it is rejected here, deterministically, with the
    real tables named (#1087) — before it can reach a retest where it reads as an empty
    array and costs a working application the roll. ``None`` means the stack's store is
    not table-keyed and the rule does not apply.
    """
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
    if store_tables is not None:
        phantom = sorted({m for m in _TABLE_REF_RE.findall(fill.body) if m not in store_tables})
        if phantom:
            findings.append(
                f"asserts on {', '.join(f'`TABLES.{p}`' for p in phantom)}, which the frozen "
                f"store does not export — a correct application persists only "
                f"{', '.join(f'`TABLES.{s}`' for s in store_tables) or 'no tables'}; an "
                f"embedded shape or response projection has no table of its own, so assert on "
                f"the owning entity's field instead (#1087)"
            )
    if element_kinds:
        findings.extend(element_kind_findings(fill.body, element_kinds))
    return findings


@dataclass(frozen=True)
class SlotDisposition:
    """What happened to one slot at merge time — the fill layer's per-slot evidence."""

    slot_id: str
    disposition: str
    detail: str = ""


# --------------------------------------------------------------------------- slot-subject gate
#
# SIP-0104 §13d: a repair is never allowed to resolve a failing slot assertion by deleting or
# weakening it. §13f (#2664) builds that as a gate on the slot-region revision itself, so every
# path that rewrites a slot body meets it — the slot-scoped qa repair, a re-dispatched qa.test,
# and a repair sent for another file that refills every slot (the MacBook lane's G4, point 2).


class SubjectVerdict(StrEnum):
    """What the gate found when a slot with an open failure was revised."""

    #: The revision still asserts on the failing assertion's subject (any matcher).
    KEPT = "kept"
    #: Refused: the subject is gone, and the declarations show its field on that surface.
    SLOT_SUBJECT_DROPPED = FailureClassification.SLOT_SUBJECT_DROPPED
    #: The subject is gone, and the declarations show its field absent there: a correct drop.
    ABSENT_THERE = "absent_there"
    #: The failing assertion's subject, or the revision's, cannot be read: recorded, not refused.
    SUBJECT_UNREADABLE = "subject_unreadable"
    #: The scaffold declares nothing for this surface, so presence cannot be shown either way.
    DECLARATIONS_UNAVAILABLE = "declarations_unavailable"
    #: The revision left the slot body as it was.
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class SlotSubjectVerdict:
    """One gated slot revision: the verdict, the failing subject, and the softer signals."""

    slot_id: str
    file: str
    verdict: SubjectVerdict
    detail: str
    failing_target: str = ""
    subject: AssertionSubject | None = None
    #: G4 point 3: the subject is kept, but only by matchers looser than the failing one's
    #: exact value — existence or shape. Recorded, never refused.
    matcher_loosened: bool = False
    #: The passing checks the revision dropped beside the failing one, by subject. Recorded.
    lost_subjects: tuple[str, ...] = ()

    @property
    def refused(self) -> bool:
        return self.verdict == SubjectVerdict.SLOT_SUBJECT_DROPPED

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "file": self.file,
            "verdict": str(self.verdict),
            "detail": self.detail,
            "failing_target": self.failing_target,
            "subject": self.subject.to_dict() if self.subject else None,
            "described": self.subject.describe() if self.subject else "",
            "matcher_loosened": self.matcher_loosened,
            "lost_subjects": list(self.lost_subjects),
        }


#: #2664: the key a handler stamps on its outputs when the gate refused a slot revision — one
#: entry per refused slot (``SlotSubjectVerdict.to_dict()``). The correction loop reads it: a
#: refused repair's round is spent, and the next round is told the slot and the subject.
SLOT_SUBJECT_DROPPED_KEY = "slot_subject_dropped"


def _declared_on(
    subject: AssertionSubject, surfaces: Mapping[str, Any], slot_id: str
) -> bool | None:
    """Whether the scaffold declares ``subject``'s field on its surface; ``None`` when it
    declares nothing for that surface, so presence cannot be shown (G4 point 5)."""
    if subject.surface == SubjectSurface.STORE:
        tables = surfaces.get("tables")
        if not isinstance(tables, Mapping):
            return None
        fields = tables.get(subject.table)
        if fields is None:
            return False
        return not subject.field or subject.field in fields
    slot = (surfaces.get("slots") or {}).get(slot_id)
    if not isinstance(slot, Mapping):
        return None
    fields = slot.get(str(subject.surface))
    if fields is None:
        return None
    if not subject.field:
        return bool(fields) or subject.surface == SubjectSurface.RESPONSE
    return subject.field in fields


def _mentions(assertion: SlotAssertion, subject: AssertionSubject) -> bool:
    """Whether an unreadable assertion could be on ``subject``: it names the field (or, for
    a whole surface, the surface's own expression). The gate refuses only what it can show."""
    if subject.field:
        token = subject.field
    elif subject.surface == SubjectSurface.STORE:
        token = f"TABLES.{subject.table}"
    elif subject.surface == SubjectSurface.ERROR_ENVELOPE:
        token = "body.error"
    else:
        token = "body"
    return re.search(rf"(?<![\w$]){re.escape(token)}(?![\w$])", assertion.resolved) is not None


@dataclass(frozen=True)
class SlotSubjectGuard:
    """The open slot failures a merge must gate, and what it judges them against.

    ``failures`` maps a slot id to ``(file, line)``: the failing assertion's line in the
    merged shell it was observed on. ``accepted`` maps a shell path to that shell — the slot's
    last accepted body lives there. ``surfaces`` are the scaffold's declarations
    (``slot_subject_surfaces``) and ``reader`` the stack's fill reader.
    """

    failures: Mapping[str, tuple[str, int | None]]
    accepted: Mapping[str, str]
    surfaces: Mapping[str, Any]
    reader: Callable[[str], tuple[SlotAssertion, ...]]

    def accepted_body(self, slot_id: str) -> list[str] | None:
        file, _line = self.failures.get(slot_id, ("", None))
        content = self.accepted.get(file)
        if content is None:
            return None
        try:
            region = next((r for r in parse_slot_regions(content) if r.slot_id == slot_id), None)
        except ScaffoldSpineError:
            return None
        if region is None:
            return None
        return content.split("\n")[region.begin_line : region.end_line - 1]

    def _failing_assertion(self, slot_id: str, body: list[str]) -> SlotAssertion | str:
        """The failing assertion, or why it cannot be read. The line is the merged shell's,
        as the runner reported it; the slot body's first line is the one after its marker."""
        file, line = self.failures[slot_id]
        content = self.accepted.get(file, "")
        region = next((r for r in parse_slot_regions(content) if r.slot_id == slot_id), None)
        if region is None or not isinstance(line, int):
            return "the failure carries no line inside the slot"
        if not region.begin_line < line < region.end_line:
            return "the failure's line is not inside the slot"
        covering = [a for a in self.reader("\n".join(body)) if a.covers(line - region.begin_line)]
        if not covering:
            return f"line {line} is not an expect() the reader can place"
        subjects = {a.subject for a in covering}
        if None in subjects or len(subjects) != 1:
            return f"the failing assertion's target `{covering[-1].target}` maps to no subject"
        return covering[-1]

    def judge(self, slot_id: str, file: str, new_body: str) -> SlotSubjectVerdict | None:
        """The verdict on revising ``slot_id`` to ``new_body``, or ``None`` when the slot has no
        open failure. ``new_body`` is ``""`` for a not-applicable disposition, which asserts
        nothing."""
        if slot_id not in self.failures:
            return None
        accepted = self.accepted_body(slot_id)
        if accepted is None:
            return SlotSubjectVerdict(
                slot_id,
                file,
                SubjectVerdict.SUBJECT_UNREADABLE,
                "the shell the failure was observed on is not available",
            )
        if "\n".join(accepted).strip() == new_body.strip():
            return SlotSubjectVerdict(
                slot_id, file, SubjectVerdict.UNCHANGED, "the body is unchanged"
            )
        failing = self._failing_assertion(slot_id, accepted)
        if isinstance(failing, str):
            return SlotSubjectVerdict(slot_id, file, SubjectVerdict.SUBJECT_UNREADABLE, failing)
        subject = failing.subject
        if subject is None:  # pragma: no cover - _failing_assertion returns a placed subject
            return None
        revised = self.reader(new_body)
        verdict, detail, loosened = self._compare(slot_id, failing, subject, revised)
        still = {a.subject for a in revised if a.subject is not None}
        lost = tuple(
            dict.fromkeys(
                a.subject.describe()
                for a in self.reader("\n".join(accepted))
                if a.subject is not None and a.subject != subject and a.subject not in still
            )
        )
        return SlotSubjectVerdict(
            slot_id,
            file,
            verdict,
            detail,
            failing_target=failing.target,
            subject=subject,
            matcher_loosened=loosened,
            lost_subjects=lost,
        )

    def _compare(
        self,
        slot_id: str,
        failing: SlotAssertion,
        subject: AssertionSubject,
        revised: tuple[SlotAssertion, ...],
    ) -> tuple[SubjectVerdict, str, bool]:
        """``(verdict, detail, matcher loosened)`` for a revision of a slot whose failing
        assertion reads ``subject``. The same surface and field with any matcher keeps it (G4
        point 3); a drop is refused only where the declarations show the field present."""
        kept = [a for a in revised if a.subject == subject]
        if kept:
            loosened = failing.matcher_class == MatcherClass.VALUE and all(
                a.matcher_class in LOOSER_THAN_VALUE for a in kept
            )
            detail = f"still asserts on {subject.describe()}"
            if loosened:
                detail += ", only by existence or shape where it pinned a value"
            return SubjectVerdict.KEPT, detail, loosened
        unread = [a for a in revised if a.subject is None and _mentions(a, subject)]
        if unread:
            return (
                SubjectVerdict.SUBJECT_UNREADABLE,
                f"the revision's `{unread[0].target}` names the subject but cannot be read",
                False,
            )
        declared = _declared_on(subject, self.surfaces, slot_id)
        if declared is None:
            return (
                SubjectVerdict.DECLARATIONS_UNAVAILABLE,
                f"dropped {subject.describe()}; the scaffold declares nothing for that surface",
                False,
            )
        if not declared:
            return (
                SubjectVerdict.ABSENT_THERE,
                f"dropped {subject.describe()}, which the declarations show absent there",
                False,
            )
        return (
            SubjectVerdict.SLOT_SUBJECT_DROPPED,
            f"dropped {subject.describe()}, which the declarations show present there",
            False,
        )


def slot_subject_guard(
    scaffold_input: Mapping[str, Any] | None,
    failures: Iterable[Mapping[str, Any]],
    accepted_files: Iterable[Mapping[str, Any]],
) -> SlotSubjectGuard | None:
    """The guard for one merge, or ``None`` when there is nothing to gate.

    ``failures`` are the open in-slot failures (``file``, ``slot_id``, ``line``), as the
    scaffold evidence observed them; ``accepted_files`` the shells they were observed on
    (``name``, ``content``). No scaffold, no failures, or a stack with no reader: no guard,
    and the merge is exactly what it was (G4 point 5).
    """
    if not isinstance(scaffold_input, Mapping):
        return None
    reader = slot_assertion_reader(str((scaffold_input.get("manifest") or {}).get("stack") or ""))
    by_slot: dict[str, tuple[str, int | None]] = {}
    for f in failures:
        slot_id, file = str(f.get("slot_id") or ""), str(f.get("file") or "")
        line = f.get("line")
        if slot_id and file and slot_id not in by_slot:
            by_slot[slot_id] = (file, line if isinstance(line, int) else None)
    if reader is None or not by_slot:
        return None
    accepted = {
        str(a.get("name")): str(a.get("content") or "") for a in accepted_files if a.get("name")
    }
    return SlotSubjectGuard(
        failures=by_slot,
        accepted=accepted,
        surfaces=scaffold_input.get("subject_surfaces") or {},
        reader=reader,
    )


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
    #: #2664: one verdict per gated slot revision — a slot with an open failure whose body
    #: this merge was asked to change. Empty when no guard was given.
    subject_verdicts: tuple[SlotSubjectVerdict, ...] = ()

    @property
    def refused(self) -> tuple[SlotSubjectVerdict, ...]:
        """The revisions the slot-subject gate refused (``slot_subject_dropped``)."""
        return tuple(v for v in self.subject_verdicts if v.refused)

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
    store_tables: Sequence[str] | None = None,
    slot_element_kinds: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    producer: str = TaskType.QA_TEST,
    task_id: str = "",
    subject_guard: SlotSubjectGuard | None = None,
) -> FillMergeRecord:
    """Merge an authored fill emission into the scaffold, deterministically.

    Slot-body replacement only, in scaffold order. Every declared slot ends in exactly
    one disposition; the merged spine is re-hashed and must equal the scaffold record's —
    containment is *verified* on every merge, never assumed (a violation here is a bug in
    this module, raised as ``AssertionError`` rather than shipped).

    **The merge is a revision transaction (SIP-0107 rollout step 2).** Each slot's merged body
    — the fill, a not-applicable note, or the fill layer's failing state — is one
    region-replacement revision, and the scaffold shells are the base. The transaction carries
    a grant over exactly those shells for ``producer``, resolves every slot through the marker
    grammar (:func:`~squadops.stacks.verification_scaffold.slot_body_span`), and applies
    all of them or none. The bytes are the ones this function always produced, so the qa lane
    is the transaction's first proof rather than its first casualty.

    **The slot-subject gate (SIP-0104 §13f, #2664).** Every slot-body write is one of these
    region revisions, so the gate sits here. With a ``subject_guard``, each slot that has an
    open failure and is revised to a fill or a not-applicable note is judged against its last
    accepted body. A revision that drops the failing assertion's subject, where the
    declarations show that field present, is refused: the slot keeps its accepted body, and the
    verdict is in ``subject_verdicts``. A caller merging a repair spends the whole repair on a
    refusal (``_merge_repair_fills``); a re-authoring qa.test keeps the rest of its emission.
    """

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
    base = {file_record.path: scaffold_by_path[file_record.path] for file_record in record.files}
    revisions: list[Revision] = []
    dispositions: list[SlotDisposition] = []
    verdicts: list[SlotSubjectVerdict] = []
    for file_record in record.files:
        regions = {r.slot_id: r for r in parse_slot_regions(base[file_record.path])}
        for slot in sorted(file_record.slots, key=lambda s: regions[s.slot_id].begin_line):
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
                    slot.slot_id,
                    fill,
                    fill_findings(fill, store_tables, (slot_element_kinds or {}).get(slot.slot_id))
                    if fill
                    else [],
                )
                if subject_guard is not None and fill is not None:
                    body, disposition = _gate_revision(
                        subject_guard, file_record.path, fill, body, disposition, verdicts
                    )
            revisions.append(
                Revision(
                    artifact_path=file_record.path,
                    region_id=slot.slot_id,
                    operation=RevisionOperation.REPLACE_REGION,
                    replacement="".join(f"{line}\n" for line in body),
                )
            )
            dispositions.append(disposition)

    transaction = RevisionTransaction(
        base_revision_id=base_revision_id(base),
        grant=WriteGrant(producer=producer, stage="qa_fill", writable=frozenset(base)),
        task_id=task_id,
        revisions=tuple(revisions),
    )
    outcome = resolve_and_apply(
        base, transaction, lambda _path, content, slot_id: slot_body_span(content, slot_id)
    )
    if not outcome.accepted:
        raise ScaffoldValidationError(
            "the fill merge's revision transaction was refused — a defect in merge_fills "
            "itself, since every revision names a declared slot of a shell it was handed: "
            + "; ".join(f"{r.reason}: {r.detail}" for r in outcome.refusals)
        )

    merged_files: list[MergedFile] = []
    for file_record in record.files:
        merged = outcome.candidate_files[file_record.path]
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
                content_hash=text_sha256(merged),
                spine_hash=merged_spine,
            )
        )
    return FillMergeRecord(
        files=tuple(merged_files),
        dispositions=tuple(dispositions),
        misaddressed=misaddressed,
        subject_verdicts=tuple(verdicts),
    )


def _gate_revision(
    guard: SlotSubjectGuard,
    path: str,
    fill: Fill,
    body: list[str],
    disposition: SlotDisposition,
    verdicts: list[SlotSubjectVerdict],
) -> tuple[list[str], SlotDisposition]:
    """One slot's revision through the slot-subject gate (#2664).

    Only a revision that could pass is judged: a fill or a not-applicable note. A rejected or
    missing slot renders the fill layer's failing state, which fails the suite on its own and
    so cannot resolve a failure by agreeing with the app.
    """
    if disposition.disposition not in (DISPOSITION_FILLED, DISPOSITION_NOT_APPLICABLE):
        return body, disposition
    verdict = guard.judge(fill.slot_id, path, "" if fill.is_not_applicable else fill.body)
    if verdict is None:
        return body, disposition
    verdicts.append(verdict)
    accepted = guard.accepted_body(fill.slot_id) if verdict.refused else None
    if accepted is None:
        return body, disposition
    return accepted, SlotDisposition(
        fill.slot_id,
        DISPOSITION_FILLED,
        f"{verdict.verdict}: the revision was refused and the accepted body kept — "
        f"{verdict.detail}",
    )


@dataclass(frozen=True)
class FollowupFillMerge:
    """A later emission's fills folded into an earlier one, per slot (#947, 1.6.5 C)."""

    emission: FillEmission
    #: slot ids the followup filled that were missing or rejected before.
    applied: tuple[str, ...] = ()
    #: slot ids the followup re-emitted although they were already filled — ignored, so a
    #: self-eval asked for "only what is missing" cannot regress a slot that was fine.
    skipped_filled: tuple[str, ...] = ()


def apply_followup_fills(
    base: FillEmission,
    followup: FillEmission,
    dispositions: Sequence[Mapping[str, Any]],
    *,
    replace_filled: bool = False,
) -> FollowupFillMerge:
    """Fold a self-eval emission's fills into the primary emission.

    A followup fill lands on a slot whose current disposition is anything but
    ``filled`` (missing, rejected, not_applicable, or a duplicate); a slot already
    filled keeps its primary fill and the re-emission is recorded, not applied. The
    followup's own duplicates stay duplicates. ``replace_filled`` is the repair's
    setting (#970): a repair is told which slots failed and may replace a filled slot;
    a self-eval asked for "only what is missing" may not. Roll 6 of the 1.6.4 set is the case:
    the primary hit the completion cap with zero fills, the self-eval re-emitted all
    eight, and the handler threw them away because it only knew how to drop shell
    paths.
    """
    filled = {d["slot_id"] for d in dispositions if d.get("disposition") == DISPOSITION_FILLED}
    followup_dups = set(followup.duplicates)
    fills: dict[str, Fill] = {
        f.slot_id: f for f in base.fills if f.slot_id not in set(base.duplicates)
    }
    applied: list[str] = []
    skipped: list[str] = []
    for f in followup.fills:
        if f.slot_id in followup_dups:
            continue
        if f.slot_id in filled and not replace_filled:
            skipped.append(f.slot_id)
            continue
        fills[f.slot_id] = f
        applied.append(f.slot_id)
    applied_set = set(applied)
    duplicates = tuple(d for d in base.duplicates if d not in applied_set) + tuple(
        d for d in followup.duplicates if d not in base.duplicates
    )
    return FollowupFillMerge(
        emission=FillEmission(
            fills=tuple(fills.values()),
            duplicates=duplicates,
            language_prefixed=tuple(
                dict.fromkeys(base.language_prefixed + followup.language_prefixed)
            ),
        ),
        applied=tuple(dict.fromkeys(applied)),
        skipped_filled=tuple(dict.fromkeys(skipped)),
    )


#: The first line ``_merged_body`` writes for each non-filled disposition. Recovery
#: reads them back; they are the only shapes a merged slot body can take besides a fill.
_FAILING_STATE_PREFIX = "    // fill layer: "
_NOT_APPLICABLE_PREFIX = "    // not_applicable (qa): "


def recover_fills(
    merged_files: Sequence[Mapping[str, str]], record: VerificationScaffoldManifest
) -> tuple[FillEmission, list[dict[str, str]]]:
    """Read the fills back out of merged shells (#970, 1.6.5 D).

    A qa repair replaces one slot's fill and must keep every other slot exactly as
    the task left it — but the task's fill emission is not stored, only the merged
    shells are. Each slot body is one of three shapes ``_merged_body`` writes: a fill
    (returned as a :class:`Fill`), an explicit not-applicable line (returned as an NA
    fill), or the deterministic failing state (returned as no fill, disposition
    ``missing``). Round-trip property: ``merge_fills(pristine, record,
    recover_fills(merged)[0])`` reproduces ``merged`` byte for byte.

    Returns ``(emission, dispositions)`` in the shape the merge record banks, so the
    result feeds :func:`apply_followup_fills` directly.
    """
    by_path = {str(f["name"]): str(f["content"]) for f in merged_files}
    fills: list[Fill] = []
    dispositions: list[dict[str, str]] = []
    for file_record in record.files:
        content = by_path.get(file_record.path)
        if content is None:
            for slot in file_record.slots:
                dispositions.append(
                    {"slot_id": slot.slot_id, "disposition": DISPOSITION_MISSING, "detail": ""}
                )
            continue
        lines = content.split("\n")
        regions = {r.slot_id: r for r in parse_slot_regions(content)}
        for slot in file_record.slots:
            region = regions.get(slot.slot_id)
            body = lines[region.begin_line : region.end_line - 1] if region else []
            first = body[0] if body else ""
            if not body or first.startswith(_FAILING_STATE_PREFIX):
                dispositions.append(
                    {"slot_id": slot.slot_id, "disposition": DISPOSITION_MISSING, "detail": ""}
                )
            elif first.startswith(_NOT_APPLICABLE_PREFIX):
                reason = first[len(_NOT_APPLICABLE_PREFIX) :]
                fills.append(Fill(slot_id=slot.slot_id, not_applicable_reason=reason))
                dispositions.append(
                    {
                        "slot_id": slot.slot_id,
                        "disposition": DISPOSITION_NOT_APPLICABLE,
                        "detail": reason,
                    }
                )
            else:
                fills.append(Fill(slot_id=slot.slot_id, body="\n".join(body)))
                dispositions.append(
                    {"slot_id": slot.slot_id, "disposition": DISPOSITION_FILLED, "detail": ""}
                )
    return FillEmission(fills=tuple(fills)), dispositions


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


#: Violation kinds for a stored shell emission (P4 region enforcement). ``region`` is the
#: adversarial/structural class (frozen spine or slot structure changed); ``containment``
#: is the prohibited-fill class (spine intact, slot body smuggles forbidden content).
SHELL_VIOLATION_REGION = "region"
SHELL_VIOLATION_CONTAINMENT = "containment"


def shell_emission_violation(file_record, content: str) -> tuple[str, str] | None:
    """Judge one stored emission against its shell's bound record — ``None`` = legal.

    The single content-based rule P4 enforces on every landing path, any role, any locus
    (SIP §4.3): the spine and slot structure must be byte-identical to the bound record's,
    and every slot body must satisfy the fill containment rules. A legal emission is
    exactly a fill-merge product: body edits inside the markers, nothing else.

    Ordered so the strongest claim wins attribution: unparseable structure, then a changed
    slot set, then a spine mutation — each ``region`` (the adversarial class) — then body
    containment (``containment``, the correctable prohibited-fill class). Returns
    ``(kind, detail)`` for the first violation.
    """
    try:
        regions = parse_slot_regions(content)
    except ScaffoldSpineError as exc:
        return (SHELL_VIOLATION_REGION, f"slot structure malformed: {exc}")
    declared = {slot.slot_id for slot in file_record.slots}
    parsed = {region.slot_id for region in regions}
    if parsed != declared:
        return (
            SHELL_VIOLATION_REGION,
            f"slot set changed: bound {sorted(declared)}, emitted {sorted(parsed)}",
        )
    emitted_spine = spine_hash(content)
    if emitted_spine != file_record.spine_hash:
        return (
            SHELL_VIOLATION_REGION,
            f"frozen spine mutated: emitted spine {emitted_spine[:12]}… != bound "
            f"{file_record.spine_hash[:12]}… (imports, invocation, status assertion and "
            f"slot markers are frozen; only slot bodies are writable)",
        )
    lines = content.split("\n")
    for region in regions:
        body = "\n".join(lines[region.begin_line : region.end_line - 1])
        for pattern, reason in _FORBIDDEN:
            if pattern.search(body):
                return (SHELL_VIOLATION_CONTAINMENT, f"slot {region.slot_id}: {reason}")
    return None

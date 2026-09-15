"""The anchored-edit emission grammar — a repair states the exact text it replaces (#1213).

A repair of an existing file used to re-emit the whole file to change a few lines, so every line
it did not mean to change was re-authored and got a fresh chance to be wrong: 1.6.5 rolls 5 and 6
died that way, one carrying the correct fix. An anchored edit names the text being replaced and
its replacement; the framework applies it through the revision transaction
(:attr:`~squadops.cycles.revision_transaction.RevisionOperation.REPLACE_ANCHOR`), which refuses an
anchor that does not occur exactly once, so every other byte is identical by construction
(SIP-0107 §9.2).

The grammar, one fence per file, one or more blocks per fence::

    ```edit:backend/routes.py
    <<<<<<< SEARCH
        return Run(**payload.dict())
    =======
        return Run(**payload.dict(exclude_none=True))
    >>>>>>> REPLACE
    ```

**Strict, and loud when it is not met.** The markers are whole lines. Blank lines may separate
blocks; any other text between blocks, a block without its divider or end marker, an empty
SEARCH, an unclosed fence and an unsafe path are each recorded as a malformed edit with its
reason — never silently dropped, and never guessed into an edit. A bare fence line inside a
REPLACE body is content, not the fence's close, so a replacement may itself contain fenced text.

SEARCH and REPLACE text are their lines, each ending in a newline, exactly as emitted.

**Structural blocks** (SIP-0107 §38 step 5) share the fence and the transaction. They name an
entity the file's resolver locates (``structural_resolution``) instead of copying its text::

    ```edit:backend/routes.py
    <<<<<<< REPLACE function:post_runs#body
        run = run_event_store.create(payload)
        return run
    >>>>>>> END
    <<<<<<< INSERT BEFORE import:fastapi
    from __future__ import annotations
    >>>>>>> END
    <<<<<<< REMOVE import:os
    >>>>>>> END
    ```

``REPLACE``, ``INSERT BEFORE``, ``INSERT AFTER`` and ``REMOVE`` each take one selector and close
with ``>>>>>>> END``. A ``REMOVE`` carries no lines; an ``INSERT`` must carry some.

Pure: no I/O. :func:`apply_anchored_edits` resolves a parse through one revision transaction;
the repair handlers call it on the workspace the verifier materialises, and re-prompt once with
:meth:`AnchoredApplication.refusal_lines` when it refuses (SIP-0107 §22).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.handlers.impl._json_extraction import _strip_think_blocks
from squadops.cycles.revision_transaction import (
    Revision,
    RevisionOperation,
    RevisionTransaction,
    TransactionOutcome,
    base_revision_id,
    resolve_and_apply,
)
from squadops.cycles.structural_resolution import resolve_entity, syntax_error
from squadops.cycles.write_authorization import WriteGrant, normalize_ws_path

#: The fence language that marks an anchored-edit block (``edit:<path>``).
EDIT_FENCE_LANGUAGE = "edit"
SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"

_EDIT_OPEN_RE = re.compile(rf"^```{EDIT_FENCE_LANGUAGE}:(?P<path>\S+)\s*$")
_FENCE_CLOSE = "```"

#: Why an edit fence could not be read — the typed reason a retry is told.
MALFORMED_UNSAFE_PATH = "unsafe_path"
MALFORMED_TEXT_OUTSIDE_BLOCK = "text_outside_block"
MALFORMED_MISSING_DIVIDER = "missing_divider"
MALFORMED_MISSING_REPLACE = "missing_replace_marker"
MALFORMED_EMPTY_SEARCH = "empty_search"
MALFORMED_UNCLOSED_FENCE = "unclosed_fence"
MALFORMED_NO_BLOCKS = "no_blocks"
MALFORMED_UNKNOWN_BLOCK = "unknown_block"
MALFORMED_MISSING_END = "missing_end_marker"
MALFORMED_REMOVE_WITH_CONTENT = "remove_with_content"
MALFORMED_EMPTY_INSERT = "empty_insert"

END_MARKER = ">>>>>>> END"
_STRUCTURAL_OPEN_RE = re.compile(
    r"^<<<<<<< (?P<op>REPLACE|INSERT BEFORE|INSERT AFTER|REMOVE) (?P<selector>\S+)\s*$"
)
_STRUCTURAL_OPERATIONS = {
    "REPLACE": RevisionOperation.REPLACE_ENTITY,
    "INSERT BEFORE": RevisionOperation.INSERT_BEFORE_ENTITY,
    "INSERT AFTER": RevisionOperation.INSERT_AFTER_ENTITY,
    "REMOVE": RevisionOperation.REMOVE_ENTITY,
}


@dataclass(frozen=True)
class AnchoredEdit:
    path: str
    anchor: str
    replacement: str


@dataclass(frozen=True)
class StructuralEdit:
    """One structural block: an operation on the entity a selector names (§8, §9.1)."""

    path: str
    operation: RevisionOperation
    selector: str
    replacement: str


@dataclass(frozen=True)
class MalformedEdit:
    path: str
    reason: str
    detail: str


@dataclass(frozen=True)
class AnchoredEditParse:
    #: Anchored and structural edits, in emission order.
    edits: tuple[AnchoredEdit | StructuralEdit, ...] = ()
    malformed: tuple[MalformedEdit, ...] = ()

    @property
    def found(self) -> bool:
        """Whether the response carried any edit fence at all, well-formed or not."""
        return bool(self.edits or self.malformed)


def _joined(lines: list[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


class _FenceReader:
    """Reads one edit fence's blocks line by line, from just after its opener."""

    def __init__(self, path: str, lines: list[str], start: int) -> None:
        self.path = path
        self.lines = lines
        self.pos = start
        self.edits: list[AnchoredEdit | StructuralEdit] = []
        self.malformed: list[MalformedEdit] = []

    def _malformed(self, reason: str, detail: str) -> None:
        self.malformed.append(MalformedEdit(path=self.path, reason=reason, detail=detail))

    def _collect_until(self, marker: str) -> list[str] | None:
        """Lines up to ``marker`` (consumed), or None when the response ends first.

        On None the fence is taken to end at the first bare fence line after the block began —
        a block missing its marker must not swallow every file emitted after it.
        """
        began = self.pos
        collected: list[str] = []
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            self.pos += 1
            if line == marker:
                return collected
            collected.append(line)
        closes = [i for i in range(began, len(self.lines)) if self.lines[i] == _FENCE_CLOSE]
        self.pos = closes[0] + 1 if closes else len(self.lines)
        return None

    def read(self) -> int:
        """Consume the fence; return the index of the line after its close."""
        blocks = 0
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            self.pos += 1
            if line == _FENCE_CLOSE:
                if blocks == 0 and not self.malformed:
                    self._malformed(MALFORMED_NO_BLOCKS, "the edit fence holds no edit block")
                return self.pos
            if not line.strip():
                continue
            if line != SEARCH_MARKER:
                if line.startswith("<<<<<<< "):
                    if not self._read_structural(line):
                        return self.pos
                    blocks += 1
                    continue
                self._malformed(
                    MALFORMED_TEXT_OUTSIDE_BLOCK,
                    f"line {self.pos} is outside an edit block: {line[:80]!r}",
                )
                continue
            anchor = self._collect_until(DIVIDER_MARKER)
            if anchor is None:
                self._malformed(MALFORMED_MISSING_DIVIDER, "a SEARCH block has no ======= line")
                return self.pos
            replacement = self._collect_until(REPLACE_MARKER)
            if replacement is None:
                self._malformed(
                    MALFORMED_MISSING_REPLACE, "a SEARCH block has no >>>>>>> REPLACE line"
                )
                return self.pos
            blocks += 1
            if not any(a.strip() for a in anchor):
                self._malformed(MALFORMED_EMPTY_SEARCH, "a SEARCH block names no text to replace")
                continue
            self.edits.append(
                AnchoredEdit(
                    path=self.path, anchor=_joined(anchor), replacement=_joined(replacement)
                )
            )
        self._malformed(MALFORMED_UNCLOSED_FENCE, "the edit fence is never closed")
        return self.pos

    def _read_structural(self, opener: str) -> bool:
        """One structural block from its opener. False when the fence ended inside it."""
        match = _STRUCTURAL_OPEN_RE.match(opener)
        body = self._collect_until(END_MARKER)
        if body is None:
            self._malformed(MALFORMED_MISSING_END, f"{opener[:80]!r} has no >>>>>>> END line")
            return False
        if match is None:
            self._malformed(
                MALFORMED_UNKNOWN_BLOCK,
                f"{opener[:80]!r} is not SEARCH, or REPLACE / INSERT BEFORE / INSERT AFTER / "
                "REMOVE followed by one selector",
            )
            return True
        verb, selector = match.group("op"), match.group("selector")
        if verb == "REMOVE" and any(line.strip() for line in body):
            self._malformed(MALFORMED_REMOVE_WITH_CONTENT, f"REMOVE {selector} carries lines")
            return True
        if verb.startswith("INSERT") and not any(line.strip() for line in body):
            self._malformed(MALFORMED_EMPTY_INSERT, f"{verb} {selector} carries no lines")
            return True
        self.edits.append(
            StructuralEdit(
                path=self.path,
                operation=_STRUCTURAL_OPERATIONS[verb],
                selector=selector,
                replacement="" if verb == "REMOVE" else _joined(body),
            )
        )
        return True


def _scan(lines: list[str]) -> list[tuple[int, int, _FenceReader]]:
    """Each edit fence as ``(opener line index, index after its close, its reader)``."""
    fences: list[tuple[int, int, _FenceReader]] = []
    i = 0
    while i < len(lines):
        match = _EDIT_OPEN_RE.match(lines[i])
        if match is None:
            i += 1
            continue
        reader = _FenceReader(match.group("path"), lines, i + 1)
        end = reader.read()
        fences.append((i, end, reader))
        i = end
    return fences


def parse_anchored_edits(response: str) -> AnchoredEditParse:
    """Every anchored edit the response carries, and every edit fence it could not read."""
    if not response:
        return AnchoredEditParse()
    edits: list[AnchoredEdit | StructuralEdit] = []
    malformed: list[MalformedEdit] = []
    for _start, _end, reader in _scan(_strip_think_blocks(response).split("\n")):
        path = normalize_ws_path(reader.path)
        if path is None:
            malformed.append(
                MalformedEdit(
                    path=reader.path,
                    reason=MALFORMED_UNSAFE_PATH,
                    detail=f"{reader.path!r} is absolute or escapes the workspace",
                )
            )
            continue
        edits.extend(dataclasses.replace(e, path=path) for e in reader.edits)
        malformed.extend(
            MalformedEdit(path=path, reason=m.reason, detail=m.detail) for m in reader.malformed
        )
    return AnchoredEditParse(edits=tuple(edits), malformed=tuple(malformed))


def strip_edit_blocks(response: str) -> str:
    """The response without its edit fences — what the whole-file extractor may read, so an
    edit block is never taken for a file named by its path."""
    if not response:
        return response
    lines = _strip_think_blocks(response).split("\n")
    kept: list[str] = []
    cursor = 0
    for start, end, _reader in _scan(lines):
        kept.extend(lines[cursor:start])
        cursor = end
    kept.extend(lines[cursor:])
    return "\n".join(kept)


def revisions_for(parse: AnchoredEditParse) -> tuple[Revision, ...]:
    """The parse's edits as revisions, in emission order, for one transaction."""
    revisions: list[Revision] = []
    for e in parse.edits:
        if isinstance(e, StructuralEdit):
            revisions.append(
                Revision(
                    artifact_path=e.path,
                    operation=e.operation,
                    entity=e.selector,
                    replacement=e.replacement,
                )
            )
        else:
            revisions.append(
                Revision(
                    artifact_path=e.path,
                    operation=RevisionOperation.REPLACE_ANCHOR,
                    anchor=e.anchor,
                    replacement=e.replacement,
                )
            )
    return tuple(revisions)


#: The ``emission_failure`` reason a repair carries when its anchored edits were refused on the
#: retry too — a repair that failed, not one that emitted nothing, so it is never refunded
#: (SIP-0107 §22; #1053 refunds only an absent emission).
EMISSION_FAILURE_ANCHORED_EDIT_REFUSED = "anchored_edit_refused"


@dataclass(frozen=True)
class AnchoredApplication:
    """A response's anchored edits applied to the base — or everything that stopped them.

    ``outcome`` is ``None`` when a malformed edit fence refused the response before any edit
    was resolved: a partially readable response is refused whole, like a partially resolvable
    transaction (§14).
    """

    parse: AnchoredEditParse
    outcome: TransactionOutcome | None
    conflicts: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            not self.parse.malformed
            and not self.conflicts
            and self.outcome is not None
            and self.outcome.accepted
        )

    def refusal_lines(self) -> tuple[str, ...]:
        """One line per reason the edits were not applied, naming the file — what a retry is
        told (§21: typed, never a bare "failed")."""
        lines = [f"`{m.path}`: {m.reason} — {m.detail}" for m in self.parse.malformed]
        lines += [
            f"`{path}`: edited and re-emitted whole in one response — use one form per file"
            for path in self.conflicts
        ]
        if self.outcome is not None:
            for refusal in self.outcome.refusals:
                path = (
                    self.parse.edits[refusal.revision_index].path
                    if 0 <= refusal.revision_index < len(self.parse.edits)
                    else "(transaction)"
                )
                lines.append(f"`{path}`: {refusal.reason} — {refusal.detail}")
        return tuple(lines)

    def record(self) -> dict[str, Any]:
        """The transaction as evidence (§36): what was applied where, or why nothing was."""
        outcome = self.outcome
        return {
            "accepted": self.accepted,
            "edits_proposed": len(self.parse.edits),
            # §39.8: which revision modes the response proposed, accepted or not.
            "operations_proposed": [str(r.operation) for r in revisions_for(self.parse)],
            "candidate_revision_id": outcome.candidate_revision_id if outcome else None,
            "edits": [
                {
                    "path": e.artifact_path,
                    "operation": str(e.operation),
                    "start": e.start,
                    "end": e.end,
                    "pre_sha256": e.pre_sha256,
                    "replacement_chars": len(e.replacement),
                }
                for e in (outcome.edits if outcome and self.accepted else ())
            ],
            "refusals": list(self.refusal_lines()),
        }


def apply_anchored_edits(
    parse: AnchoredEditParse,
    base_files: Mapping[str, str],
    *,
    writable: Iterable[str],
    producer: str,
    task_id: str,
    whole_file_paths: Iterable[str] = (),
) -> AnchoredApplication:
    """Resolve the parse's edits against ``base_files`` under a grant of ``writable``.

    ``whole_file_paths`` are the files the same response re-emitted whole; a file both edited
    and re-emitted is refused rather than letting either silently win.
    """
    edited = {e.path for e in parse.edits}
    conflicts = tuple(sorted(edited & {p for p in whole_file_paths if p}))
    if parse.malformed:
        return AnchoredApplication(parse=parse, outcome=None, conflicts=conflicts)
    base = dict(base_files)
    transaction = RevisionTransaction(
        base_revision_id=base_revision_id(base),
        grant=WriteGrant(producer=producer, stage="anchored_repair", writable=frozenset(writable)),
        task_id=task_id,
        revisions=revisions_for(parse),
    )
    outcome = resolve_and_apply(
        base,
        transaction,
        lambda _path, _content, _region: None,
        resolve_entity=resolve_entity,
        validate_syntax=_breaks_parsing_base(base),
    )
    return AnchoredApplication(parse=parse, outcome=outcome, conflicts=conflicts)


def _breaks_parsing_base(base: Mapping[str, str]):
    """§18, for a repair: refuse a candidate that no longer parses — unless its base did not
    parse either. A repair of an already-broken file (the failure it was sent to fix may be the
    syntax error) is judged by verification, never refused for still being broken."""

    def validate(path: str, content: str) -> str | None:
        if path in base and syntax_error(path, base[path]) is not None:
            return None
        return syntax_error(path, content)

    return validate


# ---------------------------------------------------------------------------------------------
# The repair's revision form, as evidence (SIP-0107 §46a, §39.8)
# ---------------------------------------------------------------------------------------------

#: What a repair response did with the files it was offered to revise in place.
REVISION_FORM_EDITS = "edits"
REVISION_FORM_EDITS_AND_WHOLE_FILE = "edits_and_whole_file"
REVISION_FORM_WHOLE_FILE = "whole_file"
REVISION_FORM_FILL = "fill"
REVISION_FORM_NEW_FILES_ONLY = "new_files_only"
REVISION_FORM_NONE = "none"

#: §39.8's per-repair modes, by the operation a proposed revision carries.
_MODE_BY_OPERATION = {
    RevisionOperation.REPLACE_ENTITY: "structural",
    RevisionOperation.INSERT_BEFORE_ENTITY: "structural",
    RevisionOperation.INSERT_AFTER_ENTITY: "structural",
    RevisionOperation.REMOVE_ENTITY: "structural",
    RevisionOperation.REPLACE_ANCHOR: "anchored",
    RevisionOperation.REPLACE_REGION: "region",
}


def revision_form_reading(offered: Mapping[str, int], outputs: Mapping[str, Any]) -> dict[str, Any]:
    """Which form a repair response took, beside what it was offered (SIP-0107 §46a).

    ``offered`` maps each file the rendered edit form listed to the number of entities listed
    for it (empty when the form was not rendered). ``outputs`` is the repair task's outputs:
    ``anchored_edits`` when the response carried edit fences, ``artifacts`` for what it yields.

    Before §38 step 7 an offered file re-emitted whole is an **unauthorized whole-file
    fallback**: accepted, counted per cell, never a scoped transaction, so it never counts
    toward N. A file the response creates is not a fallback. The reading is pure, so the count
    the record reports is the count this function decides.
    """
    record = (
        outputs.get("anchored_edits") if isinstance(outputs.get("anchored_edits"), dict) else None
    )
    edited = sorted({str(e.get("path")) for e in (record or {}).get("edits") or []})
    emitted = [
        a
        for a in outputs.get("artifacts") or []
        if isinstance(a, dict) and a.get("name") and not a.get("emission_fallback")
    ]
    fills = [a for a in emitted if a.get("type") == "fill"]
    files = sorted({str(a["name"]) for a in emitted if a.get("type") != "fill"} - set(edited))
    whole_offered = [f for f in files if f in offered]
    new_files = [f for f in files if f not in offered]
    if record is not None:
        form = REVISION_FORM_EDITS_AND_WHOLE_FILE if whole_offered else REVISION_FORM_EDITS
    elif whole_offered:
        form = REVISION_FORM_WHOLE_FILE
    elif fills:
        form = REVISION_FORM_FILL
    elif new_files:
        form = REVISION_FORM_NEW_FILES_ONLY
    else:
        form = REVISION_FORM_NONE
    proposed = (record or {}).get("operations_proposed") or []
    failure = (
        outputs.get("emission_failure") if isinstance(outputs.get("emission_failure"), dict) else {}
    )
    return {
        "offered": dict(sorted(offered.items())),
        "form": form,
        # §39.8: structural target used, exact anchored target used, region replacement used.
        "modes": sorted({_MODE_BY_OPERATION.get(RevisionOperation(op), op) for op in proposed}),
        "failure_reason": failure.get("reason"),
        "edited": edited,
        "whole_file_offered": whole_offered,
        "new_files": new_files,
        "fills": len(fills),
        "accepted": record.get("accepted") if record is not None else None,
        "refusals": len(record.get("refusals") or []) if record is not None else 0,
        "retried": "anchored_edit_retry" in outputs,
    }

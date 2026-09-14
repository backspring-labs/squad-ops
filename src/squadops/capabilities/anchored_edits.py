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

Pure: no I/O. The handler wiring, the request template and the retry with the refusal's typed
reason are SIP-0107 step 4's second half.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from squadops.capabilities.handlers.impl._json_extraction import _strip_think_blocks
from squadops.cycles.revision_transaction import Revision, RevisionOperation
from squadops.cycles.write_authorization import normalize_ws_path

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


@dataclass(frozen=True)
class AnchoredEdit:
    path: str
    anchor: str
    replacement: str


@dataclass(frozen=True)
class MalformedEdit:
    path: str
    reason: str
    detail: str


@dataclass(frozen=True)
class AnchoredEditParse:
    edits: tuple[AnchoredEdit, ...] = ()
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
        self.edits: list[AnchoredEdit] = []
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
                    self._malformed(MALFORMED_NO_BLOCKS, "the edit fence holds no SEARCH block")
                return self.pos
            if not line.strip():
                continue
            if line != SEARCH_MARKER:
                self._malformed(
                    MALFORMED_TEXT_OUTSIDE_BLOCK,
                    f"line {self.pos} is outside a SEARCH/REPLACE block: {line[:80]!r}",
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
    edits: list[AnchoredEdit] = []
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
        edits.extend(
            AnchoredEdit(path=path, anchor=e.anchor, replacement=e.replacement)
            for e in reader.edits
        )
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
    """The parse's edits as anchored revisions, in emission order, for one transaction."""
    return tuple(
        Revision(
            artifact_path=e.path,
            operation=RevisionOperation.REPLACE_ANCHOR,
            anchor=e.anchor,
            replacement=e.replacement,
        )
        for e in parse.edits
    )

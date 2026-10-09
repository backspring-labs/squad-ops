"""A producer's dispute of a check, as a typed output (SIP-0096 §17a, change 1).

The framework has refused correct work more often than it has caught the model producing wrong
work of the same kind (SIP-0096 §17a lists the cases), and the producer had no way to say so:
the repair template asks it to "say why in one line" and nothing reads that line. #1581 is the
sharpest case: a dev repair answered, correctly, that the file it was aimed at was right and the
qa suite was wrong, and the framework read that as an empty emission.

A build or repair task may now end its response with ONE fenced block:

    ```disputed_checks
    - check: acceptance:declared_imports
      file: frontend/src/views/RunList.jsx
      criterion_id: vc-view-compiles-run-list
      reason: the @/lib alias is declared in the tsconfig paths the check does not read
    ```

The block is stripped from the response before anything extracts files from it — its fence has
no path, and the single-expected-file fallback would otherwise store it AS that file — and its
entries are carried on the task's outputs as ``disputed_checks``. A dispute never credits, never
blocks and never turns a failure into a pass: it is read and adjudicated (§17a changes 2–4).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

from squadops.cycles.contract_expectations import typed_check_and_params
from squadops.cycles.verification_normalize import row_is_blocking_failure

logger = logging.getLogger(__name__)

#: The fence's info string, and the outputs key the entries ride on.
DISPUTED_CHECKS = "disputed_checks"
#: One block per response, from its opening fence to its closing one. The info string is the
#: whole word, so a file fenced ``yaml:disputed_checks.yaml`` is never read as a dispute.
_BLOCK = re.compile(
    r"^[ \t]{0,3}```[ \t]*" + DISPUTED_CHECKS + r"[ \t]*\n(?P<body>.*?)^[ \t]{0,3}```[ \t]*$\n?",
    re.M | re.S,
)
#: What a dispute is keyed by, and what it must say. ``check`` names the row; ``file`` and
#: ``criterion_id`` narrow it when the same check ran on several files or criteria.
_FIELDS = ("check", "file", "criterion_id", "reason")
#: A field's line in the block: an optional list dash, the field's name, a colon, and the rest of
#: the line as its value. ``acceptance:declared_imports`` has no space after its colon, so a check
#: name on a line of its own is a value, never a field.
_FIELD_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<dash>-[ \t]+)?(?P<key>[A-Za-z_][\w-]*)[ \t]*:(?:[ \t]+(?P<value>.*))?$"
)
#: A YAML block-scalar header on a field's line: the value is on the lines below it.
_BLOCK_SCALAR_INDICATORS = frozenset({">", "|", ">-", "|-", ">+", "|+"})
_QUOTES = "\"'`"


#: The prefix the typed-acceptance seam gives a criterion's row (``handlers/cycle/base.py``). A
#: criterion is listed under its row's name, so the name a dispute quotes is the one it matches.
_TYPED_ROW_PREFIX = "acceptance:"


def criterion_identities(criteria: Iterable[Any] | None) -> list[str]:
    """One line per typed criterion a build task is judged by: the check as its row will be
    named, its file and its criterion id. Prose criteria are not checks and are not listed.

    The expectation lines a build task reads say what each criterion requires and never name
    it, so without these a dispute could only paraphrase the check it means.
    """
    lines = []
    for entry in criteria or ():
        typed = typed_check_and_params(entry)
        if typed is None:
            continue
        check, params = typed
        criterion_id = entry.get("id") if isinstance(entry, Mapping) else getattr(entry, "id", None)
        lines.append(_identity(f"{_TYPED_ROW_PREFIX}{check}", params.get("file"), criterion_id))
    return lines


def failing_row_identities(rows: Iterable[Any] | None) -> list[str]:
    """One line per failing row a repair is aimed at — its check, file, criterion id and the
    reason it failed. A row that passed, or failed only as advice, is nothing to dispute."""
    lines = []
    for row in rows or ():
        if not isinstance(row, Mapping) or not row.get("check") or not row_is_blocking_failure(row):
            continue
        line = _identity(str(row["check"]), _row_file(row), row.get("criterion_id"))
        reason = str(row.get("reason") or "").strip()
        lines.append(f"{line} — failed: {reason}" if reason else line)
    return lines


def contested_row_lines(rows: Iterable[Any] | None) -> list[str]:
    """One line per contested row, for the analyzer's question (SIP-0096 §17a change 3): the
    row's identity, why it failed, and who disputed it and why."""
    lines = []
    for row in rows or ():
        contest = row.get("contested") if isinstance(row, Mapping) else None
        if not isinstance(contest, Mapping):
            continue
        line = _identity(str(row.get("check")), _row_file(row), row.get("criterion_id"))
        failed = str(row.get("reason") or "").strip()
        by = contest.get("by") or "the producer"
        lines.append(
            f"{line} — failed: {failed or '(no reason given)'} — disputed by {by}: "
            f"{contest.get('reason')}"
        )
    return lines


def rule_contests(
    rows: Iterable[Any] | None, rulings: Iterable[Any] | None
) -> tuple[list[dict], list[dict], list[dict]]:
    """The contested rows as the analyzer ruled them (SIP-0096 §17a changes 4–5):
    ``(confirmed, rejected, unruled)``, each entry the row's identity, the dispute and the
    ruling. A ruling names a row the way a dispute does, and a confirming ruling wins over a
    rejecting one. A ruling that names no contested row decides nothing."""
    contested = [r for r in rows or () if isinstance(r, Mapping) and r.get("contested")]
    verdicts: dict[int, tuple[bool, str]] = {}
    for ruling in rulings or ():
        if not isinstance(ruling, Mapping) or not isinstance(ruling.get("dispute_confirmed"), bool):
            continue
        for i, row in enumerate(contested):
            if dispute_names(ruling, row) and not verdicts.get(i, (False, ""))[0]:
                verdicts[i] = (ruling["dispute_confirmed"], str(ruling.get("reason") or ""))
    confirmed: list[dict] = []
    rejected: list[dict] = []
    unruled: list[dict] = []
    for i, row in enumerate(contested):
        entry = {
            "check": str(row.get("check")),
            "file": _row_file(row),
            "criterion_id": row.get("criterion_id"),
            "failed": row.get("reason"),
            "contested": dict(row["contested"]),
        }
        if i not in verdicts:
            unruled.append(entry)
            continue
        entry["ruling"] = verdicts[i][1]
        (confirmed if verdicts[i][0] else rejected).append(entry)
    return confirmed, rejected, unruled


def contest_name(contest: Mapping[str, Any]) -> str:
    """A confirmed contest's check as the run's terminal decision names it."""
    name = str(contest.get("check"))
    if contest.get("file"):
        name += f" on {contest['file']}"
    if contest.get("criterion_id"):
        name += f" ({contest['criterion_id']})"
    return name


def dispute_names(dispute: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Whether ``dispute`` names ``row``: the same check, with or without the ``acceptance:``
    prefix, and the same file and criterion wherever the dispute gives them."""
    if _bare(row.get("check")) != _bare(dispute.get("check")):
        return False
    if dispute.get("file") and str(_row_file(row) or "") != str(dispute["file"]):
        return False
    criterion = dispute.get("criterion_id")
    return not criterion or str(row.get("criterion_id") or "") == str(criterion)


def mark_contested(
    rows: Iterable[Any] | None, disputes: Iterable[Any] | None
) -> tuple[list[Any], list[dict[str, Any]]]:
    """``rows`` with ``contested: {by, reason}`` on each blocking-failed row a dispute names,
    and the disputes that named none (SIP-0096 §17a change 2).

    Only a blocking failure can be contested: a row that passed, or failed only as advice,
    has nothing to dispute, so a dispute naming only such rows is unmatched. A dispute
    without file or criterion names every failing row of its check. Where two disputes name
    one row, the first stands. Pure: the rows handed in are not changed.
    """
    marked = list(rows or ())
    unmatched: list[dict[str, Any]] = []
    for dispute in disputes or ():
        if not isinstance(dispute, Mapping) or not dispute.get("reason"):
            continue
        named = False
        for i, row in enumerate(marked):
            if not isinstance(row, Mapping) or not row_is_blocking_failure(row):
                continue
            if not dispute_names(dispute, row):
                continue
            named = True
            if not row.get("contested"):
                contest = {"by": dispute.get("by"), "reason": str(dispute["reason"])}
                marked[i] = {**row, "contested": contest}
        if not named:
            unmatched.append(dict(dispute))
    return marked, unmatched


def _bare(check: Any) -> str:
    name = str(check or "")
    return name.removeprefix(_TYPED_ROW_PREFIX)


def row_file(row: Mapping[str, Any]) -> str | None:
    """The file a check row is about: a typed row's ``params.file``, else its own ``file``."""
    return _row_file(row)


def _row_file(row: Mapping[str, Any]) -> str | None:
    params = row.get("params")
    return (params.get("file") if isinstance(params, Mapping) else None) or row.get("file")


def _identity(check: str, file: Any, criterion_id: Any) -> str:
    line = f"- check: `{check}`"
    if file:
        line += f", file: `{file}`"
    if criterion_id:
        line += f", criterion_id: `{criterion_id}`"
    return line


def split_disputed_checks(content: str) -> tuple[str, list[dict[str, str]]]:
    """``content`` without its ``disputed_checks`` block(s), and the disputes they held.

    An entry without a ``check`` and a ``reason`` disputes nothing and is logged; the block is
    still removed, because a fence left in the response is a fence the extractor could store as
    a file.
    """
    if not content or DISPUTED_CHECKS not in content:
        return content, []
    disputes: list[dict[str, str]] = []
    for match in _BLOCK.finditer(content):
        disputes.extend(_entries(match.group("body")))
    return _BLOCK.sub("", content), disputes


def _entries(body: str) -> list[dict[str, str]]:
    items = _read_block(body)
    if not items and body.strip():
        logger.warning("disputed_checks: the block holds no entry; it disputes nothing")
    entries: list[dict[str, str]] = []
    for item in items:
        entry = {key: item[key] for key in _FIELDS if item.get(key)}
        if not entry.get("check") or not entry.get("reason"):
            logger.warning(
                "disputed_checks: an entry without a check and a reason disputes nothing: %r",
                item,
            )
            continue
        entries.append(entry)
    return entries


def _read_block(body: str) -> list[dict[str, str]]:
    """The block's entries, read in the shape the appendix shows (#2168): an entry starts at a
    ``- `` line, a field is one ``field: value`` line whose value is the rest of the line, and a
    line indented deeper than its field continues the value.

    Not YAML. A reason is prose about the code a check read, and it quotes that code
    (``declares `id: number```); a check is copied as the appendix lists it, in backticks. YAML
    refuses both, and one refusal dropped every dispute in the block.
    """
    items: list[dict[str, str]] = []
    item: dict[str, str] = {}
    key: str | None = None
    key_column = -1
    for line in body.splitlines():
        if not line.strip():
            continue
        field = _FIELD_LINE.match(line)
        starts_entry = bool(field and field["dash"])
        column = len(line) - len(line.lstrip())
        if key is not None and not starts_entry and (field is None or column > key_column):
            item[key] = f"{item[key]} {line.strip()}".strip()
            continue
        if field is None:
            continue
        if starts_entry or not items:
            item = {}
            items.append(item)
        key = field["key"]
        key_column = len(field["indent"]) + len(field["dash"] or "")
        value = (field["value"] or "").strip()
        item[key] = "" if value in _BLOCK_SCALAR_INDICATORS else value
    return [{name: _unquoted(value) for name, value in each.items()} for each in items]


def _unquoted(value: str) -> str:
    """``value`` without one pair of quotes or backticks around the whole of it."""
    if len(value) >= 2 and value[0] == value[-1] in _QUOTES and value[0] not in value[1:-1]:
        return value[1:-1].strip()
    return value

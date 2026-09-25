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

import yaml

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

    A block that does not parse, or an entry without a ``check`` and a ``reason``, disputes
    nothing and is logged; the block is still removed, because a fence left in the response is
    a fence the extractor could store as a file.
    """
    if not content or DISPUTED_CHECKS not in content:
        return content, []
    disputes: list[dict[str, str]] = []
    for match in _BLOCK.finditer(content):
        disputes.extend(_entries(match.group("body")))
    return _BLOCK.sub("", content), disputes


def _entries(body: str) -> list[dict[str, str]]:
    try:
        parsed: Any = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        logger.warning("disputed_checks: the block does not parse (%s); it disputes nothing", exc)
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        logger.warning("disputed_checks: the block is not a list of disputes; it disputes nothing")
        return []
    entries: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        entry = {key: str(item[key]).strip() for key in _FIELDS if item.get(key) not in (None, "")}
        if not entry.get("check") or not entry.get("reason"):
            logger.warning(
                "disputed_checks: an entry without a check and a reason disputes nothing: %r",
                item,
            )
            continue
        entries.append(entry)
    return entries

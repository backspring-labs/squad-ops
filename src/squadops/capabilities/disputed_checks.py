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
from typing import Any

import yaml

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

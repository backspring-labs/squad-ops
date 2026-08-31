"""What an LLM call actually emitted, in one greppable line (#924, #928).

**Why this is its own module.** #924 introduced this capture inside
``handlers/cycle/base.py`` on the assumption that handlers share one LLM seam.
They do not: ``develop``, ``qa_test``, ``builder``, ``governance``, the planning
base, the plan-authoring service and the correction decision handler each carry
their *own* ``chat_stream_with_usage`` call and their own ``response.content``
read. The capture therefore covered a seam that none of the window's interesting
emissions pass through — the qa author's fill emission least of all.

Living in ``cycle/base.py`` also made it unreachable from ``planning/`` and
``impl/`` without a cross-package import into a handler base class. The concern
is "record what came back from the model", which belongs to none of those
handlers; it gets its own home, and ``test_emission_capture_covers_every_seam``
holds every seam to it.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: A fence delimiter at the start of a line, with whatever info string follows it.
#: Openers and closers are told apart by tracking depth, not by the info string —
#: a closing ``` has no info string and would otherwise count as a bare fence.
_FENCE_LINE = re.compile(r"^\s{0,3}```(.*)$")

#: The fill protocol's own address form.
_FILL_PREFIX = "fill:slot-"


def classify_fences(text: str) -> dict[str, int]:
    """Count fence openers by kind: ``fill``, ``path``, ``plain``.

    **Why this is parsed rather than substring-counted (#932).** The first version
    matched literal prefixes — ` ```typescript: ` and ` ```python: ` — and called
    everything else ``plain``. Every other language tag the models actually use was
    therefore reported as an *unaddressed* fence, which is precisely the failure mode
    this instrument exists to detect. Live during window roll 6: dev emitted
    ` ```tsx:app/page.tsx ` and builder emitted ` ```dockerfile:Dockerfile `, both
    correctly addressed, and both were reported as bare. An instrument that reports a
    healthy emission as broken is worse than no instrument — it manufactures the
    diagnosis it was built to prevent, and it did: "the UI tasks emitted bare fences"
    was written down before the vault showed the files had landed fine.

    A fence is **addressed** when its info string carries a ``<tag>:<path>`` form. The
    tag is not enumerated, because the point is to notice what the model did, not to
    assert what it should have done.
    """
    counts = {"fill": 0, "path": 0, "plain": 0}
    inside = False
    for line in text.splitlines():
        match = _FENCE_LINE.match(line)
        if not match:
            continue
        if inside:  # this delimiter closes the open fence
            inside = False
            continue
        inside = True
        info = match.group(1).strip()
        if info.startswith(_FILL_PREFIX):
            counts["fill"] += 1
        elif ":" in info:
            counts["path"] += 1
        else:
            # bare ``` or a language tag with no path — nothing addresses a file
            counts["plain"] += 1
    return counts


def log_emission_shape(
    handler_name: str,
    content: object,
    completion_tokens: object,
    reasoning_tokens: object = None,
) -> None:
    """Record the shape of one completion.

    **Why this exists (#924).** SIP-0104 window rolls 3 and 5 both ended with every
    scaffold slot unfilled, and nothing recorded what the qa author emitted: fills are
    parsed and stripped before extraction, so a successful fill leaves no artifact and
    a failed one leaves no trace at all. Three separate diagnoses were made from the
    *result* rather than the emission, and two of them were wrong — the third only
    landed because the raw completion was reproduced by hand against the live model.

    A protocol whose failures cannot be inspected can only be repaired by guessing.
    This is deliberately cheap and unconditional: shape, not content. Length, fence
    counts by kind, and a short head sample — enough to separate "emitted nothing",
    "emitted the wrong fence", and "emitted fills that the parser rejected" at a
    glance, without persisting whole completions or their prompt material.

    **Why ``reasoning_tokens`` (#924, closable only since #410).** The issue named
    ``chars=0 completion_tokens=6866`` as the line that would confirm its diagnosis
    outright. It does not: that shape is equally consistent with "the model thought the
    budget away and never reached the emission" and "the model emitted 6,866 tokens the
    parser rejected", which have opposite fixes. The reasoning split separates them —
    ``chars=0 completion_tokens=6866 reasoning_tokens=6800`` is the first, and
    ``reasoning_tokens=0`` the second. The count was on the port already; #410 is what
    made adapters actually populate it, so the line can now say which failure it is
    rather than leaving the reader to infer.
    """
    if content is None:
        return
    text = str(content)
    counts = classify_fences(text)
    head = " ".join(text[:160].split())
    # Rendered as a fraction rather than a bare count: "6800 of 6866" reads as budget
    # exhaustion at a glance, where two separate numbers have to be divided by the reader.
    reasoning_part = "" if reasoning_tokens is None else f" reasoning_tokens={reasoning_tokens}"
    logger.info(
        "%s emission shape: chars=%d completion_tokens=%s%s fences=%s head=%r",
        handler_name,
        len(text),
        completion_tokens,
        reasoning_part,
        counts,
        head,
    )

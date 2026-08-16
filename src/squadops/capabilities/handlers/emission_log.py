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

logger = logging.getLogger(__name__)

#: Fence kinds worth counting separately. Order matters only for readability;
#: ``plain`` is reported net of the addressed kinds so the numbers add up.
_EMISSION_FENCES: tuple[tuple[str, str], ...] = (
    ("fill", "```fill:slot-"),
    ("path", "```typescript:"),
    ("py", "```python:"),
    ("plain", "```"),
)


def log_emission_shape(handler_name: str, content: object, completion_tokens: object) -> None:
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
    """
    if content is None:
        return
    text = str(content)
    counts = {}
    for label, marker in _EMISSION_FENCES:
        counts[label] = text.count(marker)
    # A plain-fence count includes the addressed ones; report it net so the numbers add up.
    counts["plain"] = max(0, counts["plain"] - 2 * (counts["fill"] + counts["path"] + counts["py"]))
    head = " ".join(text[:160].split())
    logger.info(
        "%s emission shape: chars=%d completion_tokens=%s fences=%s head=%r",
        handler_name,
        len(text),
        completion_tokens,
        counts,
        head,
    )

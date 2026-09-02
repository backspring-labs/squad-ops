"""The handoff document's required sections — one matcher for every seam that reads it (#1255).

The builder handler validated the sections privately (``_validate_builder_output``) and
nothing else could: after #1252 stripped the plan's handoff regexes, a builder task carried
no typed criterion over its own document, so a repair of the exact defect the handler had
named was ``unverifiable / no_typed_criteria`` and discarded unheard (the 1.7.1 React
shakeout ``cyc_c6db3ffc1f4e``, round 0 — the repaired document had every section). The rule
lives here, read by the handler's validation (the backstop) and by the ``sections_present``
evaluator (the criterion the framework binds and the planner never authors), so the two
cannot disagree about what a section is.

The match is the one the builder has always applied: case-insensitive, a section is present
when any of its keywords appears anywhere in the document. Loose by design — it accepts a
heading the author phrased their own way (``## How to Run the Backend``) — and unchanged here
so the roll window opens on the rule the line has been running.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Per required section, the phrasings that count as it. A section absent from this table
#: is matched by its own lower-cased text.
SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "## How to Run": ("how to run", "running", "## run"),
    "## How to Test": ("how to test", "testing", "## test"),
    "## Expected Behavior": ("expected behavior", "expected output", "## expected"),
}


def section_present(content: str, section: str) -> bool:
    """Whether ``section`` is present in ``content`` under the builder's keyword rule."""
    lowered = content.lower()
    keywords = SECTION_KEYWORDS.get(section, (section.lower(),))
    return any(keyword in lowered for keyword in keywords)


def missing_sections(content: str, sections: Iterable[str]) -> list[str]:
    """The required ``sections`` ``content`` does not carry, in the order they were required."""
    return [section for section in sections if not section_present(content, section)]

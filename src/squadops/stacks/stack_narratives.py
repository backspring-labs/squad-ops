"""Architecture narratives — what a stack's code looks like, for the stages that design it.

**Separate from ``prompts/profile_narratives/`` on purpose, and the separation is a bug fix.**
Those are the *builder's* prompts: they open *"You are assembling…"* and instruct *"do not
regenerate application code — focus on packaging, configuration, and operational readiness."*
Correct for Bob, actively wrong for a designer.

#842 pointed framing's target-stack section at that directory, so every framing stage on a
`fullstack_fastapi_react` cycle was handed the packaging prompt under a heading reading
"TARGET STACK — decided, not proposed" — telling the stage that authors the technical design
not to write application code. Two audiences reading one asset, which is the ownership smell
CLAUDE.md's edit-time rule exists to catch, arriving one release after that rule was written.

So: **``profile_narratives/`` answers "how is this stack packaged"; this answers "how is this
stack written".** They are both per-stack and they are not the same question — the #92
invariant makes the difference concrete, since a builder narrative must not enumerate
filenames while an architecture narrative is largely *about* where things live.
"""

from __future__ import annotations

from pathlib import Path

from squadops.prompts import __file__ as _prompts_pkg

_NARRATIVES_DIR = Path(_prompts_pkg).parent / "stack_narratives"


def stack_narrative(stack: str) -> str:
    """How ``stack``'s code is laid out, or ``""`` if it declares no narrative.

    Deliberately tolerant where ``build_profiles._narrative`` is loud. That one raises at
    import for a registered builder profile missing its file — a registration error, correctly
    fatal. This is asked at prompt-assembly time about a stack that may legitimately not have
    one yet, and a framing stage must not die because a narrative is absent. The caller renders
    nothing rather than an authoritative-looking empty heading.
    """
    path = _NARRATIVES_DIR / f"{stack}.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text

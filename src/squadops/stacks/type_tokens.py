"""Manifest type-token helpers shared by the manifest model and every stack expander.

``list[X]`` is the manifest's one collection form. ``base_type_name`` unwraps it to the
innermost name — the right answer for naming a model class, and deliberately *not* the
answer for asserting an element kind: ``response_shape._element_token`` declines to look
more than one level down, and says why. A leaf, importing nothing from this package, so the
manifest model (``scaffold.py``) and the stack modules can both use it without a cycle. It
lived inside stack #1's inline expander until #1131 moved that block out and the shared
manifest lint was left calling a stack module's private — this is the vocabulary's home.
"""

from __future__ import annotations


def base_type_name(type_str: str) -> str:
    """The bare entity/model name inside a type token (``list[RunEvent]`` -> ``RunEvent``)."""
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        return base_type_name(t[len("list[") : -1])
    return t

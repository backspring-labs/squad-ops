"""Fields of a YAML document a model authored (#1990).

An optional list of strings is read one way: absent or empty is ``[]``, a list gives its items
as stripped, non-empty strings, and anything else is not a list. Three parsers held their own
copy of that rule. ``merge_decisions`` and ``plan_guidance`` refuse a field that is not a list;
``proposed_role_tasks`` drops one, because its sections are advisory (#187).
"""

from __future__ import annotations


def str_list(raw: object, field: str) -> list[str]:
    """``raw`` as stripped, non-empty strings, or ``[]`` when absent or empty. Raises
    ``ValueError`` naming ``field`` when ``raw`` is anything but a list."""
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a YAML list")
    return [str(x).strip() for x in raw if str(x).strip()]

"""
Role slug → human-friendly display label.

Presentation concern only — no agent instance names live here.
"""

ROLE_DISPLAY_LABELS: dict[str, str] = {
    "lead": "Lead",
    "dev": "Developer",
    "strat": "Strategy",
    "qa": "QA",
    "builder": "Builder",
    "data": "Analytics",
}


def get_role_label(role_slug: str) -> str:
    """Return a human-friendly label for a role slug, falling back to title-case."""
    return ROLE_DISPLAY_LABELS.get(role_slug, role_slug.title())

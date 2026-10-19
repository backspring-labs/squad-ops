"""SquadOps Memory plugin: a project's memory records and one page per record (SIP-0110 §A.3.11, #2182)."""


def register(ctx):
    """Register Memory plugin contributions (1 nav + 1 panel)."""
    # ── Navigation ──────────────────────────────────────────────
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Memory",
            "icon": "bookmark",
            "icon_path": "M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z",
            "priority": 550,
            "target": {"type": "panel", "panel_id": "memory"},
        },
    )

    # ── Panels ──────────────────────────────────────────────────
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "memory",
            "component": "squadops-memory-perspective",
            "priority": 800,
        },
    )

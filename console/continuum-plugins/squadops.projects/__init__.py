"""SquadOps Projects plugin — project browsing and squad profile management."""


def register(ctx):
    """Register Projects plugin contributions (1 nav + 2 panels + 1 command)."""
    # ── Navigation ──────────────────────────────────────────────
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Projects",
            "icon": "folder",
            "icon_path": "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
            "priority": 600,
            "target": {"type": "panel", "panel_id": "discovery"},
        },
    )

    # ── Panels ──────────────────────────────────────────────────
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "discovery",
            "component": "squadops-projects-list",
            "priority": 800,
        },
    )

    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "discovery",
            "component": "squadops-projects-profiles",
            "priority": 600,
        },
    )

    # ── Commands ────────────────────────────────────────────────
    ctx.register_contribution(
        "command",
        {
            "id": "squadops.set_active_profile",
            "label": "Set Active Profile",
            "action": "squadops.set_active_profile",
            "danger_level": "confirm",
        },
    )

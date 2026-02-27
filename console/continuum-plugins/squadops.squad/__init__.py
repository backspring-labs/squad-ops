"""SquadOps Squad plugin — agent health, profiles, models, cycle comparison."""


def register(ctx):
    """Register Squad plugin contributions (1 nav + 1 panel)."""
    # ── Navigation ──────────────────────────────────────────────
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Squad",
            "icon": "users",
            "icon_path": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
            "priority": 700,
            "target": {"type": "panel", "panel_id": "squad"},
        },
    )

    # ── Panels ──────────────────────────────────────────────────
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "squad",
            "component": "squadops-squad-perspective",
            "priority": 800,
        },
    )

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

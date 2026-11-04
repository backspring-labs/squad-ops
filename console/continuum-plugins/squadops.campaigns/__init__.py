"""SquadOps Campaigns plugin: every Project's Campaigns and one Campaign's state, ledger, digest,
escalations and control log. Read-only in 2.6 (#2834; the 2.6 plan's D13; SIP-0069 §14)."""


def register(ctx):
    """Register Campaigns plugin contributions (1 nav + 1 panel; no command: it writes nothing)."""
    # ── Navigation ──────────────────────────────────────────────
    ctx.register_contribution(
        "nav",
        {
            "slot": "ui.slot.left_nav",
            "label": "Campaigns",
            "icon": "flag",
            "icon_path": "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
            "priority": 650,
            "target": {"type": "panel", "panel_id": "campaigns"},
        },
    )

    # ── Panels ──────────────────────────────────────────────────
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "campaigns",
            "component": "squadops-campaigns-perspective",
            "priority": 800,
        },
    )

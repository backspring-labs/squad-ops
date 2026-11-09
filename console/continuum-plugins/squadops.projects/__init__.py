"""SquadOps Projects plugin — project browsing, goal sets and squad profile management."""


def register(ctx):
    """Register Projects plugin contributions (1 nav + 3 panels + 2 commands)."""
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

    # SIP-0115 §8.3 (slice 4, #2887): the selected Project's goal set, its backlog as a chosen
    # Campaign stands on it, the candidates waiting and the revision history.
    ctx.register_contribution(
        "panel",
        {
            "slot": "ui.slot.main",
            "perspective": "discovery",
            "component": "squadops-projects-goals",
            "priority": 700,
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

    # The goals panel's edit: the Project's next goal-set revision, written through the API.
    ctx.register_contribution(
        "command",
        {
            "id": "squadops.revise_goal_set",
            "label": "Write Goal-Set Revision",
            "action": "squadops.revise_goal_set",
            "danger_level": "confirm",
        },
    )

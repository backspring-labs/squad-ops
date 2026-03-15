"""SquadOps Chat plugin — console messaging with agents via drawer overlay."""


def register(ctx):
    """Register Chat plugin contributions."""
    ctx.register_contribution(
        "panel",
        {
            "id": "agent_chat",
            "slot": "ui.slot.drawer",
            "component": "squadops-chat-drawer",
            "title": "Chat with Joi",
            "width": "400px",
            "priority": 200,
        },
    )

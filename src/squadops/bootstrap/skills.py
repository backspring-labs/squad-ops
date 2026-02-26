"""Skill bootstrap - Auto-registration of all skills.

Provides factory functions for creating skill registries
with all skills auto-discovered and registered.

Part of SIP-0.8.8 Phase 7.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Import skill modules for auto-discovery
from squadops.agents.skills import builder, data, dev, lead, qa, shared, strat
from squadops.agents.skills.registry import SkillRegistry

if TYPE_CHECKING:
    from squadops.agents.skills.base import Skill

logger = logging.getLogger(__name__)


# Skill modules by role
SKILL_MODULES = {
    "shared": shared,
    "lead": lead,
    "dev": dev,
    "qa": qa,
    "strat": strat,
    "data": data,
    "builder": builder,
}

# Role -> skill module mappings
ROLE_SKILL_MODULES = {
    "lead": ["shared", "lead"],
    "dev": ["shared", "dev"],
    "qa": ["shared", "qa"],
    "strat": ["shared", "strat"],
    "data": ["shared", "data"],
    "builder": ["shared", "builder"],
}


def get_all_skills() -> list[type[Skill]]:
    """Get all skill classes from all modules.

    Returns:
        List of all skill classes
    """
    all_skills: list[type[Skill]] = []

    for module_name, module in SKILL_MODULES.items():
        if hasattr(module, "SKILLS"):
            skills = module.SKILLS
            all_skills.extend(skills)
            logger.debug(
                f"Discovered {len(skills)} skills from {module_name}",
            )

    return all_skills


def get_skills_for_role(role: str) -> list[type[Skill]]:
    """Get skill classes available to a specific role.

    Args:
        role: Role ID (lead, dev, qa, strat, data)

    Returns:
        List of skill classes for the role
    """
    module_names = ROLE_SKILL_MODULES.get(role, ["shared"])
    skills: list[type[Skill]] = []

    for module_name in module_names:
        module = SKILL_MODULES.get(module_name)
        if module and hasattr(module, "SKILLS"):
            skills.extend(module.SKILLS)

    return skills


def create_skill_registry(
    roles: list[str] | None = None,
    include_shared: bool = True,
) -> SkillRegistry:
    """Create a skill registry with auto-registered skills.

    Args:
        roles: Optional list of roles to include skills for.
               If None, includes all skills.
        include_shared: Whether to include shared skills (default True)

    Returns:
        SkillRegistry with skills registered
    """
    registry = SkillRegistry()

    if roles is None:
        # Register all skills
        skills = get_all_skills()
    else:
        # Register skills for specified roles
        skill_set: set[type[Skill]] = set()

        if include_shared:
            skill_set.update(get_skills_for_role("shared"))

        for role in roles:
            skill_set.update(get_skills_for_role(role))

        skills = list(skill_set)

    # Register each skill
    for skill_class in skills:
        try:
            skill = skill_class()
            registry.register(skill)
            logger.debug(f"Registered skill: {skill.name}")
        except Exception as e:
            logger.warning(f"Failed to register skill {skill_class}: {e}")

    logger.info(f"Created skill registry with {len(registry.list_skills())} skills")

    return registry

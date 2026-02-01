"""Shared skills used across all agent roles.

These are foundational skills that provide common operations.
Part of SIP-0.8.8 Phase 4.
"""
from squadops.agents.skills.shared.file_read import FileReadSkill
from squadops.agents.skills.shared.file_write import FileWriteSkill
from squadops.agents.skills.shared.llm_query import LLMQuerySkill
from squadops.agents.skills.shared.memory_recall import MemoryRecallSkill
from squadops.agents.skills.shared.memory_store import MemoryStoreSkill

# Skills exported for auto-discovery
SKILLS = [
    LLMQuerySkill,
    FileReadSkill,
    FileWriteSkill,
    MemoryStoreSkill,
    MemoryRecallSkill,
]

__all__ = [
    "LLMQuerySkill",
    "FileReadSkill",
    "FileWriteSkill",
    "MemoryStoreSkill",
    "MemoryRecallSkill",
    "SKILLS",
]

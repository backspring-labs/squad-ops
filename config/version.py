# SquadOps Framework Version Management
# This file is the single source of truth for the SquadOps framework version

# Framework Version
SQUADOPS_VERSION = "0.1.4"

# Agent Versions (individual agent versions)
AGENT_VERSIONS = {
    "max": "1.0.0",
    "neo": "1.0.0", 
    "nat": "1.0.0",
    "joi": "1.0.0",
    "data": "1.0.0",
    "eve": "1.0.0",
    "quark": "1.0.0",
    "og": "1.0.0",
    "glyph": "1.0.0",
    "hal": "1.0.0"
}

# Configuration Versions
CONFIG_VERSIONS = {
    "max": {"llm": "llama3.1:8b", "config": "lead-agent"},
    "neo": {"llm": "qwen2.5:7b", "config": "dev-agent"},
    "nat": {"llm": "mock", "config": "strategy-agent"},
    "joi": {"llm": "mock", "config": "comms-agent"},
    "data": {"llm": "mock", "config": "data-agent"},
    "eve": {"llm": "mock", "config": "qa-agent"},
    "quark": {"llm": "mock", "config": "finance-agent"},
    "og": {"llm": "mock", "config": "curator-agent"},
    "glyph": {"llm": "mock", "config": "creative-agent"},
    "hal": {"llm": "mock", "config": "audit-agent"}
}

# Version History
VERSION_HISTORY = {
    "max": [
        {"version": "1.0.0", "date": "2025-10-05", "llm": "llama3.1:8b", "notes": "Initial version with local LLM"},
    ],
    "neo": [
        {"version": "1.0.0", "date": "2025-10-05", "llm": "qwen2.5:7b", "notes": "Initial version with file modification capabilities"},
    ]
}

def get_framework_version():
    """Get the current SquadOps framework version"""
    return SQUADOPS_VERSION

def get_agent_version(agent_name):
    """Get version for a specific agent"""
    return AGENT_VERSIONS.get(agent_name.lower(), "unknown")

def get_agent_config(agent_name):
    """Get configuration for a specific agent"""
    return CONFIG_VERSIONS.get(agent_name.lower(), {})

def update_agent_version(agent_name, version, llm=None, config=None, notes=""):
    """Update agent version and add to history"""
    agent_key = agent_name.lower()
    AGENT_VERSIONS[agent_key] = version
    
    if agent_key not in VERSION_HISTORY:
        VERSION_HISTORY[agent_key] = []
    
    VERSION_HISTORY[agent_key].append({
        "version": version,
        "date": "2025-10-05",  # Would use datetime.now().isoformat() in real implementation
        "llm": llm or CONFIG_VERSIONS.get(agent_key, {}).get("llm", "unknown"),
        "notes": notes
    })

def get_version_history(agent_name):
    """Get version history for a specific agent"""
    return VERSION_HISTORY.get(agent_name.lower(), [])

def rollback_agent(agent_name, target_version):
    """Rollback agent to a previous version"""
    agent_key = agent_name.lower()
    history = VERSION_HISTORY.get(agent_key, [])
    
    for entry in reversed(history):
        if entry["version"] == target_version:
            AGENT_VERSIONS[agent_key] = target_version
            return True
    return False

# Version increment rules:
# 0.1.X - Development phase (current)
# 0.2.X - Production ready (when 100% agent work + multi-agent + production deployment)
# 1.0.X - Stable release (when enterprise features + external users)

# Current status: 0.1.4 (WarmBoot run-004)
# Next increment: 0.1.5 (WarmBoot run-005)
# Major increment: 0.2.0 (Production ready)
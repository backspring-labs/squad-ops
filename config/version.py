# SquadOps Version Management

# Core Framework Version
FRAMEWORK_VERSION = "1.0.0"

# Agent Versions - Update these when testing new configurations
AGENT_VERSIONS = {
    "max": "1.0.0",
    "neo": "1.0.0", 
    "nat": "1.0.0",
    "joi": "1.0.0",
    "data": "1.0.0",
    "eve": "1.0.0",
    "hal": "1.0.0",
    "quark": "1.0.0",
    "og": "1.0.0",
    "glyph": "1.0.0"
}

# Configuration Versions - Track LLM/model changes
CONFIG_VERSIONS = {
    "max": {
        "llm": "llama-3-13b",
        "config": "governance-v1",
        "version": "1.0.0"
    },
    "neo": {
        "llm": "codellama-70b", 
        "config": "deductive-v1",
        "version": "1.0.0"
    },
    "nat": {
        "llm": "mixtral-8x7b",
        "config": "abductive-v1", 
        "version": "1.0.0"
    },
    "joi": {
        "llm": "llama-3-13b",
        "config": "empathetic-v1",
        "version": "1.0.0"
    },
    "data": {
        "llm": "mixtral-8x7b",
        "config": "inductive-v1",
        "version": "1.0.0"
    },
    "eve": {
        "llm": "llama-3-70b",
        "config": "counterfactual-v1",
        "version": "1.0.0"
    },
    "hal": {
        "llm": "llama-3-13b",
        "config": "monitoring-v1",
        "version": "1.0.0"
    },
    "quark": {
        "llm": "llama-3-13b",
        "config": "rule-based-v1",
        "version": "1.0.0"
    },
    "og": {
        "llm": "llama-3-70b",
        "config": "pattern-detection-v1",
        "version": "1.0.0"
    },
    "glyph": {
        "llm": "stable-diffusion-xl",
        "config": "creative-synthesis-v1",
        "version": "1.0.0"
    }
}

# Version History - Track changes for rollback
VERSION_HISTORY = {
    "max": [
        {"version": "1.0.0", "config": "governance-v1", "llm": "llama-3-13b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "neo": [
        {"version": "1.0.0", "config": "deductive-v1", "llm": "codellama-70b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "nat": [
        {"version": "1.0.0", "config": "abductive-v1", "llm": "mixtral-8x7b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "joi": [
        {"version": "1.0.0", "config": "empathetic-v1", "llm": "llama-3-13b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "data": [
        {"version": "1.0.0", "config": "inductive-v1", "llm": "mixtral-8x7b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "eve": [
        {"version": "1.0.0", "config": "counterfactual-v1", "llm": "llama-3-70b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "hal": [
        {"version": "1.0.0", "config": "monitoring-v1", "llm": "llama-3-13b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "quark": [
        {"version": "1.0.0", "config": "rule-based-v1", "llm": "llama-3-13b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "og": [
        {"version": "1.0.0", "config": "pattern-detection-v1", "llm": "llama-3-70b", "date": "2024-09-20", "notes": "Initial deployment"}
    ],
    "glyph": [
        {"version": "1.0.0", "config": "creative-synthesis-v1", "llm": "stable-diffusion-xl", "date": "2024-09-20", "notes": "Initial deployment"}
    ]
}

def get_agent_version(agent_name: str) -> str:
    """Get current version for an agent"""
    return AGENT_VERSIONS.get(agent_name.lower(), "1.0.0")

def get_agent_config(agent_name: str) -> dict:
    """Get current configuration for an agent"""
    return CONFIG_VERSIONS.get(agent_name.lower(), {
        "llm": "unknown",
        "config": "unknown", 
        "version": "1.0.0"
    })

def update_agent_version(agent_name: str, new_version: str, llm: str = None, config: str = None, notes: str = ""):
    """Update agent version and track in history"""
    from datetime import datetime
    
    agent_key = agent_name.lower()
    
    # Update current version
    AGENT_VERSIONS[agent_key] = new_version
    
    # Update config if provided
    if llm or config:
        current_config = CONFIG_VERSIONS.get(agent_key, {})
        if llm:
            current_config["llm"] = llm
        if config:
            current_config["config"] = config
        current_config["version"] = new_version
        CONFIG_VERSIONS[agent_key] = current_config
    
    # Add to version history
    if agent_key not in VERSION_HISTORY:
        VERSION_HISTORY[agent_key] = []
    
    VERSION_HISTORY[agent_key].append({
        "version": new_version,
        "config": config or current_config.get("config", "unknown"),
        "llm": llm or current_config.get("llm", "unknown"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes": notes
    })

def get_version_history(agent_name: str) -> list:
    """Get version history for an agent"""
    return VERSION_HISTORY.get(agent_name.lower(), [])

def rollback_agent(agent_name: str, target_version: str) -> bool:
    """Rollback agent to a previous version"""
    agent_key = agent_name.lower()
    history = VERSION_HISTORY.get(agent_key, [])
    
    # Find the target version in history
    for entry in reversed(history):
        if entry["version"] == target_version:
            # Update current version and config
            AGENT_VERSIONS[agent_key] = target_version
            CONFIG_VERSIONS[agent_key] = {
                "llm": entry["llm"],
                "config": entry["config"],
                "version": target_version
            }
            return True
    
    return False

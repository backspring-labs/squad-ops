# {{ROLE_NAME.title()}} Role Configuration
# {{DISPLAY_NAME}} Role

ROLE_TYPE = "{{ROLE_NAME}}"
AGENT_TYPE = "{{AGENT_TYPE}}"
REASONING_STYLE = "{{REASONING_STYLE}}"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama3-8b"
CURRENT_CONFIG = "{{AGENT_TYPE}}-v1"

# Agent Capabilities
CAPABILITIES = {{CAPABILITIES}}

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama3-8b",
        "config": "{{AGENT_TYPE}}-v1",
        "date": "2024-10-03",
        "notes": "Initial deployment with basic {{AGENT_TYPE}} capabilities"
    }
]

# Task Processing Configuration
TASK_TYPES = {{TASK_TYPES}}

# Performance Metrics
METRICS = {
    "processing_time": "avg_seconds",
    "task_success_rate": "percentage",
    "quality_score": "rating",
    "efficiency_score": "score"
}

# Role-specific Configuration
ROLE_CONFIG = {
    "reasoning_style": "{{REASONING_STYLE}}",
    "memory_type": "task_state_log",
    "processing_model": "{{AGENT_TYPE}}",
    "specialization": "{{AGENT_TYPE}}_tasks"
}

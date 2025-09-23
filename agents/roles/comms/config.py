# Joi Agent Configuration
# Communications Agent

AGENT_NAME = "Joi"
AGENT_TYPE = "communications"
REASONING_STYLE = "empathetic"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama-3-13b"
CURRENT_CONFIG = "empathetic-v1"

# Agent Capabilities
CAPABILITIES = ['team_communication', 'stakeholder_management', 'documentation', 'meeting_coordination', 'status_reporting']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama-3-13b",
        "config": "empathetic-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with empathetic reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['communication_draft', 'stakeholder_update', 'documentation', 'meeting_notes', 'status_report']

# Performance Metrics
METRICS = {'communication_clarity': 'score', 'stakeholder_satisfaction': 'percentage', 'documentation_quality': 'score', 'meeting_efficiency': 'score'}

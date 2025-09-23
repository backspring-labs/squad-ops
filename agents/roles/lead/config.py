# Max Agent Configuration
# Task Lead & Governance Agent

AGENT_NAME = "Max"
AGENT_TYPE = "governance"
REASONING_STYLE = "governance"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama-3-13b"
CURRENT_CONFIG = "governance-v1"

# Agent Capabilities
CAPABILITIES = [
    "task_coordination",
    "approval_workflows", 
    "escalation_management",
    "squad_governance",
    "decision_making"
]

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama-3-13b",
        "config": "governance-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with basic governance capabilities"
    }
]

# Task Processing Configuration
TASK_TYPES = [
    "approval_request",
    "escalation",
    "governance_decision",
    "task_delegation",
    "squad_coordination"
]

# Performance Metrics
METRICS = {
    "approval_time": "avg_seconds",
    "escalation_rate": "percentage", 
    "decision_accuracy": "percentage",
    "squad_efficiency": "score"
}

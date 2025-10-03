# Data Role Configuration
# Data Role

ROLE_TYPE = "data"
AGENT_TYPE = "analytics"
REASONING_STYLE = "inductive"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "mixtral-8x7b"
CURRENT_CONFIG = "inductive-v1"

# Agent Capabilities
CAPABILITIES = ['data_analysis', 'metrics_tracking', 'insight_generation', 'reporting', 'trend_analysis']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "mixtral-8x7b",
        "config": "inductive-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with inductive reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['data_analysis', 'metrics_calculation', 'insight_generation', 'report_creation', 'trend_analysis']

# Performance Metrics
METRICS = {'analysis_accuracy': 'percentage', 'insight_value': 'score', 'report_clarity': 'score', 'prediction_accuracy': 'percentage'}

# Finance Role Configuration
# Finance Role

ROLE_TYPE = "finance"
AGENT_TYPE = "finance_ops"
REASONING_STYLE = "rule_based"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama-3-13b"
CURRENT_CONFIG = "rule-based-v1"

# Agent Capabilities
CAPABILITIES = ['financial_modeling', 'budget_management', 'cost_analysis', 'operational_efficiency', 'compliance_tracking']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama-3-13b",
        "config": "rule-based-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with rule_based reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['financial_model', 'budget_analysis', 'cost_calculation', 'efficiency_audit', 'compliance_check']

# Performance Metrics
METRICS = {'budget_accuracy': 'percentage', 'cost_efficiency': 'score', 'compliance_rate': 'percentage', 'operational_speed': 'score'}

# Audit Role Configuration
# Audit Role

ROLE_TYPE = "audit"
AGENT_TYPE = "monitoring"
REASONING_STYLE = "analytical"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama-3-13b"
CURRENT_CONFIG = "monitoring-v1"

# Agent Capabilities
CAPABILITIES = ['system_monitoring', 'performance_tracking', 'alert_management', 'health_checks', 'metrics_collection']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama-3-13b",
        "config": "monitoring-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with analytical reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['system_monitor', 'performance_analysis', 'alert_processing', 'health_check', 'metrics_collection']

# Performance Metrics
METRICS = {'monitoring_coverage': 'percentage', 'alert_accuracy': 'percentage', 'response_time': 'seconds', 'system_uptime': 'percentage'}

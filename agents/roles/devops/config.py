# {{ROLE_NAME.title()}} Role Configuration
# DevOps Engineer Role

ROLE_TYPE = "devops"
AGENT_TYPE = "devops"
REASONING_STYLE = "systematic"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama3-8b"
CURRENT_CONFIG = "devops-v1"

# Agent Capabilities
CAPABILITIES = [
    "infrastructure_automation",
    "deployment_pipeline",
    "monitoring_setup",
    "security_hardening",
    "performance_optimization"
]

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama3-8b",
        "config": "devops-v1",
        "date": "2024-10-03",
        "notes": "Initial deployment with basic devops capabilities"
    }
]

# Task Processing Configuration
TASK_TYPES = [
    "infrastructure_setup",
    "deployment_automation",
    "monitoring_configuration",
    "security_hardening",
    "performance_tuning"
]

# Performance Metrics
METRICS = {
    "processing_time": "avg_seconds",
    "task_success_rate": "percentage",
    "quality_score": "rating",
    "efficiency_score": "score"
}

# Role-specific Configuration
ROLE_CONFIG = {
    "reasoning_style": "systematic",
    "memory_type": "task_state_log",
    "processing_model": "devops",
    "specialization": "devops_tasks"
}

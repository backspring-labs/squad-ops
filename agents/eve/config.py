# EVE Agent Configuration
# Qa Security Agent

AGENT_NAME = "EVE"
AGENT_TYPE = "qa_security"
REASONING_STYLE = "counterfactual"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "llama-3-70b"
CURRENT_CONFIG = "counterfactual-v1"

# Agent Capabilities
CAPABILITIES = ['security_testing', 'quality_assurance', 'vulnerability_assessment', 'test_automation', 'compliance_checking']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "llama-3-70b",
        "config": "counterfactual-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with counterfactual reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['security_test', 'qa_testing', 'vulnerability_scan', 'test_automation', 'compliance_audit']

# Performance Metrics
METRICS = {'security_coverage': 'percentage', 'bug_detection_rate': 'percentage', 'test_efficiency': 'score', 'compliance_score': 'percentage'}

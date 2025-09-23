# Neo Agent Configuration
# Developer & Technical Implementation Agent

AGENT_NAME = "Neo"
AGENT_TYPE = "developer"
REASONING_STYLE = "deductive"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "codellama-70b"
CURRENT_CONFIG = "deductive-v1"

# Agent Capabilities
CAPABILITIES = [
    "code_generation",
    "code_review",
    "refactoring",
    "debugging",
    "technical_architecture"
]

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "codellama-70b",
        "config": "deductive-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with deductive reasoning for code tasks"
    }
]

# Task Processing Configuration
TASK_TYPES = [
    "code_generation",
    "code_review",
    "refactoring",
    "debugging",
    "architecture_design"
]

# Performance Metrics
METRICS = {
    "code_quality": "score",
    "bug_detection_rate": "percentage",
    "refactoring_success": "percentage",
    "development_speed": "lines_per_hour"
}

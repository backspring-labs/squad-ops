# Nat Agent Configuration
# Product Strategy Agent

AGENT_NAME = "Nat"
AGENT_TYPE = "product_strategy"
REASONING_STYLE = "abductive"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "mixtral-8x7b"
CURRENT_CONFIG = "abductive-v1"

# Agent Capabilities
CAPABILITIES = ['product_strategy', 'market_analysis', 'feature_prioritization', 'user_research', 'roadmap_planning']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "mixtral-8x7b",
        "config": "abductive-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with abductive reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['strategy_analysis', 'market_research', 'feature_planning', 'user_stories', 'roadmap_creation']

# Performance Metrics
METRICS = {'strategy_accuracy': 'percentage', 'market_insight_quality': 'score', 'feature_adoption': 'percentage', 'roadmap_efficiency': 'score'}

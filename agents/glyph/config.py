# Glyph Agent Configuration
# Creative Design Agent

AGENT_NAME = "Glyph"
AGENT_TYPE = "creative_design"
REASONING_STYLE = "creative_synthesis"

# Current Configuration
CURRENT_VERSION = "1.0.0"
CURRENT_LLM = "stable-diffusion-xl"
CURRENT_CONFIG = "creative-synthesis-v1"

# Agent Capabilities
CAPABILITIES = ['visual_asset_creation', 'creative_synthesis', 'design_review', 'visual_inspiration', 'brand_consistency']

# Configuration History
CONFIG_HISTORY = [
    {
        "version": "1.0.0",
        "llm": "stable-diffusion-xl",
        "config": "creative-synthesis-v1",
        "date": "2024-09-20",
        "notes": "Initial deployment with creative_synthesis reasoning"
    }
]

# Task Processing Configuration
TASK_TYPES = ['visual_asset_creation', 'creative_synthesis', 'design_review', 'visual_inspiration', 'brand_guidelines']

# Performance Metrics
METRICS = {'design_quality': 'score', 'creative_innovation': 'score', 'brand_consistency': 'percentage', 'visual_appeal': 'score'}

#!/usr/bin/env python3
"""Creative Agent - Creative Role"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CreativeAgent(BaseAgent):
    """Creative Agent - Creative Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="creative_designer",
            reasoning_style="iterative"
        )
        self.visual_assets = {}
        self.creative_queue = asyncio.Queue()
        self.inspiration_library = {}
        
        # Initialize schema validator
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
    
    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Handle agent request using capability-based routing"""
        started_at = datetime.utcnow()
        
        try:
            # Validate request
            is_valid, error_msg = self.validator.validate_request(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="VALIDATION_ERROR",
                    error_message=error_msg or "Request validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Validate constraints
            is_valid, error_msg = self._validate_constraints(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="POLICY_VIOLATION",
                    error_message=error_msg or "Constraint validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Generate idempotency key
            idempotency_key = request.generate_idempotency_key(self.name)
            
            # Route to capability handler
            action = request.action
            if action == "creative.visual_design":
                result = await self._handle_visual_design(request)
            elif action == "creative.ux_design":
                result = await self._handle_ux_design(request)
            else:
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Validate result keys
            is_valid, error_msg = self.validator.validate_result_keys(action, result)
            if not is_valid:
                logger.warning(f"{self.name}: Result validation warning: {error_msg}")
            
            # Create success response
            ended_at = datetime.utcnow()
            return AgentResponse.success(
                result=result,
                idempotency_key=idempotency_key,
                timing=Timing.create(started_at, ended_at)
            )
            
        except Exception as e:
            logger.error(f"{self.name}: Error handling request: {e}", exc_info=True)
            return AgentResponse.failure(
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                retryable=True,
                timing=Timing.create(started_at)
            )
    
    async def _handle_visual_design(self, request: AgentRequest) -> dict[str, Any]:
        """Handle creative.visual_design capability"""
        
        # Map existing visual design logic to new capability format
        return {
            'design_uri': f'/designs/{task_id}',
            'assets': [],
            'style_guide': {}
        }
    
    async def _handle_ux_design(self, request: AgentRequest) -> dict[str, Any]:
        """Handle creative.ux_design capability"""
        
        # Map existing UX design logic to new capability format
        return {
            'ux_design_uri': f'/ux-designs/{task_id}',
            'wireframes': [],
            'user_flows': []
        }
        
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process creative design tasks"""
        task_type = task.get('type', 'unknown')
        task_id = task.get('task_id', 'unknown')
        
        logger.info(f"Glyph processing {task_type} task: {task_id}")
        
        if task_type == 'visual_asset_creation':
            return await self.create_visual_asset(task)
        elif task_type == 'creative_synthesis':
            return await self.perform_creative_synthesis(task)
        elif task_type == 'visual_inspiration':
            return await self.provide_visual_inspiration(task)
        elif task_type == 'design_review':
            return await self.review_design(task)
        else:
            return await self.handle_generic_task(task)
    
    async def create_visual_asset(self, task: dict[str, Any]) -> dict[str, Any]:
        """Create visual assets using creative synthesis"""
        asset_type = task.get('asset_type', 'generic')
        specifications = task.get('specifications', {})
        
        # Mock visual asset creation (would use Stable Diffusion XL in real implementation)
        asset_id = f"asset_{task.get('task_id', 'unknown')}"
        
        result = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "status": "created",
            "specifications": specifications,
            "creative_notes": f"Created {asset_type} asset with iterative refinement approach",
            "visual_elements": {
                "color_palette": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"],
                "style": "modern_minimalist",
                "mood": "inspiring"
            },
            "iterations": 3,
            "final_version": "v3.0"
        }
        
        self.visual_assets[asset_id] = result
        logger.info(f"Glyph created visual asset: {asset_id}")
        
        return result
    
    async def perform_creative_synthesis(self, task: dict[str, Any]) -> dict[str, Any]:
        """Perform creative synthesis combining multiple elements"""
        elements = task.get('elements', [])
        synthesis_type = task.get('synthesis_type', 'blend')
        
        # Mock creative synthesis
        synthesis_id = f"synthesis_{task.get('task_id', 'unknown')}"
        
        result = {
            "synthesis_id": synthesis_id,
            "synthesis_type": synthesis_type,
            "input_elements": elements,
            "creative_process": "iterative_blending",
            "output": {
                "concept": "Unified creative vision",
                "visual_harmony": 0.95,
                "innovation_score": 0.87,
                "aesthetic_appeal": 0.92
            },
            "recommendations": [
                "Consider adding subtle gradients",
                "Balance warm and cool tones",
                "Maintain visual hierarchy"
            ]
        }
        
        logger.info(f"Glyph performed creative synthesis: {synthesis_id}")
        return result
    
    async def provide_visual_inspiration(self, task: dict[str, Any]) -> dict[str, Any]:
        """Provide visual inspiration and creative direction"""
        context = task.get('context', 'general')
        mood = task.get('mood', 'neutral')
        
        # Mock visual inspiration
        inspiration_id = f"inspiration_{task.get('task_id', 'unknown')}"
        
        result = {
            "inspiration_id": inspiration_id,
            "context": context,
            "mood": mood,
            "visual_direction": {
                "primary_colors": ["#E8F4FD", "#B8E6B8", "#FFEAA7"],
                "secondary_colors": ["#DDA0DD", "#98D8C8", "#F7DC6F"],
                "typography_style": "clean_modern",
                "layout_approach": "grid_based",
                "visual_metaphors": ["growth", "connection", "innovation"]
            },
            "creative_prompts": [
                "Think outside the box while maintaining usability",
                "Create visual stories that resonate emotionally",
                "Balance creativity with functional design"
            ],
            "reference_styles": [
                "Scandinavian minimalism",
                "Japanese wabi-sabi",
                "Swiss design principles"
            ]
        }
        
        self.inspiration_library[inspiration_id] = result
        logger.info(f"Glyph provided visual inspiration: {inspiration_id}")
        return result
    
    async def review_design(self, task: dict[str, Any]) -> dict[str, Any]:
        """Review and provide feedback on designs"""
        design_data = task.get('design_data', {})
        review_criteria = task.get('criteria', ['aesthetics', 'usability', 'brand_consistency'])
        
        # Mock design review
        review_id = f"review_{task.get('task_id', 'unknown')}"
        
        result = {
            "review_id": review_id,
            "design_data": design_data,
            "criteria": review_criteria,
            "scores": {
                "aesthetics": 0.88,
                "usability": 0.92,
                "brand_consistency": 0.85,
                "innovation": 0.79,
                "overall": 0.86
            },
            "feedback": {
                "strengths": [
                    "Strong visual hierarchy",
                    "Excellent color harmony",
                    "Clear user flow"
                ],
                "improvements": [
                    "Consider adding more visual interest",
                    "Enhance accessibility features",
                    "Strengthen brand personality"
                ]
            },
            "recommendations": [
                "Add subtle animations for engagement",
                "Consider responsive design patterns",
                "Implement design system consistency"
            ]
        }
        
        logger.info(f"Glyph completed design review: {review_id}")
        return result
    
    async def handle_generic_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Handle generic creative tasks"""
        task_description = task.get('description', 'No description provided')
        
        result = {
            "task_id": task.get('task_id', 'unknown'),
            "status": "completed",
            "creative_approach": "iterative_synthesis",
            "output": f"Creative solution for: {task_description}",
            "visual_elements": {
                "style": "adaptive",
                "mood": "inspiring",
                "approach": "human_centered"
            },
            "notes": "Applied creative thinking principles with iterative refinement"
        }
        
        logger.info(f"Glyph handled generic creative task: {task.get('task_id', 'unknown')}")
        return result
    
    async def handle_message(self, message):
        """Handle incoming messages with creative perspective"""
        if message.message_type == "creative_request":
            await self.creative_queue.put(message)
            logger.info(f"Glyph received creative request from {message.sender}")
        elif message.message_type == "design_feedback":
            logger.info(f"Glyph received design feedback from {message.sender}")
        else:
            logger.info(f"Glyph received message from {message.sender}: {message.content}")

async def main():
    """Main entry point for Creative agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = CreativeAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())

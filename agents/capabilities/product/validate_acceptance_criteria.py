#!/usr/bin/env python3
"""
Validate Acceptance Criteria Capability
Validates PRD acceptance criteria against deployed application.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ValidateAcceptanceCriteria:
    """
    Validate Acceptance Criteria - Product domain capability
    
    Validates PRD acceptance criteria against deployed application.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize ValidateAcceptanceCriteria with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def validate(self, prd_path: str, app_url: str = "http://localhost:8080/hello-squad/") -> Dict[str, Any]:
        """
        Validate PRD acceptance criteria against deployed application.
        
        Implements the product.validate_acceptance_criteria capability.
        
        Args:
            prd_path: Path to PRD file
            app_url: URL of deployed application (default: hello-squad)
            
        Returns:
            Dictionary containing:
            - criteria_met: List of criteria that match
            - criteria_unmet: List of criteria that don't match
            - criteria_partial: List of criteria partially met
            - validation_score: Float (0.0-1.0) percentage of criteria met
            - details: Dict with detailed comparison results
        """
        try:
            # Load PRD content
            prd_content = await self.agent.read_file(prd_path)
            logger.info(f"{self.name} loaded PRD from {prd_path}")
            
            # Use ParsePRDAcceptanceCriteria skill to extract criteria
            from agents.skills.product.parse_prd_acceptance_criteria import ParsePRDAcceptanceCriteria
            parser = ParsePRDAcceptanceCriteria()
            criteria_list = parser.extract(prd_content)
            
            if not criteria_list:
                logger.warning(f"{self.name} no acceptance criteria found in PRD")
                return {
                    'criteria_met': [],
                    'criteria_unmet': [],
                    'criteria_partial': [],
                    'validation_score': 0.0,
                    'details': {
                        'total_criteria': 0,
                        'testable_criteria': 0,
                        'message': 'No acceptance criteria found in PRD'
                    }
                }
            
            # Use CompareAppOutputToCriteria skill to fetch app HTML and compare
            from agents.skills.qa.compare_app_output_to_criteria import CompareAppOutputToCriteria
            comparer = CompareAppOutputToCriteria()
            comparison_results = await comparer.compare(app_url, criteria_list)
            
            criteria_met = comparison_results['criteria_met']
            criteria_unmet = comparison_results['criteria_unmet']
            criteria_partial = comparison_results['criteria_partial']
            
            # Calculate validation score
            total_testable = len(criteria_met) + len(criteria_unmet) + len(criteria_partial)
            if total_testable == 0:
                validation_score = 0.0
            else:
                # Full credit for met, half credit for partial
                met_score = len(criteria_met)
                partial_score = len(criteria_partial) * 0.5
                validation_score = (met_score + partial_score) / total_testable
            
            logger.info(f"{self.name} validation complete: score={validation_score:.2%}, met={len(criteria_met)}, unmet={len(criteria_unmet)}, partial={len(criteria_partial)}")
            
            # Record memory for validation results
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="prd_validation",
                    payload={
                        'prd_path': prd_path,
                        'app_url': app_url,
                        'validation_score': validation_score,
                        'criteria_met_count': len(criteria_met),
                        'criteria_unmet_count': len(criteria_unmet),
                        'criteria_partial_count': len(criteria_partial),
                        'total_criteria': len(criteria_list)
                    },
                    importance=0.7
                )
            
            return {
                'criteria_met': criteria_met,
                'criteria_unmet': criteria_unmet,
                'criteria_partial': criteria_partial,
                'validation_score': validation_score,
                'details': {
                    'total_criteria': len(criteria_list),
                    'testable_criteria': total_testable,
                    'non_testable_criteria': len(criteria_list) - total_testable,
                    'app_url': app_url,
                    'prd_path': prd_path
                }
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to validate acceptance criteria: {e}", exc_info=True)
            raise


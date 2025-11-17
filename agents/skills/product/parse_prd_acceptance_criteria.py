#!/usr/bin/env python3
"""
Parse PRD Acceptance Criteria Skill
Extracts acceptance criteria from PRD content.
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ParsePRDAcceptanceCriteria:
    """
    Parse PRD Acceptance Criteria - Product domain skill
    
    Parses PRD markdown to identify Success Criteria section.
    Deterministic skill (parsing logic only).
    """
    
    def extract(self, prd_content: str) -> List[Dict[str, Any]]:
        """
        Extract acceptance criteria from PRD markdown content.
        
        Args:
            prd_content: PRD markdown content
            
        Returns:
            Structured list with:
            - criterion_id: Unique identifier
            - description: Criterion text
            - type: 'functional', 'technical', 'design'
            - testable: Boolean indicating if it can be validated against deployed app
        """
        criteria = []
        
        # Find Success Criteria section
        # Look for "Success Criteria" or "### Success Criteria" or similar patterns
        success_criteria_pattern = r'(?:##\s*)?(?:###\s*)?Success\s+Criteria[:\s]*(.*?)(?=\n##|\Z)'
        match = re.search(success_criteria_pattern, prd_content, re.IGNORECASE | re.DOTALL)
        
        if not match:
            logger.warning("No Success Criteria section found in PRD")
            return criteria
        
        criteria_section = match.group(1)
        
        # Extract individual criteria (bullet points or numbered list)
        # Match lines starting with -, *, or numbers
        criterion_pattern = r'(?:^[\s]*[-*•]\s+|^\d+[\.\)]\s+)(.+?)(?=\n(?:[\s]*[-*•]\s+|^\d+[\.\)]\s+)|\n##|\Z)'
        criterion_matches = re.finditer(criterion_pattern, criteria_section, re.MULTILINE | re.DOTALL)
        
        for idx, criterion_match in enumerate(criterion_matches, 1):
            criterion_text = criterion_match.group(1).strip()
            
            if not criterion_text:
                continue
            
            # Determine type based on keywords
            criterion_lower = criterion_text.lower()
            if any(word in criterion_lower for word in ['load', 'performance', 'speed', 'response', 'scalability']):
                criterion_type = 'technical'
            elif any(word in criterion_lower for word in ['design', 'appearance', 'visual', 'layout', 'style']):
                criterion_type = 'design'
            else:
                criterion_type = 'functional'
            
            # Determine if testable (can be validated against deployed app)
            # Most criteria are testable unless explicitly marked as non-testable
            testable = True
            if any(word in criterion_lower for word in ['non-testable', 'not testable', 'subjective only']):
                testable = False
            
            criteria.append({
                'criterion_id': f'criteria_{idx:03d}',
                'description': criterion_text,
                'type': criterion_type,
                'testable': testable
            })
        
        # If no bullet points found, try to extract from paragraph format
        if not criteria:
            # Look for sentences that might be criteria
            sentences = re.split(r'[.!?]+', criteria_section)
            for idx, sentence in enumerate(sentences, 1):
                sentence = sentence.strip()
                if len(sentence) > 20 and not sentence.startswith('Note'):
                    criterion_lower = sentence.lower()
                    if any(word in criterion_lower for word in ['must', 'should', 'will', 'shall', 'requires']):
                        criterion_type = 'functional'
                        if any(word in criterion_lower for word in ['load', 'performance', 'speed']):
                            criterion_type = 'technical'
                        
                        criteria.append({
                            'criterion_id': f'criteria_{idx:03d}',
                            'description': sentence,
                            'type': criterion_type,
                            'testable': True
                        })
        
        logger.info(f"Extracted {len(criteria)} acceptance criteria from PRD")
        return criteria


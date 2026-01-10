#!/usr/bin/env python3
"""
Text Match Skill
Implements semantic text matching for criteria validation.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TextMatch:
    """
    Text Match - Shared skill for semantic text matching
    
    Provides text matching functionality for criteria validation.
    Can use simple keyword matching for MVP, LLM-based semantic matching later.
    """
    
    def match(self, text: str, pattern: str, threshold: float = 0.7) -> dict[str, Any]:
        """
        Match text against a pattern using semantic matching.
        
        Args:
            text: Text to search in
            pattern: Pattern to match against
            threshold: Minimum similarity score (0.0-1.0) to consider a match
            
        Returns:
            Dictionary containing:
            - match_score: Float (0.0 to 1.0 similarity score)
            - matched: Boolean (True if score > threshold)
        """
        # Simple keyword-based matching for MVP
        # TODO: Enhance with LLM-based semantic matching later
        
        text_lower = text.lower()
        pattern_lower = pattern.lower()
        
        # Split pattern into keywords
        pattern_keywords = [kw.strip() for kw in pattern_lower.split() if len(kw.strip()) > 2]
        
        if not pattern_keywords:
            # Empty pattern matches everything
            return {
                'match_score': 1.0,
                'matched': True
            }
        
        # Count how many keywords are found in text
        matches = sum(1 for keyword in pattern_keywords if keyword in text_lower)
        
        # Calculate match score as percentage of keywords found
        match_score = matches / len(pattern_keywords) if pattern_keywords else 0.0
        
        # Also check for exact phrase match (bonus)
        if pattern_lower in text_lower:
            match_score = min(1.0, match_score + 0.2)
        
        matched = match_score >= threshold
        
        return {
            'match_score': match_score,
            'matched': matched
        }


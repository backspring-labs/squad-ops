#!/usr/bin/env python3
"""
Compare App Output to Criteria Skill
Fetches deployed app HTML, parses content, and compares against acceptance criteria.
"""

import logging
import aiohttp
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import sys
import os

# Add parent directory to path to import shared skill
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
from agents.skills.shared.text_match import TextMatch

logger = logging.getLogger(__name__)


class CompareAppOutputToCriteria:
    """
    Compare App Output to Criteria - QA domain skill
    
    Fetches deployed app HTML, parses content, and compares against acceptance criteria.
    Not deterministic (requires HTTP fetch).
    """
    
    def __init__(self):
        """Initialize with text match skill"""
        self.text_match = TextMatch()
    
    async def compare(self, app_url: str, criteria_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fetch deployed app HTML and compare against acceptance criteria.
        
        Args:
            app_url: URL of deployed application
            criteria_list: List of criteria dictionaries with 'description', 'type', 'testable'
            
        Returns:
            Comparison results:
            - criteria_met: List of criteria that match
            - criteria_unmet: List of criteria that don't match
            - criteria_partial: List of criteria partially met
        """
        # Fetch app HTML
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(app_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch app: HTTP {response.status}")
                        return {
                            'criteria_met': [],
                            'criteria_unmet': criteria_list,
                            'criteria_partial': []
                        }
                    
                    html_content = await response.text()
        except Exception as e:
            logger.error(f"Error fetching app HTML: {e}")
            return {
                'criteria_met': [],
                'criteria_unmet': criteria_list,
                'criteria_partial': []
            }
        
        # Parse HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract text content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get all text content
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Extract specific elements
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        footer_text = ''
        footer = soup.find('footer')
        if footer:
            footer_text = footer.get_text(strip=True)
        
        # Extract version/build information (common patterns)
        version_info = []
        build_info = []
        status_indicators = []
        
        # Look for version patterns
        version_patterns = soup.find_all(string=re.compile(r'version|v\d+\.\d+', re.I))
        version_info.extend([v.strip() for v in version_patterns])
        
        # Look for build patterns
        build_patterns = soup.find_all(string=re.compile(r'build|warmboot|run-', re.I))
        build_info.extend([b.strip() for b in build_patterns])
        
        # Combine all text for matching
        all_text = ' '.join([
            text_content,
            ' '.join(headings),
            ' '.join(paragraphs),
            footer_text,
            ' '.join(version_info),
            ' '.join(build_info)
        ])
        
        # Compare each criterion
        criteria_met = []
        criteria_unmet = []
        criteria_partial = []
        
        for criterion in criteria_list:
            if not criterion.get('testable', True):
                # Skip non-testable criteria
                continue
            
            description = criterion.get('description', '')
            criterion_type = criterion.get('type', 'functional')
            
            # Use text match skill to compare
            match_result = self.text_match.match(all_text, description, threshold=0.7)
            
            if match_result['matched']:
                if match_result['match_score'] >= 0.9:
                    criteria_met.append(criterion)
                else:
                    criteria_partial.append({
                        **criterion,
                        'match_score': match_result['match_score']
                    })
            else:
                criteria_unmet.append({
                    **criterion,
                    'match_score': match_result['match_score']
                })
        
        logger.info(f"Comparison complete: {len(criteria_met)} met, {len(criteria_unmet)} unmet, {len(criteria_partial)} partial")
        
        return {
            'criteria_met': criteria_met,
            'criteria_unmet': criteria_unmet,
            'criteria_partial': criteria_partial
        }


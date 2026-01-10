"""
Output validation utilities for LLM responses.

Provides hard validation that fails fast if LLM output doesn't meet quality standards.
"""

import logging

logger = logging.getLogger(__name__)


def validate_html(html: str) -> str:
    """Validate HTML output - fail hard if quality issues detected"""
    html = html.strip()
    
    # Hard validation: markdown markers indicate prompt failure
    if '```' in html:
        raise ValueError(
            "HTML contains markdown code block markers. "
            "This indicates the LLM did not follow output format instructions. "
            "Prompt engineering or model capability issue."
        )
    
    # Structural validation
    if not html.startswith('<!DOCTYPE'):
        raise ValueError("HTML doesn't start with DOCTYPE declaration")
    
    # Path validation
    if '<base href=' in html:
        raise ValueError("HTML contains base href - should use relative paths")
    
    return html


def validate_css(css: str) -> str:
    """Validate CSS output - fail hard if quality issues detected"""
    css = css.strip()
    
    if '```' in css:
        raise ValueError(
            "CSS contains markdown code block markers. "
            "This indicates the LLM did not follow output format instructions."
        )
    
    return css


def validate_js(js: str) -> str:
    """Validate JavaScript output - fail hard if quality issues detected"""
    js = js.strip()
    
    if '```' in js:
        raise ValueError(
            "JavaScript contains markdown code block markers. "
            "This indicates the LLM did not follow output format instructions."
        )
    
    return js


def strip_markdown_markers(content: str) -> str:
    """Strip markdown code block markers from LLM response"""
    import re
    
    # Remove opening and closing fences
    patterns = [
        r'^```\w*\n?',  # Opening fence with optional language
        r'\n?```$',     # Closing fence
        r'^```\w*',     # Opening without newline
        r'```$'         # Closing without newline
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    return content.strip()

def clean_yaml_response(response: str) -> str:
    """Clean YAML response by stripping markdown markers"""
    if '```' in response:
        logger.info("LLM response contained markdown markers - stripping")
        return strip_markdown_markers(response)
    return response

def parse_delimited_files(content: str, delimiter: str = "--- FILE:") -> list[dict[str, str]]:
    """Parse delimited file format from LLM response"""
    files = []
    sections = content.split(delimiter)
    
    for section in sections[1:]:  # Skip first empty section
        lines = section.strip().split('\n', 1)
        if len(lines) < 2:
            continue
            
        file_path = lines[0].strip().rstrip('---').strip()
        file_content = lines[1].strip()
        
        files.append({
            'path': file_path,
            'content': file_content
        })
    
    return files

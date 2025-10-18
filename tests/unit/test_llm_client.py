"""
Unit tests for LLM client infrastructure.
"""

import pytest
import os

def test_llm_provider_configured():
    """Ensure at least one LLM provider is configured"""
    has_ollama = os.getenv('USE_LOCAL_LLM', 'false').lower() == 'true'
    has_openai = bool(os.getenv('OPENAI_API_KEY'))
    assert has_ollama or has_openai, "No LLM provider configured"

@pytest.mark.asyncio
async def test_ollama_client_integration():
    """Test Ollama client makes real API calls"""
    from agents.llm.providers.ollama import OllamaClient
    
    if os.getenv('USE_LOCAL_LLM', 'false').lower() != 'true':
        pytest.skip("Ollama not configured")
    
    client = OllamaClient()
    response = await client.complete("Say 'test' and nothing else.")
    assert response is not None
    assert len(response) > 0

def test_delimited_parsing():
    """Test delimited file format parsing"""
    from agents.llm.validators import parse_delimited_files
    
    response = """
--- FILE: index.html ---
<!DOCTYPE html>
<html></html>

--- FILE: styles.css ---
body { margin: 0; }
"""
    
    files = parse_delimited_files(response)
    assert len(files) == 2
    assert files[0]['path'] == 'index.html'
    assert files[1]['path'] == 'styles.css'

def test_html_validation():
    """Test HTML validation"""
    from agents.llm.validators import validate_html
    
    # Should clean markdown and validate
    html_with_markers = "```html\n<!DOCTYPE html>\n<html></html>\n```"
    with pytest.raises(ValueError, match="markdown code block markers"):
        validate_html(html_with_markers)
    
    # Should accept valid HTML
    valid_html = "<!DOCTYPE html>\n<html></html>"
    clean = validate_html(valid_html)
    assert clean.startswith('<!DOCTYPE')
    
    # Should reject invalid HTML
    bad_html = "<html>No DOCTYPE</html>"
    with pytest.raises(ValueError, match="DOCTYPE"):
        validate_html(bad_html)

def test_css_validation():
    """Test CSS validation"""
    from agents.llm.validators import validate_css
    
    # Should reject markdown markers
    css_with_markers = "```css\nbody { margin: 0; }\n```"
    with pytest.raises(ValueError, match="markdown code block markers"):
        validate_css(css_with_markers)
    
    # Should accept valid CSS
    valid_css = "body { margin: 0; }"
    clean = validate_css(valid_css)
    assert clean == valid_css

def test_js_validation():
    """Test JavaScript validation"""
    from agents.llm.validators import validate_js
    
    # Should reject markdown markers
    js_with_markers = "```js\nconsole.log('test');\n```"
    with pytest.raises(ValueError, match="markdown code block markers"):
        validate_js(js_with_markers)
    
    # Should accept valid JS
    valid_js = "console.log('test');"
    clean = validate_js(valid_js)
    assert clean == valid_js



"""
Unit tests for LLM client infrastructure.
"""

import pytest
import os
from unittest.mock import patch

def test_llm_provider_configured():
    """Ensure LLM router can provide a client"""
    from agents.llm.router import LLMRouter
    
    # Test that router can be created and provides a client
    router = LLMRouter.from_config('config/llm_config.yaml')
    client = router.get_default_client()
    
    # Client should be created successfully
    assert client is not None
    assert hasattr(client, 'complete')
    assert hasattr(client, 'chat')

@pytest.mark.asyncio
async def test_ollama_client_integration():
    """Test Ollama client functionality"""
    from agents.llm.providers.ollama import OllamaClient
    from unittest.mock import patch, AsyncMock
    
    # Create client with localhost URL
    client = OllamaClient(url='http://localhost:11434')
    
    # Mock the aiohttp session to avoid actual network calls
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = AsyncMock()
        mock_response.json.return_value = {'response': 'test response'}
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Test complete method
        response = await client.complete("Say 'test' and nothing else.")
        assert response is not None
        assert len(response) > 0
        
        # Test chat method
        chat_response = await client.chat("Hello", "test context")
        assert chat_response is not None

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

def test_llm_router_default_config():
    """Test LLM router with default config when file doesn't exist"""
    from agents.llm.router import LLMRouter
    from unittest.mock import patch
    
    # Mock file not existing
    with patch('builtins.open', side_effect=FileNotFoundError):
        router = LLMRouter.from_config('nonexistent.yaml')
        assert router.default_provider == 'ollama'
        assert 'ollama' in router.config['providers']

def test_llm_router_expand_env_vars_list():
    """Test environment variable expansion in lists"""
    from agents.llm.router import LLMRouter
    
    router = LLMRouter({'test': ['${HOME}', 'static_value']})
    expanded = router._expand_env_vars(['${HOME}', 'static_value'])
    assert len(expanded) == 2
    assert expanded[1] == 'static_value'
    # First item should be expanded to actual HOME value

def test_llm_router_expand_env_vars_no_default():
    """Test environment variable expansion without default value"""
    from agents.llm.router import LLMRouter
    
    router = LLMRouter({})
    # Test ${VAR} without default (should return empty string if not set)
    expanded = router._expand_env_vars('${NONEXISTENT_VAR}')
    assert expanded == ''

def test_llm_router_mock_client():
    """Test mock client creation when USE_LOCAL_LLM=false"""
    from agents.llm.router import LLMRouter
    
    with patch.dict('os.environ', {'USE_LOCAL_LLM': 'false'}):
        router = LLMRouter({'default_provider': 'ollama', 'providers': {}})
        client = router.get_default_client()
        
        # Should return a mock client
        assert hasattr(client, 'complete')
        assert hasattr(client, 'chat')
        
        # Test mock responses
        assert client.complete("test") == "[MOCK CODE RESPONSE] Test prompt for code generation"
        assert client.chat("test", "context") == "[MOCK CHAT RESPONSE] Test prompt"

def test_llm_router_unknown_provider():
    """Test error handling for unknown provider"""
    from agents.llm.router import LLMRouter
    
    router = LLMRouter({'default_provider': 'unknown_provider', 'providers': {}})
    
    with pytest.raises(ValueError, match="Unknown provider: unknown_provider"):
        router.get_default_client()

def test_html_validation_base_href():
    """Test HTML validation for base href"""
    from agents.llm.validators import validate_html
    
    html_with_base = """<!DOCTYPE html>
<html><head><base href='/absolute/'></head><body></body></html>"""
    with pytest.raises(ValueError, match="HTML contains base href"):
        validate_html(html_with_base)

def test_strip_markdown_markers():
    """Test markdown marker stripping functionality"""
    from agents.llm.validators import strip_markdown_markers
    
    # Test various markdown patterns
    content_with_fences = "```html\n<div>content</div>\n```"
    cleaned = strip_markdown_markers(content_with_fences)
    assert cleaned == "<div>content</div>"
    
    # Test without newlines
    content_no_newline = "```html<div>content</div>```"
    cleaned = strip_markdown_markers(content_no_newline)
    assert cleaned == "<div>content</div>"
    
    # Test multiple patterns
    content_mixed = "```\n<div>content</div>\n```"
    cleaned = strip_markdown_markers(content_mixed)
    assert cleaned == "<div>content</div>"

def test_clean_yaml_response():
    """Test YAML response cleaning"""
    from agents.llm.validators import clean_yaml_response
    
    # Test with markdown markers
    yaml_with_markers = "```yaml\nkey: value\n```"
    cleaned = clean_yaml_response(yaml_with_markers)
    assert cleaned == "key: value"
    
    # Test without markdown markers
    yaml_clean = "key: value"
    cleaned = clean_yaml_response(yaml_clean)
    assert cleaned == "key: value"

def test_parse_delimited_files_skip_invalid():
    """Test parsing delimited files with invalid sections"""
    from agents.llm.validators import parse_delimited_files
    
    content = """--- FILE: valid.txt
This is valid content
--- FILE: invalid
--- FILE: another.txt
More content"""
    
    files = parse_delimited_files(content)
    # Should skip the invalid section and only return 2 files
    assert len(files) == 2
    assert files[0]['path'] == 'valid.txt'
    assert files[1]['path'] == 'another.txt'




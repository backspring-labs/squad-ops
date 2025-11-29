"""
Unit tests for MemoryProvider interface
"""

import pytest
from agents.memory.base import MemoryProvider


class TestMemoryProvider:
    """Test MemoryProvider abstract interface"""
    
    def test_memory_provider_is_abstract(self):
        """Test that MemoryProvider cannot be instantiated directly"""
        with pytest.raises(TypeError):
            MemoryProvider()
    
    def test_memory_provider_interface_methods(self):
        """Test that MemoryProvider defines required methods"""
        assert hasattr(MemoryProvider, 'put')
        assert hasattr(MemoryProvider, 'get')
        assert hasattr(MemoryProvider, 'promote')
        
        # Check methods are abstract
        assert MemoryProvider.put.__isabstractmethod__
        assert MemoryProvider.get.__isabstractmethod__
        assert MemoryProvider.promote.__isabstractmethod__


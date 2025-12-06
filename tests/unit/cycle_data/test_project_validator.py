"""
Unit tests for project validator (SIP-0047)
"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from agents.cycle_data.project_validator import ProjectNotFoundError, validate_project_id


class TestProjectValidator:
    """Test project validation functionality"""
    
    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool"""
        pool = AsyncMock(spec=asyncpg.Pool)
        return pool
    
    @pytest.mark.asyncio
    async def test_validate_existing_project(self, mock_db_pool):
        """Test validation of existing project"""
        # Mock database connection
        mock_conn = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock query result - project exists
        mock_row = MagicMock()
        mock_row.__getitem__.return_value = "test_project"
        mock_conn.fetchrow.return_value = mock_row
        
        # Should not raise
        result = await validate_project_id("test_project", mock_db_pool)
        assert result is True
        
        # Verify query was called correctly
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT project_id FROM projects WHERE project_id = $1",
            "test_project"
        )
    
    @pytest.mark.asyncio
    async def test_validate_nonexistent_project(self, mock_db_pool):
        """Test validation of non-existent project"""
        # Mock database connection
        mock_conn = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock query result - project doesn't exist
        mock_conn.fetchrow.return_value = None
        
        # Should raise ProjectNotFoundError
        with pytest.raises(ProjectNotFoundError, match="Project 'missing_project' not found"):
            await validate_project_id("missing_project", mock_db_pool)
    
    @pytest.mark.asyncio
    async def test_validate_database_error(self, mock_db_pool):
        """Test handling of database errors"""
        # Mock database connection
        mock_conn = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock database error
        mock_conn.fetchrow.side_effect = Exception("Database connection failed")
        
        # Should raise ProjectNotFoundError with error message
        with pytest.raises(ProjectNotFoundError, match="Failed to validate project"):
            await validate_project_id("test_project", mock_db_pool)


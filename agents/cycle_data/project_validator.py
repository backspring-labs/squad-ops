#!/usr/bin/env python3
"""
Project Validator - Validates project_id against projects table (SIP-0047)
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a project_id is not found in the projects table."""
    pass


async def validate_project_id(project_id: str, db_pool: asyncpg.Pool) -> bool:
    """
    Validate that a project_id exists in the projects table.
    
    Args:
        project_id: Project identifier to validate
        db_pool: Database connection pool
        
    Returns:
        True if project exists
        
    Raises:
        ProjectNotFoundError: If project doesn't exist
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT project_id FROM projects WHERE project_id = $1",
                project_id
            )
            
            if row is None:
                raise ProjectNotFoundError(
                    f"Project '{project_id}' not found in projects table. "
                    "Projects must be registered before use."
                )
            
            logger.debug(f"Validated project_id: {project_id}")
            return True
            
    except ProjectNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error validating project_id {project_id}: {e}")
        raise ProjectNotFoundError(
            f"Failed to validate project '{project_id}': {str(e)}"
        ) from e


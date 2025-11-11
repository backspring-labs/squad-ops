#!/usr/bin/env python3
"""
File Manager Component for Dev Agent
Handles file system operations, file creation, and file management
"""

import logging
import asyncio
import os
from typing import Dict, Any, List
import sys

# Add config path
sys.path.append('/app')
from config.deployment_config import get_filesystem_config

logger = logging.getLogger(__name__)

class FileManager:
    """Handles file system operations and file management"""
    
    def __init__(self):
        self.file_cache = {}
        self.operation_history = []
    
    async def create_file(self, file_path: str, content: str, directory: str = None) -> Dict[str, Any]:
        """Create a file with specified content"""
        try:
            # Combine directory and file_path to get full path
            if directory:
                # Ensure directory exists
                await self._ensure_directory_exists(directory)
                # Join directory and filename (handle both absolute and relative paths)
                if os.path.isabs(file_path):
                    full_path = file_path
                else:
                    full_path = os.path.join(directory.rstrip('/'), os.path.basename(file_path))
            else:
                # No directory specified, use file_path as-is
                full_path = file_path
                await self._ensure_directory_exists(os.path.dirname(full_path) if os.path.dirname(full_path) else '.')
            
            # Write file content using full path
            await self._write_file(full_path, content)
            
            # Cache file info
            self.file_cache[full_path] = {
                'content': content,
                'created_at': asyncio.get_event_loop().time(),
                'size': len(content)
            }
            
            # Log operation
            self.operation_history.append({
                'operation': 'create_file',
                'file_path': full_path,
                'size': len(content),
                'timestamp': asyncio.get_event_loop().time()
            })
            
            logger.info(f"FileManager created file: {full_path} ({len(content)} bytes)")
            
            return {
                'status': 'success',
                'file_path': full_path,
                'size': len(content),
                'operation': 'created'
            }
            
        except Exception as e:
            logger.error(f"FileManager failed to create file {file_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'file_path': file_path
            }
    
    async def read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            # Check cache first
            if file_path in self.file_cache:
                return self.file_cache[file_path]['content']
            
            # Read from filesystem
            content = await self._read_file(file_path)
            
            # Cache content
            self.file_cache[file_path] = {
                'content': content,
                'read_at': asyncio.get_event_loop().time(),
                'size': len(content)
            }
            
            logger.debug(f"FileManager read file: {file_path} ({len(content)} bytes)")
            return content
            
        except Exception as e:
            logger.error(f"FileManager failed to read file {file_path}: {e}")
            raise
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"test -f '{file_path}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    async def directory_exists(self, dir_path: str) -> bool:
        """Check if a directory exists"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"test -d '{dir_path}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    async def create_directory(self, dir_path: str) -> Dict[str, Any]:
        """Create a directory"""
        try:
            await self._execute_command(f"mkdir -p '{dir_path}'")
            
            logger.info(f"FileManager created directory: {dir_path}")
            
            return {
                'status': 'success',
                'directory': dir_path,
                'operation': 'created'
            }
            
        except Exception as e:
            logger.error(f"FileManager failed to create directory {dir_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'directory': dir_path
            }
    
    async def list_files(self, dir_path: str, pattern: str = None) -> List[str]:
        """List files in a directory"""
        try:
            if pattern:
                command = f"find '{dir_path}' -name '{pattern}' -type f"
            else:
                command = f"find '{dir_path}' -type f"
            
            result = await self._execute_command(command)
            files = result.split('\\n') if result else []
            
            logger.debug(f"FileManager listed {len(files)} files in {dir_path}")
            return files
            
        except Exception as e:
            logger.error(f"FileManager failed to list files in {dir_path}: {e}")
            return []
    
    async def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Delete a file"""
        try:
            if await self.file_exists(file_path):
                await self._execute_command(f"rm -f '{file_path}'")
                
                # Remove from cache
                if file_path in self.file_cache:
                    del self.file_cache[file_path]
                
                logger.info(f"FileManager deleted file: {file_path}")
                
                return {
                    'status': 'success',
                    'file_path': file_path,
                    'operation': 'deleted'
                }
            else:
                return {
                    'status': 'not_found',
                    'file_path': file_path
                }
                
        except Exception as e:
            logger.error(f"FileManager failed to delete file {file_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'file_path': file_path
            }
    
    async def copy_file(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Copy a file"""
        try:
            # Ensure destination directory exists
            await self._ensure_directory_exists(os.path.dirname(dest_path))
            
            await self._execute_command(f"cp '{source_path}' '{dest_path}'")
            
            logger.info(f"FileManager copied file: {source_path} -> {dest_path}")
            
            return {
                'status': 'success',
                'source_path': source_path,
                'dest_path': dest_path,
                'operation': 'copied'
            }
            
        except Exception as e:
            logger.error(f"FileManager failed to copy file {source_path} to {dest_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'source_path': source_path,
                'dest_path': dest_path
            }
    
    async def move_file(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Move a file"""
        try:
            # Ensure destination directory exists
            await self._ensure_directory_exists(os.path.dirname(dest_path))
            
            await self._execute_command(f"mv '{source_path}' '{dest_path}'")
            
            # Update cache
            if source_path in self.file_cache:
                self.file_cache[dest_path] = self.file_cache[source_path]
                del self.file_cache[source_path]
            
            logger.info(f"FileManager moved file: {source_path} -> {dest_path}")
            
            return {
                'status': 'success',
                'source_path': source_path,
                'dest_path': dest_path,
                'operation': 'moved'
            }
            
        except Exception as e:
            logger.error(f"FileManager failed to move file {source_path} to {dest_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'source_path': source_path,
                'dest_path': dest_path
            }
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information"""
        try:
            if not await self.file_exists(file_path):
                return {
                    'status': 'not_found',
                    'file_path': file_path
                }
            
            # Get file stats
            result = await self._execute_command(f"stat -c '%s %Y %A' '{file_path}'")
            parts = result.split()
            
            if len(parts) >= 3:
                size = int(parts[0])
                modified_time = int(parts[1])
                permissions = parts[2]
                
                return {
                    'status': 'success',
                    'file_path': file_path,
                    'size': size,
                    'modified_time': modified_time,
                    'permissions': permissions
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Failed to parse file stats',
                    'file_path': file_path
                }
                
        except Exception as e:
            logger.error(f"FileManager failed to get file info for {file_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'file_path': file_path
            }
    
    async def validate_file_path(self, file_path: str) -> Dict[str, Any]:
        """Validate file path for security and compliance"""
        try:
            # Check for path traversal attempts
            if '..' in file_path or file_path.startswith('/'):
                return {
                    'status': 'invalid',
                    'error': 'Path traversal or absolute path not allowed',
                    'file_path': file_path
                }
            
            # Check file extension
            allowed_extensions = get_filesystem_config('allowed_extensions')
            file_ext = os.path.splitext(file_path)[1]
            
            if file_ext not in allowed_extensions:
                return {
                    'status': 'invalid',
                    'error': f'File extension {file_ext} not allowed',
                    'file_path': file_path,
                    'allowed_extensions': allowed_extensions
                }
            
            # Check file size (if file exists)
            if await self.file_exists(file_path):
                file_info = await self.get_file_info(file_path)
                max_size = get_filesystem_config('max_file_size')
                
                if file_info.get('size', 0) > max_size:
                    return {
                        'status': 'invalid',
                        'error': f'File size exceeds maximum allowed size',
                        'file_path': file_path,
                        'file_size': file_info.get('size'),
                        'max_size': max_size
                    }
            
            return {
                'status': 'valid',
                'file_path': file_path
            }
            
        except Exception as e:
            logger.error(f"FileManager failed to validate file path {file_path}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'file_path': file_path
            }
    
    async def cleanup_temp_files(self, temp_dir: str = None) -> Dict[str, Any]:
        """Clean up temporary files"""
        try:
            if not temp_dir:
                temp_dir = get_filesystem_config('warm_boot_dir') + '/temp'
            
            if await self.directory_exists(temp_dir):
                # Remove files older than 1 hour
                await self._execute_command(f"find '{temp_dir}' -type f -mmin +60 -delete")
                
                logger.info(f"FileManager cleaned up temp files in {temp_dir}")
                
                return {
                    'status': 'success',
                    'temp_dir': temp_dir,
                    'operation': 'cleaned'
                }
            else:
                return {
                    'status': 'no_temp_dir',
                    'temp_dir': temp_dir
                }
                
        except Exception as e:
            logger.error(f"FileManager failed to cleanup temp files: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'temp_dir': temp_dir
            }
    
    async def get_operation_history(self) -> Dict[str, Any]:
        """Get file operation history"""
        return {
            'status': 'success',
            'operations': self.operation_history,
            'total_operations': len(self.operation_history),
            'cached_files': len(self.file_cache)
        }
    
    async def _ensure_directory_exists(self, dir_path: str):
        """Ensure directory exists, create if it doesn't"""
        # Skip if directory path is empty
        if not dir_path or dir_path.strip() == '':
            logger.warning(f"FileManager skipping directory creation for empty path")
            return
        
        if not await self.directory_exists(dir_path):
            await self._execute_command(f"mkdir -p '{dir_path}'")
    
    async def _read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"cat '{file_path}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Failed to read file: {file_path}")
            
            return stdout.decode()
        except Exception as e:
            logger.error(f"FileManager failed to read file {file_path}: {e}")
            raise
    
    async def _write_file(self, file_path: str, content: str):
        """Write content to file"""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(file_path)
            await self._ensure_directory_exists(dir_path)
            
            # Write file
            process = await asyncio.create_subprocess_shell(
                f"cat > '{file_path}'",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=content.encode())
            
            if process.returncode != 0:
                raise Exception(f"Failed to write file: {file_path}")
                
        except Exception as e:
            logger.error(f"FileManager failed to write file {file_path}: {e}")
            raise
    
    async def _execute_command(self, command: str) -> str:
        """Execute a shell command and return output"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Command failed: {command}, Error: {stderr.decode()}")
            
            return stdout.decode().strip()
            
        except Exception as e:
            logger.error(f"FileManager command execution failed: {command}, Error: {e}")
            raise

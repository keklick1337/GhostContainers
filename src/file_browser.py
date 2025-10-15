"""
File Browser - file manager for containers
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileBrowser:
    """Container file manager"""
    
    def __init__(self, docker_manager):
        """
        Initialize file manager
        
        Args:
            docker_manager: DockerManager instance
        """
        self.docker_manager = docker_manager
    
    def list_files(
        self,
        container_name: str,
        path: str = '/',
        show_hidden: bool = False
    ) -> Optional[List[Dict[str, str]]]:
        """
        Get list of files in container directory
        
        Args:
            container_name: Container name
            path: Path in container
            show_hidden: Show hidden files
            
        Returns:
            List of files and directories or None
        """
        # Build ls command
        ls_flags = '-la' if show_hidden else '-l'
        command = f"ls {ls_flags} {path}"
        
        output = self.docker_manager.exec_command(container_name, command)
        
        if not output:
            return None
        
        # Parse ls output
        files = []
        lines = output.strip().split('\n')
        
        # Skip first line (total)
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split(maxsplit=8)
            if len(parts) < 9:
                continue
            
            permissions = parts[0]
            size = parts[4]
            name = parts[8]
            
            file_type = 'directory' if permissions.startswith('d') else 'file'
            if permissions.startswith('l'):
                file_type = 'symlink'
            
            files.append({
                'name': name,
                'type': file_type,
                'permissions': permissions,
                'size': size,
                'path': os.path.join(path, name)
            })
        
        return files
    
    def read_file(
        self,
        container_name: str,
        file_path: str,
        max_size: int = 1024 * 1024  # 1MB by default
    ) -> Optional[str]:
        """
        Read file content from container
        
        Args:
            container_name: Container name
            file_path: File path in container
            max_size: Maximum file size for reading
            
        Returns:
            File content or None
        """
        # Check file size
        size_cmd = f"stat -c %s {file_path} 2>/dev/null || stat -f %z {file_path}"
        size_output = self.docker_manager.exec_command(container_name, size_cmd)
        
        if size_output:
            try:
                file_size = int(size_output.strip())
                if file_size > max_size:
                    logger.warning(f"File {file_path} too large: {file_size} bytes")
                    return f"[File too large: {file_size} bytes]"
            except ValueError:
                pass
        
        # Reading file
        command = f"cat {file_path}"
        return self.docker_manager.exec_command(container_name, command)
    
    def write_file(
        self,
        container_name: str,
        file_path: str,
        content: str,
        user: Optional[str] = None
    ) -> bool:
        """
        Write content to file in container
        
        Args:
            container_name: Container name
            file_path: File path in container
            content: Content to write
            user: User (for access rights)
            
        Returns:
            True if successful
        """
        # Escape content for safe transfer
        escaped_content = content.replace("'", "'\\''")
        
        # Write via echo
        command = f"echo '{escaped_content}' > {file_path}"
        
        output = self.docker_manager.exec_command(
            container_name,
            command,
            user=user
        )
        
        # Check success
        check_cmd = f"test -f {file_path} && echo 'success' || echo 'failed'"
        check_output = self.docker_manager.exec_command(container_name, check_cmd)
        
        if check_output and 'success' in check_output:
            logger.info(f"File {file_path} written to {container_name}")
            return True
        else:
            logger.error(f"File write error {file_path}")
            return False
    
    def create_directory(
        self,
        container_name: str,
        dir_path: str,
        user: Optional[str] = None
    ) -> bool:
        """
        Create directory in container
        
        Args:
            container_name: Container name
            dir_path: Path to directory
            user: User
            
        Returns:
            True if successful
        """
        command = f"mkdir -p {dir_path}"
        
        output = self.docker_manager.exec_command(
            container_name,
            command,
            user=user
        )
        
        # Check success
        check_cmd = f"test -d {dir_path} && echo 'success' || echo 'failed'"
        check_output = self.docker_manager.exec_command(container_name, check_cmd)
        
        if check_output and 'success' in check_output:
            logger.info(f"Directory {dir_path} created in {container_name}")
            return True
        else:
            logger.error(f"Directory creation error {dir_path}")
            return False
    
    def delete_file(
        self,
        container_name: str,
        file_path: str,
        recursive: bool = False,
        user: Optional[str] = None
    ) -> bool:
        """
        Remove file or directory in container
        
        Args:
            container_name: Container name
            file_path: File/directory path
            recursive: Recursive deletion (for directories)
            user: User
            
        Returns:
            True if successful
        """
        rm_flag = '-rf' if recursive else '-f'
        command = f"rm {rm_flag} {file_path}"
        
        output = self.docker_manager.exec_command(
            container_name,
            command,
            user=user
        )
        
        # Check success
        check_cmd = f"test -e {file_path} && echo 'exists' || echo 'deleted'"
        check_output = self.docker_manager.exec_command(container_name, check_cmd)
        
        if check_output and 'deleted' in check_output:
            logger.info(f"File {file_path} removed from {container_name}")
            return True
        else:
            logger.error(f"Deletion error {file_path}")
            return False
    
    def change_permissions(
        self,
        container_name: str,
        file_path: str,
        permissions: str,
        recursive: bool = False,
        user: Optional[str] = 'root'
    ) -> bool:
        """
        Change file access permissions
        
        Args:
            container_name: Container name
            file_path: File path
            permissions: Permissions in chmod format (for example, '755')
            recursive: Recursively (for directories)
            user: User (usually needs root)
            
        Returns:
            True if successful
        """
        chmod_flag = '-R' if recursive else ''
        command = f"chmod {chmod_flag} {permissions} {file_path}"
        
        output = self.docker_manager.exec_command(
            container_name,
            command,
            user=user
        )
        
        # Check new permissions
        check_cmd = f"ls -ld {file_path}"
        check_output = self.docker_manager.exec_command(container_name, check_cmd)
        
        if check_output:
            logger.info(f"Permissions {file_path} changed to {permissions}")
            return True
        else:
            logger.error(f"Permission change error {file_path}")
            return False
    
    def change_owner(
        self,
        container_name: str,
        file_path: str,
        owner: str,
        recursive: bool = False
    ) -> bool:
        """
        Change file owner
        
        Args:
            container_name: Container name
            file_path: File path
            owner: Owner in format 'user:group' or 'user'
            recursive: Recursively
            
        Returns:
            True if successful
        """
        chown_flag = '-R' if recursive else ''
        command = f"chown {chown_flag} {owner} {file_path}"
        
        output = self.docker_manager.exec_command(
            container_name,
            command,
            user='root'
        )
        
        # Check new owner
        check_cmd = f"ls -ld {file_path}"
        check_output = self.docker_manager.exec_command(container_name, check_cmd)
        
        if check_output:
            logger.info(f"Owner {file_path} changed to {owner}")
            return True
        else:
            logger.error(f"Owner change error {file_path}")
            return False
    
    def search_files(
        self,
        container_name: str,
        pattern: str,
        search_path: str = '/',
        max_depth: Optional[int] = None
    ) -> Optional[List[str]]:
        """
        Search files by pattern
        
        Args:
            container_name: Container name
            pattern: Search pattern (for find -name)
            search_path: Search path
            max_depth: Maximum search depth
            
        Returns:
            List of found paths or None
        """
        depth_flag = f"-maxdepth {max_depth}" if max_depth else ""
        command = f"find {search_path} {depth_flag} -name '{pattern}' 2>/dev/null"
        
        output = self.docker_manager.exec_command(container_name, command)
        
        if not output:
            return None
        
        # Parse results
        files = [line.strip() for line in output.strip().split('\n') if line.strip()]
        return files
    
    def get_file_info(self, container_name: str, file_path: str) -> Optional[Dict[str, str]]:
        """
        Get detailed file information
        
        Args:
            container_name: Container name
            file_path: File path
            
        Returns:
            Dict with file information or None
        """
        command = f"stat {file_path}"
        output = self.docker_manager.exec_command(container_name, command)
        
        if not output:
            return None
        
        # Parse stat output
        info = {'path': file_path}
        
        for line in output.split('\n'):
            if 'Size:' in line:
                parts = line.split()
                if len(parts) >= 2:
                    info['size'] = parts[1]
            elif 'Access:' in line and 'Uid:' not in line:
                info['permissions'] = line.split('(')[1].split('/')[0] if '(' in line else ''
        
        return info

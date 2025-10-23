"""
Docker Container File Operations
Handles file copying between host and container using Docker API
"""

import logging
import os
from typing import Optional
from .docker_api.exceptions import ContainerNotFound

logger = logging.getLogger(__name__)


def copy_to_container(docker_manager, name: str, src_path: str, dst_path: str) -> bool:
    """
    Copy file or directory to container using Docker API
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        src_path: Path on host (file or directory)
        dst_path: Path in container (directory where to place the file/dir)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from .docker_api.tar_utils import create_tar_from_file, create_tar_from_directory
        
        # Check if source is file or directory
        if os.path.isfile(src_path):
            # Create tar from file
            tar_data = create_tar_from_file(src_path)
        elif os.path.isdir(src_path):
            # Create tar from directory
            tar_data = create_tar_from_directory(src_path)
        else:
            logger.error(f"Source path not found: {src_path}")
            return False
        
        # Get container and upload archive
        container = docker_manager.client.containers.get(name)
        container.put_archive(dst_path, tar_data)
        
        logger.info(f"Copied {src_path} to {name}:{dst_path}")
        return True
        
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to copy to container {name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def copy_from_container(docker_manager, name: str, src_path: str, dst_path: str) -> bool:
    """
    Copy file or directory from container using Docker API
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        src_path: Path in container (file or directory)
        dst_path: Path on host (directory where to extract)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from .docker_api.tar_utils import extract_tar_to_file
        
        # Get container and download archive
        container = docker_manager.client.containers.get(name)
        tar_data = container.get_archive(src_path)
        
        # Create output directory if it doesn't exist
        os.makedirs(dst_path, exist_ok=True)
        
        # Extract tar archive
        extract_tar_to_file(tar_data, dst_path)
        
        logger.info(f"Copied {name}:{src_path} to {dst_path}")
        return True
        
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to copy from container {name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

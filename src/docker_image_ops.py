"""
Docker Image Operations
Handles image operations: build, pull, push, remove, etc.
"""

import logging
import os
from typing import Dict, List, Optional, Any, Generator
from .docker_api.exceptions import ImageNotFound, APIError

logger = logging.getLogger(__name__)


def build_image(
    docker_manager,
    path: str,
    tag: str,
    dockerfile: str = "Dockerfile",
    buildargs: Optional[Dict[str, str]] = None,
    nocache: bool = False,
    rm: bool = True,
    pull: bool = False
) -> Optional[tuple]:
    """
    Build a Docker image
    
    Args:
        docker_manager: DockerManager instance
        path: Build context path
        tag: Image tag
        dockerfile: Dockerfile name
        buildargs: Build arguments
        nocache: Don't use cache
        rm: Remove intermediate containers
        pull: Always pull newer version of base image
        
    Returns:
        Tuple of (image, logs) or None on failure
    """
    try:
        logger.info(f"Building image {tag} from {path}")
        image, logs = docker_manager.client.images.build(
            path=path,
            tag=tag,
            dockerfile=dockerfile,
            buildargs=buildargs,
            nocache=nocache,
            rm=rm,
            pull=pull
        )
        logger.info(f"Image built successfully: {tag}")
        return image, logs
    except Exception as e:
        logger.error(f"Failed to build image {tag}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def pull_image(docker_manager, repository: str, tag: str = "latest") -> Optional[Any]:
    """
    Pull an image from registry
    
    Args:
        docker_manager: DockerManager instance
        repository: Image repository
        tag: Image tag
        
    Returns:
        Image object or None on failure
    """
    try:
        logger.info(f"Pulling image {repository}:{tag}")
        image = docker_manager.client.images.pull(repository, tag=tag)
        logger.info(f"Image pulled successfully: {repository}:{tag}")
        return image
    except Exception as e:
        logger.error(f"Failed to pull image {repository}:{tag}: {e}")
        return None


def push_image(docker_manager, repository: str, tag: str = "latest") -> bool:
    """
    Push an image to registry
    
    Args:
        docker_manager: DockerManager instance
        repository: Image repository
        tag: Image tag
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Pushing image {repository}:{tag}")
        docker_manager.client.images.push(repository, tag=tag)
        logger.info(f"Image pushed successfully: {repository}:{tag}")
        return True
    except Exception as e:
        logger.error(f"Failed to push image {repository}:{tag}: {e}")
        return False


def remove_image(docker_manager, image: str, force: bool = False, noprune: bool = False) -> bool:
    """
    Remove an image
    
    Args:
        docker_manager: DockerManager instance
        image: Image name or ID
        force: Force removal
        noprune: Don't delete untagged parents
        
    Returns:
        True if successful, False otherwise
    """
    try:
        docker_manager.client.images.remove(image, force=force, noprune=noprune)
        logger.info(f"Image removed: {image}")
        return True
    except ImageNotFound:
        logger.error(f"Image not found: {image}")
        return False
    except Exception as e:
        logger.error(f"Failed to remove image {image}: {e}")
        return False


def tag_image(docker_manager, image: str, repository: str, tag: str = "latest") -> bool:
    """
    Tag an image
    
    Args:
        docker_manager: DockerManager instance
        image: Image name or ID
        repository: Target repository
        tag: Target tag
        
    Returns:
        True if successful, False otherwise
    """
    try:
        img = docker_manager.client.images.get(image)
        img.tag(repository, tag=tag)
        logger.info(f"Image tagged: {image} -> {repository}:{tag}")
        return True
    except ImageNotFound:
        logger.error(f"Image not found: {image}")
        return False
    except Exception as e:
        logger.error(f"Failed to tag image {image}: {e}")
        return False


def list_images(docker_manager, name: Optional[str] = None, all: bool = False) -> List[Any]:
    """
    List images
    
    Args:
        docker_manager: DockerManager instance
        name: Filter by image name
        all: Show all images (including intermediate)
        
    Returns:
        List of image objects
    """
    try:
        return docker_manager.client.images.list(name=name, all=all)
    except Exception as e:
        logger.error(f"Failed to list images: {e}")
        return []


def get_image(docker_manager, name: str) -> Optional[Any]:
    """
    Get an image by name or ID
    
    Args:
        docker_manager: DockerManager instance
        name: Image name or ID
        
    Returns:
        Image object or None if not found
    """
    try:
        return docker_manager.client.images.get(name)
    except ImageNotFound:
        logger.error(f"Image not found: {name}")
        return None
    except Exception as e:
        logger.error(f"Failed to get image {name}: {e}")
        return None


def inspect_image(docker_manager, name: str) -> Optional[Dict]:
    """
    Get detailed image information
    
    Args:
        docker_manager: DockerManager instance
        name: Image name or ID
        
    Returns:
        Image info dict or None on failure
    """
    try:
        image = docker_manager.client.images.get(name)
        return image.attrs
    except ImageNotFound:
        logger.error(f"Image not found: {name}")
        return None
    except Exception as e:
        logger.error(f"Failed to inspect image {name}: {e}")
        return None


def prune_images(docker_manager, filters: Optional[Dict] = None) -> Optional[Dict]:
    """
    Remove unused images
    
    Args:
        docker_manager: DockerManager instance
        filters: Filters to apply
        
    Returns:
        Dict with pruning results or None on failure
    """
    try:
        result = docker_manager.client.images.prune(filters=filters)
        logger.info(f"Images pruned: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to prune images: {e}")
        return None


def export_image(docker_manager, image: str, output_path: str) -> bool:
    """
    Export image to tar archive
    
    Args:
        docker_manager: DockerManager instance
        image: Image name or ID
        output_path: Path to output tar file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        img = docker_manager.client.images.get(image)
        with open(output_path, 'wb') as f:
            for chunk in img.save():
                f.write(chunk)
        logger.info(f"Image exported: {image} -> {output_path}")
        return True
    except ImageNotFound:
        logger.error(f"Image not found: {image}")
        return False
    except Exception as e:
        logger.error(f"Failed to export image {image}: {e}")
        return False


def import_image(docker_manager, input_path: str, repository: Optional[str] = None, tag: str = "latest") -> Optional[Any]:
    """
    Import image from tar archive
    
    Args:
        docker_manager: DockerManager instance
        input_path: Path to input tar file
        repository: Target repository name
        tag: Target tag
        
    Returns:
        Image object or None on failure
    """
    try:
        with open(input_path, 'rb') as f:
            image = docker_manager.client.images.load(f.read())
        logger.info(f"Image imported: {input_path}")
        
        if repository and image:
            # Tag the imported image
            image[0].tag(repository, tag=tag)
            logger.info(f"Image tagged as: {repository}:{tag}")
            
        return image[0] if image else None
    except Exception as e:
        logger.error(f"Failed to import image from {input_path}: {e}")
        return None


def search_images(docker_manager, term: str, limit: int = 25) -> List[Dict]:
    """
    Search for images on Docker Hub
    
    Args:
        docker_manager: DockerManager instance
        term: Search term
        limit: Maximum number of results
        
    Returns:
        List of search results
    """
    try:
        results = docker_manager.client.images.search(term, limit=limit)
        return results
    except Exception as e:
        logger.error(f"Failed to search images: {e}")
        return []

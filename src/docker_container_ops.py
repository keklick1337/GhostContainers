"""
Docker Container Operations
Handles container lifecycle operations: create, start, stop, remove, etc.
"""

import logging
from typing import Dict, List, Optional, Any
from .docker_api.exceptions import ContainerNotFound, APIError

logger = logging.getLogger(__name__)


def create_container(
    docker_manager,
    name: str,
    image: str,
    command: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
    volumes: Optional[Dict[str, Dict[str, str]]] = None,
    ports: Optional[Dict[str, int]] = None,
    network: Optional[str] = None,
    detach: bool = True,
    **kwargs
) -> Optional[Any]:
    """
    Create a new container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        image: Image name
        command: Command to run
        environment: Environment variables
        volumes: Volume mounts
        ports: Port mappings
        network: Network name
        detach: Run in detached mode
        **kwargs: Additional container creation parameters
        
    Returns:
        Container object or None on failure
    """
    try:
        container = docker_manager.client.containers.create(
            image=image,
            name=name,
            command=command,
            environment=environment,
            volumes=volumes,
            ports=ports,
            network=network,
            detach=detach,
            **kwargs
        )
        logger.info(f"Container created: {name}")
        return container
    except Exception as e:
        logger.error(f"Failed to create container {name}: {e}")
        return None


def start_container(docker_manager, name: str) -> bool:
    """
    Start a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.start()
        logger.info(f"Container started: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to start container {name}: {e}")
        return False


def stop_container(docker_manager, name: str, timeout: int = 10) -> bool:
    """
    Stop a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.stop(timeout=timeout)
        logger.info(f"Container stopped: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to stop container {name}: {e}")
        return False


def remove_container(docker_manager, name: str, force: bool = False, v: bool = False) -> bool:
    """
    Remove a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        force: Force removal
        v: Remove associated volumes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.remove(force=force, v=v)
        logger.info(f"Container removed: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to remove container {name}: {e}")
        return False


def restart_container(docker_manager, name: str, timeout: int = 10) -> bool:
    """
    Restart a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.restart(timeout=timeout)
        logger.info(f"Container restarted: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to restart container {name}: {e}")
        return False


def pause_container(docker_manager, name: str) -> bool:
    """
    Pause a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.pause()
        logger.info(f"Container paused: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to pause container {name}: {e}")
        return False


def unpause_container(docker_manager, name: str) -> bool:
    """
    Unpause a container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        
    Returns:
        True if successful, False otherwise
    """
    try:
        container = docker_manager.client.containers.get(name)
        container.unpause()
        logger.info(f"Container unpaused: {name}")
        return True
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return False
    except Exception as e:
        logger.error(f"Failed to unpause container {name}: {e}")
        return False


def get_container_logs(docker_manager, name: str, tail: int = 100, follow: bool = False) -> Optional[str]:
    """
    Get container logs using custom Docker API
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        tail: Number of lines to return
        follow: Follow log output
        
    Returns:
        Logs as string or None on failure
    """
    try:
        container = docker_manager.client.containers.get(name)
        logs = container.logs(stdout=True, stderr=True, tail=str(tail), follow=follow)
        
        if isinstance(logs, bytes):
            return logs.decode('utf-8', errors='replace')
        return str(logs)
        
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return None
    except Exception as e:
        logger.error(f"Failed to get logs for container {name}: {e}")
        return None


def get_container_stats(docker_manager, name: str, stream: bool = False) -> Optional[Dict]:
    """
    Get container stats
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        stream: Stream stats continuously
        
    Returns:
        Stats dict or None on failure
    """
    try:
        container = docker_manager.client.containers.get(name)
        return container.stats(stream=stream)
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return None
    except Exception as e:
        logger.error(f"Failed to get stats for container {name}: {e}")
        return None


def exec_command(
    docker_manager,
    name: str,
    command: str,
    user: Optional[str] = None,
    workdir: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None
) -> Optional[tuple]:
    """
    Execute a command in a running container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        command: Command to execute
        user: User to run as
        workdir: Working directory
        environment: Environment variables
        
    Returns:
        Tuple of (exit_code, output) or None on failure
    """
    try:
        container = docker_manager.client.containers.get(name)
        result = container.exec_run(
            cmd=command,
            user=user,
            workdir=workdir,
            environment=environment
        )
        return result.exit_code, result.output.decode('utf-8', errors='replace')
    except ContainerNotFound:
        logger.error(f"Container not found: {name}")
        return None
    except Exception as e:
        logger.error(f"Failed to execute command in container {name}: {e}")
        return None


def list_containers(docker_manager, all: bool = False, filters: Optional[Dict] = None) -> List[Any]:
    """
    List containers
    
    Args:
        docker_manager: DockerManager instance
        all: Show all containers (including stopped)
        filters: Filter containers
        
    Returns:
        List of container objects
    """
    try:
        return docker_manager.client.containers.list(all=all, filters=filters)
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")
        return []

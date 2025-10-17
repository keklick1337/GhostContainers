"""
Docker Manager - module for managing Docker containers
Using custom Docker API without external dependencies
"""

from .docker_api import DockerClient
from .docker_api.exceptions import DockerException, ImageNotFound, ContainerNotFound, APIError
import logging
from typing import List, Dict, Optional, Any
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DockerManager:
    """Docker container management"""
    
    def __init__(self, database_manager=None):
        """
        Initialize Docker client
        
        Args:
            database_manager: Optional DatabaseManager instance for tracking containers
        """
        try:
            self.client = DockerClient()
            docker_info = self.client.info()
            self.db = database_manager
            logger.info(f"Docker connected: {docker_info.get('ServerVersion', 'Unknown')}")
        except Exception as e:
            logger.error(f"Docker connection error: {e}")
            raise
    
    def check_docker_version(self) -> Dict[str, str]:
        """
        Check Docker version
        
        Returns:
            Dict with client and server version
        """
        try:
            version = self.client.version()
            info = self.client.info()
            return {
                'client': version.get('Version', 'Unknown'),
                'server': info.get('ServerVersion', 'Unknown'),
                'api': version.get('ApiVersion', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Error getting Docker version: {e}")
            return {}
    
    def list_containers(self, all_containers: bool = True, show_all: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of containers
        
        Args:
            all_containers: Show all (including stopped)
            show_all: Show all Docker containers or only tracked by this app
            
        Returns:
            List of containers with information
        """
        try:
            containers = self.client.containers.list(all=all_containers)
            result = []
            
            for container in containers:
                # Get network information
                network_settings = container.attrs.get('NetworkSettings', {})
                networks = list(network_settings.get('Networks', {}).keys())
                
                # Get image tags
                image_obj = container.attrs.get('Config', {}).get('Image', '')
                image_name = image_obj if image_obj else container.image
                
                container_info = {
                    'id': container.short_id,
                    'full_id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'image': image_name,
                    'created': container.attrs.get('Created', ''),
                    'ports': container.ports,
                    'labels': container.labels,
                    'network': networks if networks else ['bridge'],
                    'tracked': False
                }
                
                # Check if tracked by this app (by ID or by name)
                if self.db:
                    tracked_by_id = self.db.is_tracked(container.id)
                    tracked_by_name = self.db.is_tracked_by_name(container.name)
                    container_info['tracked'] = tracked_by_id or tracked_by_name
                    
                    # Filter if show_all is False
                    if not show_all and not container_info['tracked']:
                        continue
                
                result.append(container_info)
            
            return result
        except Exception as e:
            logger.error(f"Error getting container list: {e}")
            return []
    
    def create_container(
        self,
        image: str,
        name: str,
        environment: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network_mode: Optional[str] = None,
        hostname: Optional[str] = None,
        remove: bool = False,
        detach: bool = True,
        template: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Create container
        
        Args:
            image: Docker image
            name: Container name
            environment: Environment variables
            volumes: Mounted volumes
            network_mode: Network mode
            hostname: Container hostname
            remove: Remove after stop (disposable)
            detach: Run in background
            template: Template name (for tracking)
            **kwargs: Additional parameters
            
        Returns:
            ID of created container or None
        """
        try:
            # Check if image exists, pull/rebuild if not
            image_exists = False
            try:
                self.client.images.get(image)
                image_exists = True
                logger.info(f"Image {image} found")
            except ImageNotFound:
                logger.warning(f"Image {image} not found locally")
                
                # Try to pull from registry if it's not a custom image
                if not image.startswith('ghostcontainers-'):
                    try:
                        logger.info(f"Attempting to pull {image} from registry...")
                        repo = image.split(':')[0]
                        tag_name = image.split(':')[1] if ':' in image else 'latest'
                        self.client.images.pull(repo, tag=tag_name)
                        image_exists = True
                        logger.info(f"Successfully pulled {image}")
                    except Exception as pull_error:
                        logger.error(f"Failed to pull {image}: {pull_error}")
                        # For ghostcontainers images, we'll need to rebuild them
                        # For now, just log and continue - the create will fail with a clear error
                
                # If still not found, the create will fail with appropriate error
                if not image_exists:
                    logger.error(f"Image {image} not available. Need to build or pull it first.")
            
            # Create container
            container = self.client.containers.create(
                image=image,
                name=name,
                environment=environment,
                volumes=volumes,
                network_mode=network_mode,
                hostname=hostname,
                detach=detach,
                stdin_open=True,
                tty=True,
                auto_remove=remove,
                **kwargs
            )
            
            logger.info(f"Container {name} created: {container.short_id}")
            
            # Add to database if available
            if self.db:
                self.db.add_container(
                    container_id=container.id,
                    name=name,
                    template=template,
                    disposable=remove
                )
                
                # Track shared folders
                if volumes:
                    for host_path, mount_info in volumes.items():
                        container_path = mount_info.get('bind', '')
                        if container_path:
                            self.db.add_shared_folder(
                                container_id=container.id,
                                host_path=host_path,
                                container_path=container_path
                            )
            
            return container.id
            
        except APIError as e:
            logger.error(f"Error creating container {name}: {e}")
            return None
    
    def start_container(self, name: str) -> bool:
        """
        Start container
        
        Args:
            name: Container name
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            container.start()
            
            # Update last_started in database
            if self.db:
                self.db.update_last_started(container.id)
            
            logger.info(f"Container {name} started")
            return True
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error starting container {name}: {e}")
            return False
    
    def stop_container(self, name: str, timeout: int = 10) -> bool:
        """
        Stop container
        
        Args:
            name: Container name
            timeout: Timeout for stop operation
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            container.stop(timeout=timeout)
            logger.info(f"Container {name} stopped")
            return True
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error stopping container {name}: {e}")
            return False
    
    def restart_container(self, name: str, timeout: int = 10) -> bool:
        """
        Restart container
        
        Args:
            name: Container name
            timeout: Timeout for restart operation
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            container.restart(timeout=timeout)
            logger.info(f"Container {name} restarted")
            return True
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error restarting container {name}: {e}")
            return False
    
    def remove_container(self, name: str, force: bool = False) -> bool:
        """
        Remove container
        
        Args:
            name: Container name
            force: Force removal (even if running)
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            container_id = container.id
            container.remove(force=force)
            
            # Remove from database
            if self.db:
                self.db.remove_container(container_id)
            
            logger.info(f"Container {name} removed")
            return True
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error removing container {name}: {e}")
            return False
    
    def exec_command(
        self,
        name: str,
        command: str,
        user: Optional[str] = None,
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Execute command in container
        
        Args:
            name: Container name
            command: Command to execute
            user: User (default root)
            workdir: Working directory
            environment: Environment variables
            
        Returns:
            Command output or None
        """
        try:
            container = self.client.containers.get(name)
            result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                user=user or '',
                workdir=workdir or '',
                environment=environment
            )
            
            # Parse result - our API returns raw response
            # Need to read and decode
            if result:
                return str(result)
            return None
            
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return None
        except APIError as e:
            logger.error(f"Command execution error in {name}: {e}")
            return None
    
    def run_gui_app(
        self,
        name: str,
        app: str,
        user: Optional[str] = None,
        background: bool = True
    ) -> bool:
        """
        Run GUI application in container
        
        Args:
            name: Container name
            app: Application command
            user: User to run as (default: container's default user)
            background: Run in background (default: True)
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            
            # Get DISPLAY from environment
            display = os.environ.get('DISPLAY', ':0')
            
            # Prepare environment variables
            env_vars = {
                'DISPLAY': display,
                'XAUTHORITY': '/tmp/.Xauthority'
            }
            
            # Fix Firefox popup black screen issue
            if 'firefox' in app.lower() or 'mozilla' in app.lower():
                env_vars['MOZ_X11_EGL'] = '0'
                env_vars['MOZ_DISABLE_CONTENT_SANDBOX'] = '1'
                env_vars['LIBGL_ALWAYS_SOFTWARE'] = '1'
                env_vars['MOZ_ACCELERATED'] = '0'
            
            logger.info(f"Running GUI app '{app}' in container {name} with DISPLAY={display}")
            
            result = container.exec_run(
                cmd=app,
                stdout=True,
                stderr=True,
                user=user or '',
                detach=background,
                environment=env_vars
            )
            
            return True
            
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except Exception as e:
            logger.error(f"Error running GUI app in {name}: {e}")
            return False
    
    def execute_command(self, name: str, command: str, user: Optional[str] = None) -> Optional[str]:
        """
        Alias for exec_command for compatibility
        """
        return self.exec_command(name, command, user=user)
    
    def get_container_status(self, name: str) -> Optional[str]:
        """
        Get container status
        
        Args:
            name: Container name
            
        Returns:
            Status or None
        """
        try:
            container = self.client.containers.get(name)
            return container.status
        except ContainerNotFound:
            return None
        except APIError as e:
            logger.error(f"Error getting status {name}: {e}")
            return None
    
    def get_container_logs(self, name: str, tail: int = 100) -> Optional[str]:
        """
        Get container logs (not implemented in custom API yet)
        Using docker CLI for now
        """
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'logs', '--tail', str(tail), name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout + result.stderr
            return None
        except Exception as e:
            logger.error(f"Error getting logs {name}: {e}")
            return None
    
    def copy_to_container(self, name: str, src_path: str, dst_path: str) -> bool:
        """
        Copy file to container (using docker CLI)
        """
        try:
            cmd = f"docker cp {src_path} {name}:{dst_path}"
            result = os.system(cmd)
            
            if result == 0:
                logger.info(f"File {src_path} copied to {name}:{dst_path}")
                return True
            else:
                logger.error(f"Error copying file to container")
                return False
                
        except Exception as e:
            logger.error(f"Copy error: {e}")
            return False
    
    def copy_from_container(self, name: str, src_path: str, dst_path: str) -> bool:
        """
        Copy file from container (using docker CLI)
        """
        try:
            cmd = f"docker cp {name}:{src_path} {dst_path}"
            result = os.system(cmd)
            
            if result == 0:
                logger.info(f"File {name}:{src_path} copied to {dst_path}")
                return True
            else:
                logger.error(f"Copy error from container")
                return False
                
        except Exception as e:
            logger.error(f"Copy error: {e}")
            return False
    
    def build_image(self, path: str, tag: str, callback=None, **kwargs) -> bool:
        """
        Build image from Dockerfile
        
        Args:
            path: Path to directory with Dockerfile
            tag: Image tag
            callback: Optional callback function for log messages
            **kwargs: Additional build parameters
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Building image {tag} from {path}...")
            
            # Extract build args
            buildargs = kwargs.get('buildargs')
            platform = kwargs.get('platform')
            
            # Build image using our API
            image = self.client.images.build(
                path=path,
                tag=tag,
                buildargs=buildargs,
                platform=platform,
                callback=callback
            )
            
            logger.info(f"Image {tag} built successfully")
            return True
            
        except Exception as e:
            logger.error(f"Image build error {tag}: {e}")
            if callback:
                callback(f"ERROR: {str(e)}")
            return False

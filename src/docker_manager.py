"""
Docker Manager - module for managing Docker containers
"""

import docker
from docker.errors import DockerException, NotFound, APIError
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
            self.client = docker.from_env()
            self.docker_info = self.client.info()
            self.db = database_manager
            logger.info(f"Docker connected: {self.docker_info.get('ServerVersion', 'Unknown')}")
        except DockerException as e:
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
            return {
                'client': version.get('Version', 'Unknown'),
                'server': self.docker_info.get('ServerVersion', 'Unknown'),
                'api': version.get('ApiVersion', 'Unknown')
            }
        except DockerException as e:
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
                
                container_info = {
                    'id': container.id[:12],
                    'full_id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
                    'created': container.attrs['Created'],
                    'ports': container.ports,
                    'labels': container.labels,
                    'network': networks if networks else ['bridge'],
                    'tracked': False
                }
                
                # Check if tracked by this app
                if self.db:
                    container_info['tracked'] = self.db.is_tracked(container.id)
                    
                    # Filter if show_all is False
                    if not show_all and not container_info['tracked']:
                        continue
                
                result.append(container_info)
            
            return result
        except DockerException as e:
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
            # Check if image exists
            try:
                self.client.images.get(image)
            except NotFound:
                logger.info(f"Image {image} not found, pulling...")
                self.client.images.pull(image)
            
            # Create container
            container = self.client.containers.create(
                image=image,
                name=name,
                environment=environment or {},
                volumes=volumes or {},
                network_mode=network_mode,
                hostname=hostname or name,
                detach=detach,
                stdin_open=True,
                tty=True,
                auto_remove=remove,
                **kwargs
            )
            
            logger.info(f"Container {name} created: {container.id[:12]}")
            
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
        except NotFound:
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
        except NotFound:
            logger.error(f"Container {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error stopping container {name}: {e}")
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
        except NotFound:
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
            
            exec_config = {
                'cmd': command,
                'stdout': True,
                'stderr': True,
                'stdin': False,
                'tty': False
            }
            
            if user:
                exec_config['user'] = user
            if workdir:
                exec_config['workdir'] = workdir
            if environment:
                exec_config['environment'] = environment
            
            result = container.exec_run(**exec_config)
            
            return result.output.decode('utf-8')
            
        except NotFound:
            logger.error(f"Container {name} not found")
            return None
        except APIError as e:
            logger.error(f"Command execution error in {name}: {e}")
            return None
    
    def exec_interactive(
        self,
        name: str,
        command: str = "/bin/bash",
        user: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Open interactive session in container
        
        Args:
            name: Container name
            command: Command (default /bin/bash)
            user: User
            environment: Environment variables
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            
            # Build docker exec command for interactive mode
            user_flag = f"-u {user}" if user else ""
            env_flags = " ".join([f"-e {k}={v}" for k, v in (environment or {}).items()])
            
            exec_cmd = f"docker exec -it {env_flags} {user_flag} {name} {command}"
            
            logger.info(f"Starting interactive session: {exec_cmd}")
            
            # Using os.system for interactive mode
            os.system(exec_cmd)
            
            return True
            
        except NotFound:
            logger.error(f"Container {name} not found")
            return False
        except Exception as e:
            logger.error(f"Error opening interactive session in {name}: {e}")
            return False
    
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
            # Add environment variables to disable hardware acceleration
            if 'firefox' in app.lower() or 'mozilla' in app.lower():
                env_vars['MOZ_X11_EGL'] = '0'
                env_vars['MOZ_DISABLE_CONTENT_SANDBOX'] = '1'
                env_vars['LIBGL_ALWAYS_SOFTWARE'] = '1'
                env_vars['MOZ_ACCELERATED'] = '0'
            
            exec_config = {
                'cmd': app,
                'stdout': True,
                'stderr': True,
                'stdin': False,
                'tty': False,
                'detach': background,
                'environment': env_vars
            }
            
            if user:
                exec_config['user'] = user
            
            logger.info(f"Running GUI app '{app}' in container {name} with DISPLAY={display}")
            result = container.exec_run(**exec_config)
            
            if not background and result.exit_code != 0:
                logger.error(f"GUI app failed: {result.output.decode('utf-8')}")
                return False
            
            return True
            
        except NotFound:
            logger.error(f"Container {name} not found")
            return False
        except Exception as e:
            logger.error(f"Error running GUI app in {name}: {e}")
            return False
    
    def execute_command(self, name: str, command: str, user: Optional[str] = None) -> Optional[str]:
        """
        Alias for exec_command for compatibility
        
        Args:
            name: Container name
            command: Command to execute
            user: User to run as
            
        Returns:
            Command output or None
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
        except NotFound:
            return None
        except APIError as e:
            logger.error(f"Error getting status {name}: {e}")
            return None
    
    def get_container_logs(self, name: str, tail: int = 100) -> Optional[str]:
        """
        Get container logs
        
        Args:
            name: Container name
            tail: Number of last lines
            
        Returns:
            Logs or None
        """
        try:
            container = self.client.containers.get(name)
            logs = container.logs(tail=tail).decode('utf-8')
            return logs
        except NotFound:
            logger.error(f"Container {name} not found")
            return None
        except APIError as e:
            logger.error(f"Error getting logs {name}: {e}")
            return None
    
    def copy_to_container(self, name: str, src_path: str, dst_path: str) -> bool:
        """
        Copy file to container
        
        Args:
            name: Container name
            src_path: File path on host
            dst_path: Path in container
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            
            # Using docker cp command
            cmd = f"docker cp {src_path} {name}:{dst_path}"
            result = os.system(cmd)
            
            if result == 0:
                logger.info(f"File {src_path} copied to {name}:{dst_path}")
                return True
            else:
                logger.error(f"Error copying file to container")
                return False
                
        except NotFound:
            logger.error(f"Container {name} not found")
            return False
        except Exception as e:
            logger.error(f"Copy error: {e}")
            return False
    
    def copy_from_container(self, name: str, src_path: str, dst_path: str) -> bool:
        """
        Copy file from container
        
        Args:
            name: Container name
            src_path: Path in container
            dst_path: Path on host
            
        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(name)
            
            # Using docker cp command
            cmd = f"docker cp {name}:{src_path} {dst_path}"
            result = os.system(cmd)
            
            if result == 0:
                logger.info(f"File {name}:{src_path} copied to {dst_path}")
                return True
            else:
                logger.error(f"Copy error file from container")
                return False
                
        except NotFound:
            logger.error(f"Container {name} not found")
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
            
            # Remove callback from kwargs if present (not a docker API parameter)
            kwargs.pop('callback', None)
            
            image, build_logs = self.client.images.build(
                path=path,
                tag=tag,
                rm=True,
                **kwargs
            )
            
            for log in build_logs:
                if 'stream' in log:
                    message = log['stream'].strip()
                    if message:
                        logger.info(message)
                        if callback:
                            callback(message)
            
            logger.info(f"Image {tag} built successfully")
            return True
            
        except APIError as e:
            logger.error(f"Image build error {tag}: {e}")
            if callback:
                callback(f"ERROR: {str(e)}")
            return False

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
                
                # Copy template apps to database
                template_apps = kwargs.get('template_apps', [])
                for app in template_apps:
                    self.db.add_container_app(
                        container_name=name,
                        app_name=app.get('name', ''),
                        app_command=app.get('command', '')
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
        launch_mode: Optional[str] = None
    ) -> bool:
        """
        Run GUI application in container
        
        Args:
            name: Container name
            app: Application command
            user: User to run as (default: container's default user)
            launch_mode: Launch mode - 'api', 'terminal', or 'custom'
            
        Returns:
            True if successful, or dict with container info for API mode
        """
        try:
            # Setup X11 permissions and verify display
            from .x11_helper import setup_xhost_permissions, verify_display_socket, check_xquartz_running
            
            # Check if XQuartz is running on macOS
            import platform
            system = platform.system()
            if system == "Darwin":
                if not check_xquartz_running():
                    logger.error("XQuartz is not running! Please start XQuartz first.")
                    return {'success': False, 'error': 'XQuartz is not running. Please start XQuartz and try again.'}
            
            # Verify DISPLAY socket
            display_ok, display_msg = verify_display_socket()
            if not display_ok:
                logger.error(f"Display verification failed: {display_msg}")
                return {'success': False, 'error': display_msg}
            
            logger.info(f"Display check: {display_msg}")
            
            # Setup xhost permissions
            if not setup_xhost_permissions():
                logger.warning("Failed to setup xhost permissions, continuing anyway...")
            
            # Get container to find its image and volumes
            container = self.client.containers.get(name)
            
            # Get DISPLAY from environment
            from .x11_helper import get_display
            display = get_display()
            
            # Prepare environment variables
            # On macOS, use host.docker.internal instead of socket path
            import platform
            system = platform.system()
            
            if system == "Darwin" and ':' in display:
                # Extract display number from socket path
                display_num = display.split(':')[-1]
                env_vars = {
                    'DISPLAY': f'host.docker.internal:{display_num}',
                    'XAUTHORITY': '/tmp/.Xauthority'
                }
            else:
                env_vars = {
                    'DISPLAY': display,
                    'XAUTHORITY': '/tmp/.Xauthority'
                }
            
            # Add container's existing environment
            container_env = container.attrs.get('Config', {}).get('Env', [])
            for env in container_env:
                if '=' in env:
                    key, value = env.split('=', 1)
                    if key not in env_vars:  # Don't override DISPLAY
                        env_vars[key] = value
            
            # Fix Firefox popup black screen issue
            if 'firefox' in app.lower() or 'mozilla' in app.lower():
                env_vars['MOZ_X11_EGL'] = '0'
                env_vars['MOZ_DISABLE_CONTENT_SANDBOX'] = '1'
                env_vars['LIBGL_ALWAYS_SOFTWARE'] = '1'
                env_vars['MOZ_ACCELERATED'] = '0'
            
            # Get container's image
            image = container.attrs.get('Config', {}).get('Image', '')
            
            # Get container's volumes
            mounts = container.attrs.get('Mounts', [])
            volumes = {}
            for mount in mounts:
                if mount.get('Type') == 'bind':
                    source = mount.get('Source', '')
                    destination = mount.get('Destination', '')
                    mode = 'rw' if mount.get('RW', True) else 'ro'
                    if source and destination:
                        volumes[source] = {'bind': destination, 'mode': mode}
            
            # Note: On macOS with Docker Desktop, we use host.docker.internal
            # No need to mount X11 socket as Docker handles the forwarding
            
            # Get network
            network_settings = container.attrs.get('NetworkSettings', {})
            networks = list(network_settings.get('Networks', {}).keys())
            network_mode = networks[0] if networks else 'bridge'
            
            # Get launch mode from settings if not provided
            if not launch_mode:
                from .settings_manager import SettingsManager
                settings = SettingsManager()
                settings.load()
                launch_mode = settings.get('launch_mode', 'api')
            
            logger.info(f"Running GUI app '{app}' from container {name} with DISPLAY={display}, mode={launch_mode}")
            
            import platform
            system = platform.system()
            
            # Generate unique name for GUI app container
            import time
            app_container_name = f"{name}-gui-{int(time.time())}"
            
            if launch_mode == 'terminal' and system == "Darwin":
                # macOS - run in Terminal window
                env_flags = ' '.join([f'-e {k}={v}' for k, v in env_vars.items()])
                
                # Add volume flags
                volume_flags = ''
                if volumes:
                    for host_path, mount_info in volumes.items():
                        container_path = mount_info['bind']
                        mode = mount_info.get('mode', 'rw')
                        volume_flags += f' -v {host_path}:{container_path}:{mode}'
                
                script = f'''
tell application "Terminal"
    do script "docker run --rm -it --name {app_container_name} --network {network_mode} {env_flags}{volume_flags} {image} {app}"
    activate
end tell
'''
                import subprocess
                subprocess.Popen(['osascript', '-e', script])
                logger.info("GUI app started in Terminal window")
                return True
                
            elif launch_mode == 'custom':
                # Run with custom terminal command
                from .settings_manager import SettingsManager
                settings = SettingsManager()
                settings.load()
                custom_cmd = settings.get('custom_terminal_command', '')
                
                if custom_cmd and '{command}' in custom_cmd:
                    env_flags = ' '.join([f'-e {k}={v}' for k, v in env_vars.items()])
                    
                    volume_flags = ''
                    if volumes:
                        for host_path, mount_info in volumes.items():
                            container_path = mount_info['bind']
                            mode = mount_info.get('mode', 'rw')
                            volume_flags += f' -v {host_path}:{container_path}:{mode}'
                    
                    docker_cmd = f"docker run --rm -it --name {app_container_name} --network {network_mode} {env_flags}{volume_flags} {image} {app}"
                    final_cmd = custom_cmd.replace('{command}', docker_cmd)
                    
                    import subprocess
                    subprocess.Popen(final_cmd, shell=True)
                    logger.info("GUI app started with custom command")
                    return True
                else:
                    logger.error("Custom command not configured properly")
                    return False
                    
            else:
                # API mode (default) - run via Docker API like disposable
                logger.info("Starting GUI app container via API...")
                
                try:
                    # Create and start container with API
                    gui_container = self.client.containers.run(
                        image=image,
                        command=app,
                        name=app_container_name,
                        environment=env_vars,
                        volumes=volumes,
                        network_mode=network_mode,
                        auto_remove=True,  # Auto-remove when stopped
                        detach=True,  # Run in background
                        tty=True,
                        stdin_open=True
                    )
                    
                    logger.info(f"GUI app container started: {gui_container.id[:12]}")
                    
                    # Return container info for logs window
                    return {
                        'success': True,
                        'container_id': gui_container.id,
                        'container_name': app_container_name
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to start GUI app container: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {'success': False, 'error': str(e)}
            
        except ContainerNotFound:
            logger.error(f"Container {name} not found")
            return False
        except Exception as e:
            logger.error(f"Error running GUI app in {name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
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

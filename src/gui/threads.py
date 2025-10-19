"""
Background threads for async operations
"""

import os
import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class ContainerCreateThread(QThread):
    """Thread for async container creation"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    open_logs_signal = pyqtSignal(str, str)  # container_id, container_name
    
    def __init__(self, docker_manager, template_manager, config):
        super().__init__()
        self.docker_manager = docker_manager
        self.template_manager = template_manager
        self.config = config
        self.container_for_logs = None
        
    def run(self):
        """Run container creation"""
        from ..localization import t
        
        try:
            self.log_signal.emit(t('messages.starting_container_creation').format(name=self.config['name']))
            self.progress_signal.emit(10)
            
            # Build image if needed
            template = self.template_manager.get_template(self.config['template_id'])
            if not template:
                self.finished_signal.emit(False, t('messages.failed_build_image').format(tag=self.config['template_id']))
                return
            
            # Include platform in image tag if specified
            platform_val = self.config.get('platform')
            platform_suffix = ''
            if platform_val:
                # Extract architecture from platform (e.g., linux/amd64 -> amd64)
                arch = platform_val.split('/')[-1] if '/' in platform_val else platform_val
                platform_suffix = f"-{arch}"
            
            image_tag = f"ghostcontainers-{self.config['template_id']}{platform_suffix}:latest"
            self.log_signal.emit(t('messages.checking_image').format(tag=image_tag))
            self.progress_signal.emit(20)
            
            # Check if we need to build/rebuild
            need_build = False
            image_found = False
            
            # Check if image exists
            try:
                from ..docker_api.exceptions import ImageNotFound
                image = self.docker_manager.client.images.get(image_tag)
                image_found = True
                
                # If platform specified, check if image platform matches
                if platform_val:
                    image_platform = image.attrs.get('Architecture', '')
                    requested_arch = platform_val.split('/')[-1] if '/' in platform_val else platform_val
                    
                    # Normalize architecture names
                    arch_map = {
                        'amd64': 'x86_64',
                        'arm64': 'aarch64',
                        'arm': 'arm'
                    }
                    image_arch = arch_map.get(image_platform.lower(), image_platform.lower())
                    req_arch = arch_map.get(requested_arch.lower(), requested_arch.lower())
                    
                    if image_arch != req_arch and requested_arch.lower() not in image_platform.lower():
                        self.log_signal.emit(f"Image platform ({image_platform}) doesn't match requested ({platform_val})")
                        self.log_signal.emit("Rebuilding image for requested platform...")
                        need_build = True
                    else:
                        self.log_signal.emit(t('messages.image_found').format(tag=image_tag))
                else:
                    self.log_signal.emit(t('messages.image_found').format(tag=image_tag))
            except ImageNotFound:
                self.log_signal.emit(f"Image {image_tag} not found - need to build")
                need_build = True
            except Exception as e:
                self.log_signal.emit(f"Error checking image: {str(e)} - will rebuild")
                need_build = True
            
            # Build image if needed
            if need_build:
                self.log_signal.emit(t('messages.building_image').format(tag=image_tag))
                self.progress_signal.emit(30)
                
                # Pass platform to build if specified
                build_kwargs = {}
                if platform_val:
                    build_kwargs['platform'] = platform_val
                    self.log_signal.emit(f"Building for platform: {platform_val}")
                
                if not self.docker_manager.build_image(template['path'], image_tag, 
                                                       callback=lambda msg: self.log_signal.emit(msg),
                                                       **build_kwargs):
                    self.finished_signal.emit(False, t('messages.failed_build_image').format(tag=image_tag))
                    return
            
            self.progress_signal.emit(70)
            self.log_signal.emit(t('messages.creating_container'))
            
            # Prepare volumes - start with user-specified volumes
            volumes = self.config.get('volumes', {}).copy()
            
            # Add GUI support volumes on macOS
            if self.config.get('gui', False):
                import platform
                if platform.system() == "Darwin":  # macOS with XQuartz
                    # Get DISPLAY socket path
                    display = self.config.get('environment', {}).get('DISPLAY', '')
                    if display and ':' in display:
                        # Extract socket path from DISPLAY
                        # Format: /private/tmp/com.apple.launchd.xxx/org.xquartz:0
                        socket_path = display.split(':')[0]
                        if socket_path and os.path.exists(socket_path):
                            volumes[socket_path] = {'bind': '/tmp/.X11-unix', 'mode': 'rw'}
                            self.log_signal.emit(f"Mounting X11 socket: {socket_path}")
            
            # Log shared folders
            for host_path, mount_info in volumes.items():
                if '/tmp/.X11-unix' not in mount_info['bind']:  # Don't log X11 socket
                    mode = mount_info.get('mode', 'rw')
                    self.log_signal.emit(f"Volume: {host_path} -> {mount_info['bind']} ({mode})")
            
            # Prepare kwargs for create_container
            create_kwargs = {}
            platform_val = self.config.get('platform')
            if platform_val:
                create_kwargs['platform'] = platform_val
                self.log_signal.emit(f"Platform: {platform_val}")
            
            # For disposable containers with startup command, skip create and run directly
            if self.config.get('disposable') and self.config.get('startup_command'):
                container_id = 'disposable'  # Placeholder ID for disposable containers
                startup_cmd = self.config['startup_command']
                self.log_signal.emit(f"Starting disposable container with command: {startup_cmd}")
                
                # Add to database for tracking by NAME (since container has --rm flag)
                # This allows tracking even when container auto-removes
                container_name = self.config['name']
                if self.docker_manager.db:
                    # Use container name as ID for disposable containers
                    # This way we can track by name even after container is removed
                    self.docker_manager.db.add_container(
                        container_id=container_name,  # Use name as ID for tracking
                        name=container_name,
                        template=self.config['template_id'],
                        disposable=True
                    )
                    
                    # Copy template apps to database
                    if 'template_apps' in self.config:
                        for app in self.config['template_apps']:
                            self.docker_manager.db.add_container_app(
                                container_name=container_name,
                                app_name=app.get('name', ''),
                                app_command=app.get('command', '')
                            )
                    
                    # Track shared folders
                    if volumes:
                        for host_path, mount_info in volumes.items():
                            container_path = mount_info.get('bind', '')
                            if container_path:
                                self.docker_manager.db.add_shared_folder(
                                    container_id=container_name,
                                    host_path=host_path,
                                    container_path=container_path
                                )
                
                # Prepare environment
                env_dict = self.config.get('environment', {}).copy()
                
                # Parse command for inline environment variables (e.g., "MOZ_X11_EGL=1 firefox")
                import shlex
                actual_command = []
                
                try:
                    # Split command respecting quotes
                    parts = shlex.split(startup_cmd)
                    for part in parts:
                        if '=' in part and not part.startswith('-'):
                            # This looks like ENV=value
                            key, value = part.split('=', 1)
                            # Check if key is a valid environment variable name
                            if key.replace('_', '').isalnum() and key[0].isalpha():
                                env_dict[key] = value
                                continue
                        actual_command.append(part)
                    
                    # Reconstruct command without env vars
                    parsed_cmd = ' '.join(actual_command) if actual_command else startup_cmd
                except:
                    # If parsing fails, use original command
                    parsed_cmd = startup_cmd
                
                # Run container with the command
                import platform
                import subprocess
                system = platform.system()
                container_name = self.config['name']
                
                # Get launch mode from config (set by dialog)
                # If not specified in config, fall back to settings
                launch_mode = self.config.get('launch_mode')
                
                if not launch_mode:
                    from ..settings_manager import SettingsManager
                    settings = SettingsManager()
                    settings.load()
                    launch_mode = settings.get('launch_mode', 'api')
                
                self.log_signal.emit(f"Launch mode: {launch_mode}")
                
                if launch_mode == 'terminal' and system == "Darwin":
                    # macOS - run in Terminal with auto-remove
                    env_flags = ' '.join([f'-e {k}={v}' for k, v in env_dict.items()])
                    
                    # Add volume flags from config
                    volume_flags = ''
                    if volumes:
                        for host_path, mount_info in volumes.items():
                            container_path = mount_info['bind']
                            mode = mount_info.get('mode', 'rw')
                            volume_flags += f' -v {host_path}:{container_path}:{mode}'
                    
                    # Add platform flag if specified
                    platform_flag = ''
                    if platform_val:
                        platform_flag = f'--platform {platform_val}'
                    
                    # Add network flag
                    network_flag = ''
                    if self.config.get('network'):
                        network_flag = f'--network {self.config["network"]}'
                    
                    # Add hostname flag
                    hostname_flag = ''
                    if self.config.get('hostname'):
                        hostname_flag = f'--hostname {self.config["hostname"]}'
                    
                    script = f'''
tell application "Terminal"
    do script "docker run --rm -it --name {container_name} {platform_flag} {network_flag} {hostname_flag} {env_flags}{volume_flags} {image_tag} sh -c '{parsed_cmd}'"
    activate
end tell
'''
                    subprocess.Popen(['osascript', '-e', script])
                    self.log_signal.emit(t('messages.started_in_terminal'))
                
                elif launch_mode == 'api':
                    # Run using Docker API with logs window
                    self.log_signal.emit("Starting container via API...")
                    
                    try:
                        # Create and start container with API
                        container = self.docker_manager.client.containers.run(
                            image=image_tag,
                            command=parsed_cmd,
                            name=container_name,
                            environment=env_dict,
                            volumes=volumes,
                            network_mode=self.config.get('network', 'bridge'),
                            hostname=self.config.get('hostname'),
                            auto_remove=True,  # Disposable
                            detach=True,  # Run in background
                            tty=True,
                            stdin_open=True,
                            platform=platform_val
                        )
                        
                        self.log_signal.emit(f"Container started: {container.id[:12]}")
                        
                        # Emit signal to open logs window in main thread
                        self.open_logs_signal.emit(container.id, container_name)
                        
                        self.log_signal.emit("Opening logs window...")
                        
                    except Exception as e:
                        self.log_signal.emit(f"Failed to start container: {e}")
                        raise
                
                elif launch_mode == 'custom':
                    # Run with custom terminal command
                    custom_cmd = settings.get('custom_terminal_command', '')
                    if custom_cmd and '{command}' in custom_cmd:
                        # Build docker run command
                        env_flags = ' '.join([f'-e {k}={v}' for k, v in env_dict.items()])
                        volume_flags = ''
                        if volumes:
                            for host_path, mount_info in volumes.items():
                                container_path = mount_info['bind']
                                mode = mount_info.get('mode', 'rw')
                                volume_flags += f' -v {host_path}:{container_path}:{mode}'
                        
                        platform_flag = f'--platform {platform_val}' if platform_val else ''
                        network_flag = f'--network {self.config.get("network")}' if self.config.get('network') else ''
                        hostname_flag = f'--hostname {self.config.get("hostname")}' if self.config.get('hostname') else ''
                        
                        docker_cmd = f"docker run --rm -it --name {container_name} {platform_flag} {network_flag} {hostname_flag} {env_flags}{volume_flags} {image_tag} sh -c '{parsed_cmd}'"
                        
                        # Replace {command} with actual docker command
                        final_cmd = custom_cmd.replace('{command}', docker_cmd)
                        
                        # Execute custom command
                        subprocess.Popen(final_cmd, shell=True)
                        self.log_signal.emit("Started with custom terminal command")
                    else:
                        self.log_signal.emit("Custom command not configured properly")
                
                else:
                    # Fallback - run in background via API
                    launch_mode = self.config.get('launch_mode', 'api')
                    result = self.docker_manager.run_gui_app(
                        container_name,
                        startup_cmd,
                        launch_mode=launch_mode
                    )
                    if result:
                        self.log_signal.emit(t('command_executed'))
                
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, t('messages.container_created_success').format(container_id=container_name))
            
            else:
                # Normal container - create and start it
                
                # Pass template apps if available
                if 'template_apps' in self.config:
                    create_kwargs['template_apps'] = self.config['template_apps']
                
                container_id = self.docker_manager.create_container(
                    image=image_tag,
                    name=self.config['name'],
                    environment=self.config.get('environment', {}),
                    volumes=volumes if volumes else None,
                    network_mode=self.config.get('network'),
                    hostname=self.config.get('hostname'),
                    remove=False,
                    template=self.config['template_id'],
                    **create_kwargs
                )
                
                if container_id:
                    self.progress_signal.emit(90)
                    self.log_signal.emit(t('messages.container_created_success').format(container_id=container_id[:12]))
                    
                    # Start the container
                    if self.docker_manager.start_container(self.config['name']):
                        self.log_signal.emit(t('messages.container_started').format(name=self.config['name']))
                        
                        # Run startup app if specified (like in disposable mode)
                        startup_cmd = self.config.get('startup_command')
                        if startup_cmd:
                            self.log_signal.emit(f"Starting application: {startup_cmd}")
                            # Run GUI app in the container with launch mode from config
                            launch_mode = self.config.get('launch_mode', 'api')
                            result = self.docker_manager.run_gui_app(
                                self.config['name'],
                                startup_cmd,
                                launch_mode=launch_mode
                            )
                            if result:
                                self.log_signal.emit("Application started successfully")
                            else:
                                self.log_signal.emit("Failed to start application")
                    
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(True, t('messages.container_created_success').format(container_id=container_id[:12]))
                else:
                    self.finished_signal.emit(False, t('messages.failed_create_container'))
                
        except Exception as e:
            logger.error(f"Container creation error: {e}")
            self.log_signal.emit(f"ERROR: {str(e)}")
            self.finished_signal.emit(False, str(e))


class ContainerOperationThread(QThread):
    """Thread for async container operations (start, stop, remove, etc.)"""
    status_signal = pyqtSignal(str)  # Status message with animation
    finished_signal = pyqtSignal(bool, str)  # Success, message
    
    def __init__(self, docker_manager, operation, container_name):
        super().__init__()
        self.docker_manager = docker_manager
        self.operation = operation  # 'start', 'stop', 'remove', 'restart'
        self.container_name = container_name
        
    def run(self):
        """Run container operation"""
        from ..localization import t
        
        try:
            if self.operation == 'start':
                self.status_signal.emit(t('messages.starting'))
                result = self.docker_manager.start_container(self.container_name)
                if result:
                    self.finished_signal.emit(True, t('messages.container_started').format(name=self.container_name))
                else:
                    self.finished_signal.emit(False, t('messages.failed_start_container'))
                    
            elif self.operation == 'stop':
                self.status_signal.emit(t('messages.stopping'))
                result = self.docker_manager.stop_container(self.container_name)
                if result:
                    self.finished_signal.emit(True, t('messages.container_stopped').format(name=self.container_name))
                else:
                    self.finished_signal.emit(False, t('messages.failed_stop_container'))
                    
            elif self.operation == 'restart':
                self.status_signal.emit(t('messages.restarting'))
                result = self.docker_manager.restart_container(self.container_name)
                if result:
                    self.finished_signal.emit(True, t('messages.container_restarted').format(name=self.container_name))
                else:
                    self.finished_signal.emit(False, t('messages.failed_restart_container'))
                    
            elif self.operation == 'remove':
                self.status_signal.emit(t('messages.removing'))
                # First, stop the container if it's running
                try:
                    container = self.docker_manager.client.containers.get(self.container_name)
                    if container.status == 'running':
                        self.status_signal.emit(t('messages.stopping_before_remove'))
                        self.docker_manager.stop_container(self.container_name)
                except:
                    pass
                
                # Now remove
                result = self.docker_manager.remove_container(self.container_name)
                if result:
                    self.finished_signal.emit(True, t('messages.container_removed').format(name=self.container_name))
                else:
                    self.finished_signal.emit(False, t('messages.failed_remove_container'))
                    
        except Exception as e:
            logger.error(f"Container operation error: {e}")
            self.finished_signal.emit(False, str(e))

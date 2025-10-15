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
    
    def __init__(self, docker_manager, template_manager, config):
        super().__init__()
        self.docker_manager = docker_manager
        self.template_manager = template_manager
        self.config = config
        
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
            
            # Check if image exists
            try:
                image = self.docker_manager.client.images.get(image_tag)
                
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
            except:
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
            
            # Create container
            container_id = self.docker_manager.create_container(
                image=image_tag,
                name=self.config['name'],
                environment=self.config.get('environment', {}),
                volumes=volumes if volumes else None,
                network_mode=self.config.get('network'),
                hostname=self.config.get('hostname'),
                remove=self.config.get('disposable', False),
                template=self.config['template_id'],
                **create_kwargs
            )
            
            if container_id:
                self.progress_signal.emit(90)
                self.log_signal.emit(t('messages.container_created_success').format(container_id=container_id[:12]))
                
                # For disposable containers with startup command, run directly with the command
                if self.config.get('disposable') and self.config.get('startup_command'):
                    startup_cmd = self.config['startup_command']
                    self.log_signal.emit(f"Starting disposable container with command: {startup_cmd}")
                    
                    # Remove the created container and run with the command instead
                    try:
                        container = self.docker_manager.client.containers.get(container_id)
                        container.remove(force=True)
                    except:
                        pass
                    
                    # Prepare environment
                    env_dict = self.config.get('environment', {}).copy()
                    
                    # Parse command for inline environment variables (e.g., "MOZ_X11_EGL=1 firefox")
                    import shlex
                    cmd_parts = []
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
                    system = platform.system()
                    container_name = self.config['name']
                    use_terminal = self.config.get('use_terminal', False)
                    
                    if use_terminal and system == "Darwin":
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
                        import subprocess
                        subprocess.Popen(['osascript', '-e', script])
                        self.log_signal.emit(t('messages.started_in_terminal'))
                    else:
                        # Run in background or foreground depending on use_terminal
                        result = self.docker_manager.run_gui_app(
                            container_name,
                            startup_cmd
                        )
                        if result:
                            self.log_signal.emit(t('command_executed'))
                
                else:
                    # Normal container - just start it
                    if self.docker_manager.start_container(self.config['name']):
                        self.log_signal.emit(t('messages.container_started').format(name=self.config['name']))
                
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

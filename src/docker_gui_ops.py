"""
Docker GUI Operations - GUI application management
"""

import os
import logging
import platform
import time
import subprocess
from typing import Optional, Dict

from .docker_api.exceptions import ContainerNotFound

logger = logging.getLogger(__name__)


def run_gui_app(
    docker_manager,
    name: str,
    app: str,
    user: Optional[str] = None,
    launch_mode: Optional[str] = None
):
    """
    Run GUI application in container
    
    Args:
        docker_manager: DockerManager instance
        name: Container name
        app: Application command
        user: User to run as (default: container's default user)
        launch_mode: Launch mode - 'api', 'terminal', or 'custom'
        
    Returns:
        True if successful, or dict with container info for API mode
    """
    try:
        # Setup X11 permissions and verify display
        from .x11_helper import setup_xhost_permissions, verify_display_socket, check_xquartz_running, get_display
        
        logger.info(f"[run_gui_app] Starting GUI app '{app}' in container '{name}'")
        logger.info(f"[run_gui_app] Launch mode: {launch_mode}")
        
        # Check if XQuartz is running on macOS
        system = platform.system()
        logger.debug(f"[run_gui_app] Platform: {system}")
        
        if system == "Darwin":
            if not check_xquartz_running():
                logger.error("[run_gui_app] XQuartz is not running!")
                return {'success': False, 'error': 'XQuartz is not running. Please start XQuartz and try again.'}
        
        # Verify DISPLAY socket
        display_ok, display_msg = verify_display_socket()
        if not display_ok:
            logger.error(f"[run_gui_app] Display verification failed: {display_msg}")
            return {'success': False, 'error': display_msg}
        
        logger.info(f"[run_gui_app] Display check: {display_msg}")
        
        # Setup xhost permissions
        xhost_ok = setup_xhost_permissions()
        if xhost_ok:
            logger.info("[run_gui_app] xhost permissions configured")
        else:
            logger.warning("[run_gui_app] Failed to setup xhost permissions, continuing anyway...")
        
        # Get container to find its image and volumes
        container = docker_manager.client.containers.get(name)
        logger.debug(f"[run_gui_app] Container found: {container.id[:12]}")
        
        # Get DISPLAY from environment
        display = get_display()
        logger.info(f"[run_gui_app] Using DISPLAY: {display}")
        
        # Prepare environment variables
        # On macOS, use host.docker.internal instead of socket path
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
        
        logger.info(f"Running GUI app '{app}' from container {name} with DISPLAY={env_vars['DISPLAY']}, mode={launch_mode}")
        
        # Generate unique name for GUI app container
        app_container_name = f"{name}-gui-{int(time.time())}"
        
        if launch_mode == 'terminal' and system == "Darwin":
            return _run_in_terminal(app_container_name, env_vars, volumes, network_mode, image, app)
        elif launch_mode == 'custom':
            return _run_with_custom_command(app_container_name, env_vars, volumes, network_mode, image, app)
        else:
            return _run_via_api(docker_manager, app_container_name, env_vars, volumes, network_mode, image, app)
        
    except ContainerNotFound:
        logger.error(f"Container {name} not found")
        return False
    except Exception as e:
        logger.error(f"Error running GUI app in {name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def _run_in_terminal(app_container_name, env_vars, volumes, network_mode, image, app):
    """Run GUI app in Terminal window (macOS)"""
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
    subprocess.Popen(['osascript', '-e', script])
    logger.info("GUI app started in Terminal window")
    return True


def _run_with_custom_command(app_container_name, env_vars, volumes, network_mode, image, app):
    """Run GUI app with custom terminal command"""
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
        
        subprocess.Popen(final_cmd, shell=True)
        logger.info("GUI app started with custom command")
        return True
    else:
        logger.error("Custom command not configured properly")
        return False


def _run_via_api(docker_manager, app_container_name, env_vars, volumes, network_mode, image, app):
    """Run GUI app via Docker API"""
    logger.info("Starting GUI app container via API...")
    
    try:
        # Create and start container with API
        gui_container = docker_manager.client.containers.run(
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

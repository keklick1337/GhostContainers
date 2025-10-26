"""
Terminal Launcher - Unified terminal/command execution system
Supports multiple launch modes: API (with logs window), Terminal, Custom
"""

import platform
import subprocess
import logging
from typing import Optional, Dict, List
from .settings_manager import SettingsManager

logger = logging.getLogger(__name__)


class TerminalLauncher:
    """
    Unified launcher for executing commands in containers
    
    Modes:
    - 'api': Execute via Docker API with logs window (default)
    - 'terminal': Spawn system terminal
    - 'custom': Use custom terminal command from settings
    """
    
    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        """
        Initialize terminal launcher
        
        Args:
            settings_manager: Settings manager instance (will create if None)
        """
        self.settings = settings_manager or SettingsManager()
        self.settings.load()
        self.system = platform.system()
    
    def launch(
        self,
        container_name: str,
        command: str,
        mode: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        image: Optional[str] = None,
        platform_val: Optional[str] = None,
        user: Optional[str] = None,
        additional_flags: Optional[List[str]] = None
    ) -> bool:
        """
        Launch container with command using specified mode
        
        Args:
            container_name: Container name
            command: Command to execute
            mode: Launch mode ('api', 'terminal', 'custom', or None for default)
            env_vars: Environment variables
            volumes: Volume mounts
            network: Network name
            image: Image name (required for new containers)
            platform_val: Platform (e.g., 'linux/amd64')
            user: User to run as
            additional_flags: Additional docker run flags
            
        Returns:
            bool: True if launched successfully
        """
        # Determine mode
        if mode is None:
            mode = self.settings.get('launch_mode', 'api')
        
        logger.info(f"[TerminalLauncher] Launching container '{container_name}' with mode '{mode}'")
        logger.debug(f"[TerminalLauncher] Command: {command}")
        
        # Route to appropriate launcher
        if mode == 'terminal':
            return self._launch_terminal(
                container_name, command, env_vars, volumes, 
                network, image, platform_val, user, additional_flags
            )
        elif mode == 'custom':
            return self._launch_custom_terminal(
                container_name, command, env_vars, volumes,
                network, image, platform_val, user, additional_flags
            )
        elif mode == 'api':
            # API mode is handled by caller (requires docker_manager and parent window)
            logger.info("[TerminalLauncher] API mode - caller should handle logs window")
            return True
        else:
            logger.error(f"[TerminalLauncher] Unknown mode: {mode}")
            return False
    
    def _build_docker_command(
        self,
        container_name: str,
        command: str,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        image: Optional[str] = None,
        platform_val: Optional[str] = None,
        user: Optional[str] = None,
        additional_flags: Optional[List[str]] = None
    ) -> str:
        """
        Build docker run command string
        
        Returns:
            str: Complete docker run command
        """
        parts = ['docker', 'run', '--rm', '-it', f'--name={container_name}']
        
        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                parts.append(f'-e')
                parts.append(f'{key}={value}')
        
        # Add volumes
        if volumes:
            for host_path, mount_info in volumes.items():
                container_path = mount_info['bind']
                mode = mount_info.get('mode', 'rw')
                parts.append('-v')
                parts.append(f'{host_path}:{container_path}:{mode}')
        
        # Add network
        if network:
            parts.append(f'--network={network}')
        
        # Add platform
        if platform_val:
            parts.append(f'--platform={platform_val}')
        
        # Add user
        if user:
            parts.append(f'--user={user}')
        
        # Add additional flags
        if additional_flags:
            parts.extend(additional_flags)
        
        # Add image
        if image:
            parts.append(image)
        else:
            logger.error("[TerminalLauncher] No image specified!")
            return ""
        
        # Add command
        parts.append('/bin/sh')
        parts.append('-c')
        parts.append(command)
        
        return ' '.join(parts)
    
    def _launch_terminal(
        self,
        container_name: str,
        command: str,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        image: Optional[str] = None,
        platform_val: Optional[str] = None,
        user: Optional[str] = None,
        additional_flags: Optional[List[str]] = None
    ) -> bool:
        """
        Launch in system terminal
        
        Returns:
            bool: True if terminal launched
        """
        docker_cmd = self._build_docker_command(
            container_name, command, env_vars, volumes,
            network, image, platform_val, user, additional_flags
        )
        
        if not docker_cmd:
            return False
        
        logger.info(f"[TerminalLauncher] Launching terminal with command")
        logger.debug(f"[TerminalLauncher] Docker command: {docker_cmd}")
        
        try:
            if self.system == "Darwin":
                # macOS - use Terminal.app
                escaped_cmd = docker_cmd.replace('"', '\\"')
                terminal_cmd = ['osascript', '-e', f'tell app "Terminal" to do script "{escaped_cmd}"']
                subprocess.Popen(terminal_cmd)
                logger.info("[TerminalLauncher] ✓ Launched macOS Terminal")
                return True
                
            elif self.system == "Linux":
                # Linux - try various terminal emulators
                terminals = [
                    ['x-terminal-emulator', '-e'],
                    ['gnome-terminal', '--'],
                    ['konsole', '-e'],
                    ['xfce4-terminal', '-e'],
                    ['xterm', '-e'],
                    ['alacritty', '-e'],
                    ['kitty', '-e'],
                ]
                
                for term_cmd in terminals:
                    try:
                        # Check if terminal exists
                        subprocess.run(['which', term_cmd[0]], 
                                     capture_output=True, check=True, timeout=1)
                        
                        # Launch terminal
                        full_cmd = term_cmd + ['/bin/sh', '-c', docker_cmd]
                        subprocess.Popen(full_cmd)
                        logger.info(f"[TerminalLauncher] ✓ Launched {term_cmd[0]}")
                        return True
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                    except Exception as e:
                        logger.debug(f"[TerminalLauncher] Failed to launch {term_cmd[0]}: {e}")
                        continue
                
                logger.error("[TerminalLauncher] No terminal emulator found!")
                logger.error("[TerminalLauncher] Install: gnome-terminal, konsole, xfce4-terminal, or xterm")
                return False
                
            elif self.system == "Windows":
                # Windows - use cmd or PowerShell
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', docker_cmd])
                logger.info("[TerminalLauncher] ✓ Launched Windows terminal")
                return True
            
            else:
                logger.error(f"[TerminalLauncher] Unsupported platform: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"[TerminalLauncher] Failed to launch terminal: {e}")
            return False
    
    def _launch_custom_terminal(
        self,
        container_name: str,
        command: str,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        image: Optional[str] = None,
        platform_val: Optional[str] = None,
        user: Optional[str] = None,
        additional_flags: Optional[List[str]] = None
    ) -> bool:
        """
        Launch using custom terminal command from settings
        
        Returns:
            bool: True if custom terminal launched
        """
        custom_cmd = self.settings.get('custom_terminal_command', '')
        
        if not custom_cmd:
            logger.warning("[TerminalLauncher] No custom terminal command configured, falling back to default")
            return self._launch_terminal(
                container_name, command, env_vars, volumes,
                network, image, platform_val, user, additional_flags
            )
        
        docker_cmd = self._build_docker_command(
            container_name, command, env_vars, volumes,
            network, image, platform_val, user, additional_flags
        )
        
        if not docker_cmd:
            return False
        
        # Replace {command} placeholder
        full_cmd = custom_cmd.replace('{command}', docker_cmd)
        
        logger.info(f"[TerminalLauncher] Launching custom terminal")
        logger.debug(f"[TerminalLauncher] Custom command: {full_cmd}")
        
        try:
            subprocess.Popen(full_cmd, shell=True)
            logger.info("[TerminalLauncher] ✓ Launched custom terminal")
            return True
        except Exception as e:
            logger.error(f"[TerminalLauncher] Failed to launch custom terminal: {e}")
            return False
    
    @staticmethod
    def get_docker_shell_command(container_name: str, as_root: bool = False) -> List[str]:
        """
        Get docker exec command for opening shell in running container
        
        Args:
            container_name: Container name
            as_root: Execute as root user
            
        Returns:
            List[str]: Command parts for subprocess
        """
        cmd = ['docker', 'exec', '-it']
        
        if as_root:
            cmd.extend(['-u', 'root'])
        
        cmd.extend([container_name, '/bin/sh'])
        
        return cmd
    
    def launch_shell(self, container_name: str, as_root: bool = False) -> bool:
        """
        Launch shell in running container via terminal
        
        Args:
            container_name: Container name
            as_root: Execute as root user
            
        Returns:
            bool: True if launched successfully
        """
        shell_cmd = self.get_docker_shell_command(container_name, as_root)
        shell_cmd_str = ' '.join(shell_cmd)
        
        logger.info(f"[TerminalLauncher] Launching shell for container '{container_name}' (root={as_root})")
        
        try:
            if self.system == "Darwin":
                # macOS - use Terminal.app
                escaped_cmd = shell_cmd_str.replace('"', '\\"')
                terminal_cmd = ['osascript', '-e', f'tell app "Terminal" to do script "{escaped_cmd}"']
                subprocess.Popen(terminal_cmd)
                logger.info("[TerminalLauncher] ✓ Launched shell in macOS Terminal")
                return True
                
            elif self.system == "Linux":
                # Linux - try various terminal emulators
                terminals = [
                    ['x-terminal-emulator', '-e'],
                    ['gnome-terminal', '--'],
                    ['konsole', '-e'],
                    ['xfce4-terminal', '-e'],
                    ['xterm', '-e'],
                    ['alacritty', '-e'],
                    ['kitty', '-e'],
                ]
                
                for term_cmd in terminals:
                    try:
                        subprocess.run(['which', term_cmd[0]], 
                                     capture_output=True, check=True, timeout=1)
                        
                        full_cmd = term_cmd + shell_cmd
                        subprocess.Popen(full_cmd)
                        logger.info(f"[TerminalLauncher] ✓ Launched shell in {term_cmd[0]}")
                        return True
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                    except Exception as e:
                        logger.debug(f"[TerminalLauncher] Failed {term_cmd[0]}: {e}")
                        continue
                
                logger.error("[TerminalLauncher] No terminal emulator found!")
                return False
                
            elif self.system == "Windows":
                # Windows
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k'] + shell_cmd)
                logger.info("[TerminalLauncher] ✓ Launched shell in Windows terminal")
                return True
            
            else:
                logger.error(f"[TerminalLauncher] Unsupported platform: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"[TerminalLauncher] Failed to launch shell: {e}")
            return False

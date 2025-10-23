"""
X Server Manager - auto-detection and configuration for different platforms
"""

import os
import platform
import subprocess
import logging
from typing import Dict, Optional, Tuple
import socket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import X11 constants
from .x11_helper import X11_SOCKET_DIR


class XServerManager:
    """X Server forwarding management"""
    
    def __init__(self):
        """Initialize X Server manager"""
        self.os_type = platform.system()
        self.display = None
        self.xauth_path = None
        self.session_type = self._detect_session_type()
        
    def _detect_session_type(self) -> str:
        """
        Detect graphical session type
        
        Returns:
            'wayland', 'x11', 'macos', 'windows' or 'unknown'
        """
        from .x11_helper import get_display
        
        if self.os_type == "Linux":
            # Check Wayland
            if os.environ.get('WAYLAND_DISPLAY'):
                return 'wayland'
            # Check X11
            elif get_display():
                return 'x11'
            else:
                return 'unknown'
        elif self.os_type == "Darwin":
            return 'macos'
        elif self.os_type == "Windows":
            return 'windows'
        else:
            return 'unknown'
    
    def detect_display(self) -> Optional[str]:
        """
        Auto-detect DISPLAY
        
        Returns:
            DISPLAY variable or None
        """
        from .x11_helper import get_display
        
        if self.os_type == "Linux":
            # Linux (X11 or Wayland with XWayland)
            display = get_display()
            
            # If no display found on Wayland, log helpful message
            if not display and self.session_type == 'wayland':
                logger.error("XWayland not available on Wayland session. Install xwayland package.")
                return None
            
            self.display = display
            return display
            
        elif self.os_type == "Darwin":
            # macOS
            hostname = socket.gethostname()
            self.display = f"{hostname}:0"
            return self.display
            
        elif self.os_type == "Windows":
            # Windows
            host_ip = self._get_wsl_host_ip() or 'localhost'
            self.display = f"{host_ip}:0.0"
            return self.display
            
        return None
    
    def _get_wsl_host_ip(self) -> Optional[str]:
        """
        Get host IP for WSL2
        
        Returns:
            IP host address or None
        """
        try:
            # In WSL2 host IP can be obtained from /etc/resolv.conf
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        return line.split()[1]
        except:
            pass
        return None
    
    def detect_xauthority(self) -> Optional[str]:
        """
        Auto-detect XAUTHORITY
        
        Returns:
            Path to .Xauthority or None
        """
        if self.os_type == "Linux" or self.os_type == "Darwin":
            # Check environment variable
            xauth = os.environ.get('XAUTHORITY')
            if xauth and os.path.exists(xauth):
                self.xauth_path = xauth
                return xauth
            
            # Check standard location
            home = os.path.expanduser('~')
            xauth_default = os.path.join(home, '.Xauthority')
            if os.path.exists(xauth_default):
                self.xauth_path = xauth_default
                return xauth_default
        
        return None
    
    def get_environment_vars(self) -> Dict[str, str]:
        """
        Get environment variables for X forwarding
        
        Returns:
            Dict with DISPLAY and XAUTHORITY
        """
        env_vars = {}
        
        display = self.detect_display()
        if display:
            env_vars['DISPLAY'] = display
        
        xauth = self.detect_xauthority()
        if xauth:
            env_vars['XAUTHORITY'] = '/tmp/.Xauthority'
        
        return env_vars
    
    def get_volume_mounts(self) -> Dict[str, Dict[str, str]]:
        """
        Get mounts for X Server
        
        Returns:
            Dict with volume bindings
        """
        volumes = {}
        
        if self.os_type == "Linux":
            # X11 socket
            if self.session_type == 'x11':
                if os.path.exists(X11_SOCKET_DIR):
                    volumes[X11_SOCKET_DIR] = {'bind': X11_SOCKET_DIR, 'mode': 'rw'}
                    logger.debug(f"X11: Mounting {X11_SOCKET_DIR}")
            
            # Wayland - requires XWayland
            elif self.session_type == 'wayland':
                # XWayland creates X11 socket
                if os.path.exists(X11_SOCKET_DIR):
                    volumes[X11_SOCKET_DIR] = {'bind': X11_SOCKET_DIR, 'mode': 'rw'}
                    logger.info(f"Wayland: Mounting {X11_SOCKET_DIR} for XWayland")
                else:
                    logger.warning(f"Wayland: {X11_SOCKET_DIR} not found. XWayland may not be running.")
                
                # Wayland socket (optional, for native Wayland applications)
                wayland_display = os.environ.get('WAYLAND_DISPLAY', 'wayland-0')
                wayland_socket = f"/run/user/{os.getuid()}/{wayland_display}"
                if os.path.exists(wayland_socket):
                    volumes[wayland_socket] = {'bind': f'/run/user/1000/{wayland_display}', 'mode': 'rw'}
                    logger.info(f"Wayland: Mounting Wayland socket {wayland_display}")
                else:
                    logger.debug(f"Wayland socket not found: {wayland_socket}")
            
            # .Xauthority
            xauth = self.detect_xauthority()
            if xauth and os.path.exists(xauth):
                volumes[xauth] = {'bind': '/tmp/.Xauthority', 'mode': 'ro'}
        
        elif self.os_type == "Darwin":
            # macOS - XQuartz
            # XQuartz uses network connection, mounting not required
            # But can mount .Xauthority if available
            xauth = self.detect_xauthority()
            if xauth and os.path.exists(xauth):
                volumes[xauth] = {'bind': '/tmp/.Xauthority', 'mode': 'ro'}
        
        return volumes
    
    def check_xserver_running(self) -> Tuple[bool, str]:
        """
        Check if X Server is running
        
        Returns:
            (True/False, message)
        """
        if self.os_type == "Linux":
            if self.session_type == 'x11':
                # Check X11
                try:
                    result = subprocess.run(['xdpyinfo'], 
                                          capture_output=True, 
                                          timeout=2)
                    if result.returncode == 0:
                        return True, "X11 Server running"
                    else:
                        return False, "X11 Server not responding"
                except FileNotFoundError:
                    return False, "xdpyinfo not installed (install: apt install x11-utils)"
                except subprocess.TimeoutExpired:
                    return False, "X11 Server not responding (timeout)"
                    
            elif self.session_type == 'wayland':
                # Check XWayland
                if os.path.exists(X11_SOCKET_DIR):
                    return True, "Wayland + XWayland active"
                else:
                    return False, f"XWayland not running. {X11_SOCKET_DIR} not found. Install: emerge --ask x11-base/xwayland"
                    
        elif self.os_type == "Darwin":
            # Check XQuartz on macOS
            try:
                result = subprocess.run(['ps', 'aux'], 
                                      capture_output=True, 
                                      text=True)
                if 'XQuartz' in result.stdout or 'Xquartz' in result.stdout:
                    return True, "XQuartz running"
                else:
                    return False, "XQuartz not running. Run: open -a XQuartz"
            except:
                return False, "Failed to check XQuartz"
                
        elif self.os_type == "Windows":
            # Check VcXsrv/Xming on Windows
            # Try to connect to display
            try:
                # This will work only if DISPLAY variable is set
                display = self.detect_display()
                if display:
                    return True, f"X Server presumably running on {display}"
                else:
                    return False, "DISPLAY not set. Run VcXsrv or Xming"
            except:
                return False, "Failed to check X Server"
        
        return False, "Unsupported platform"
    
    def enable_xhost_access(self) -> Tuple[bool, str]:
        """
        Allow Docker access to X Server via xhost
        
        Returns:
            (True/False, message)
        """
        if self.os_type == "Linux":
            try:
                # Allow local connections
                result = subprocess.run(['xhost', '+local:docker'], 
                                      capture_output=True, 
                                      text=True,
                                      timeout=2)
                if result.returncode == 0:
                    return True, "Docker added to xhost (local:docker)"
                else:
                    return False, f"xhost error: {result.stderr}"
            except FileNotFoundError:
                return False, "xhost not found (install: apt install x11-xserver-utils)"
            except subprocess.TimeoutExpired:
                return False, "xhost timeout"
            except Exception as e:
                return False, f"Error: {e}"
                
        elif self.os_type == "Darwin":
            try:
                # On macOS allow by hostname
                hostname = socket.gethostname()
                result = subprocess.run(['xhost', '+', hostname], 
                                      capture_output=True, 
                                      text=True,
                                      timeout=2)
                if result.returncode == 0:
                    return True, f"Access allowed for {hostname}"
                else:
                    return False, f"xhost error: {result.stderr}"
            except FileNotFoundError:
                return False, "xhost not found in XQuartz"
            except Exception as e:
                return False, f"Error: {e}"
        
        elif self.os_type == "Windows":
            return True, "On Windows configure 'Disable access control' in VcXsrv/Xming"
        
        return False, "Unsupported platform"
    
    def get_setup_instructions(self) -> str:
        """
        Get X Server setup instructions
        
        Returns:
            Instructions text
        """
        if self.os_type == "Linux":
            if self.session_type == 'x11':
                return """
X11 setup on Linux:

1. Allow Docker access to X Server:
   xhost +local:docker

2. Check DISPLAY:
   echo $DISPLAY

3. Install x11-apps for testing (optional):
   sudo apt install x11-apps
   xeyes  # test
"""
            elif self.session_type == 'wayland':
                return """
Wayland + XWayland setup on Linux:

1. Make sure that XWayland installed:
   Debian/Ubuntu: sudo apt install xwayland
   Fedora:        sudo dnf install xorg-x11-server-Xwayland
   Gentoo:        sudo emerge --ask x11-base/xwayland

2. Install xhost for access control:
   Debian/Ubuntu: sudo apt install x11-xserver-utils
   Fedora:        sudo dnf install xorg-x11-server-utils
   Gentoo:        sudo emerge --ask x11-apps/xhost

3. Allow Docker access:
   xhost +local:

3. Check variables:
   echo $DISPLAY           # Should show :0 or :1
   echo $WAYLAND_DISPLAY   # Should show wayland-0 or similar
   ls -la {X11_SOCKET_DIR}/  # Check X11 socket exists

5. If DISPLAY is wrong or missing:
   # Find correct display number
   ls {X11_SOCKET_DIR}/
   export DISPLAY=:1  # or :0, depending on what you found

6. Install x11-apps for testing:
   Debian/Ubuntu: sudo apt install x11-apps
   Gentoo:        sudo emerge --ask x11-apps/xeyes
   xeyes  # test
"""
            else:
                return "Graphical session not detected. Run X11 or Wayland."
                
        elif self.os_type == "Darwin":
            return """
XQuartz setup on macOS:

1. Install XQuartz (if not installed):
   brew install --cask xquartz

2. Run XQuartz:
   open -a XQuartz

3. **IMPORTANT**: Enable network connections in XQuartz:
   - Open XQuartz
   - Go to: XQuartz → Settings (⌘,)
   - Click on "Security" tab
   - ✓ Check "Allow connections from network clients"
   - Close and restart XQuartz

4. Allow access in Terminal:
   xhost + localhost
   xhost + 127.0.0.1
   xhost + $(hostname)

5. Check DISPLAY variable:
   echo $DISPLAY
   # Should show something like: /private/tmp/com.apple.launchd.xxx/org.xquartz:0

6. Test with xeyes (in XQuartz terminal):
   xeyes

**Note**: Containers will connect via host.docker.internal
"""
        
        elif self.os_type == "Windows":
            return """
X Server setup on Windows:

Option 1: VcXsrv (recommended)
1. Download: https://sourceforge.net/projects/vcxsrv/
   or: choco install vcxsrv

2. Run XLaunch with parameters:
   - Display settings: Multiple windows
   - Display number: 0
   - Start no client
   - Extra settings: ✓ Disable access control

3. Set variable DISPLAY in WSL/Docker:
   export DISPLAY=<your-windows-ip>:0.0

Option 2: Xming
1. Download: https://sourceforge.net/projects/xming/

2. Run Xming

3. Disable access control in settings
"""
        
        return "Unsupported platform"
    
    def get_docker_run_flags(self) -> list:
        """
        Get flags for docker run with X forwarding
        
        Returns:
            List flags
        """
        flags = []
        
        # Environment variables
        env_vars = self.get_environment_vars()
        for key, value in env_vars.items():
            flags.extend(['-e', f'{key}={value}'])
        
        # Volume mounts
        volumes = self.get_volume_mounts()
        for host_path, config in volumes.items():
            container_path = config['bind']
            mode = config.get('mode', 'rw')
            flags.extend(['-v', f'{host_path}:{container_path}:{mode}'])
        
        # Additional flags
        if self.os_type == "Linux":
            # Host network mode for better compatibility (optional)
            # flags.extend(['--network', 'host'])
            pass
        
        return flags

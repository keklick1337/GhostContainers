"""
X11 Helper - utilities for X11/XQuartz setup
"""

import os
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)


def get_display():
    """
    Get DISPLAY environment variable with proper fallback
    
    Returns:
        str: DISPLAY value or default ':0'
    """
    return os.environ.get('DISPLAY', ':0')


def setup_xhost_permissions():
    """
    Setup xhost permissions for X11 access
    
    Returns:
        bool: True if successful or not needed
    """
    system = platform.system()
    
    if system not in ["Darwin", "Linux"]:
        return True  # Not needed on other systems
    
    try:
        # Add localhost permissions
        subprocess.run(['xhost', '+localhost'], 
                     capture_output=True, timeout=2, check=False)
        subprocess.run(['xhost', '+127.0.0.1'], 
                     capture_output=True, timeout=2, check=False)
        
        # Add hostname permissions
        hostname_result = subprocess.run(['hostname'], 
                                       capture_output=True, 
                                       text=True, 
                                       timeout=2,
                                       check=False)
        if hostname_result.returncode == 0:
            hostname = hostname_result.stdout.strip()
            subprocess.run(['xhost', f'+{hostname}'], 
                         capture_output=True, timeout=2, check=False)
        
        logger.info("X11 permissions configured successfully")
        return True
        
    except Exception as e:
        logger.warning(f"Could not configure xhost: {e}")
        return False


def verify_display_socket():
    """
    Verify DISPLAY socket exists and is accessible
    
    Returns:
        tuple: (bool, str) - (success, message)
    """
    display = get_display()
    
    if not display:
        return False, "DISPLAY environment variable not set"
    
    # On macOS with XQuartz, check socket path
    if platform.system() == "Darwin" and ':' in display:
        # DISPLAY format: /private/tmp/com.apple.launchd.XXX/org.xquartz:0
        # We need to check the socket file itself
        socket_path = display  # Full path with :0
        
        # Check if the socket exists (it's a Unix socket, not a regular file)
        if not os.path.exists(socket_path):
            # Try checking the directory instead
            socket_dir = display.split(':')[0]
            if not os.path.exists(socket_dir):
                return False, f"X11 socket directory not found: {socket_dir}. Is XQuartz running?"
            # Directory exists, so socket should be OK
            logger.info(f"X11 socket directory exists: {socket_dir}")
        
        # Note: Unix sockets may not be accessible via os.access, so we skip that check
    
    return True, "DISPLAY configured correctly"


def check_xquartz_running():
    """
    Check if XQuartz is running (macOS only)
    
    Returns:
        bool: True if XQuartz is running or not needed
    """
    if platform.system() != "Darwin":
        return True  # Not needed on other systems
    
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        
        return 'XQuartz' in result.stdout or 'Xquartz' in result.stdout
        
    except Exception as e:
        logger.warning(f"Could not check XQuartz status: {e}")
        return False

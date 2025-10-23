"""
X11 Helper - utilities for X11/XQuartz setup
"""

import os
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)

# Constants
X11_SOCKET_DIR = "/tmp/.X11-unix"


def get_display():
    """
    Get DISPLAY environment variable with proper fallback
    
    For Wayland sessions, ensures XWayland DISPLAY is properly detected.
    
    Returns:
        str: DISPLAY value or None if not available
    """
    display = os.environ.get('DISPLAY')
    logger.debug(f"[get_display] Initial DISPLAY from env: {display}")
    
    # If DISPLAY is not set but we're on Wayland, check for XWayland
    if not display and platform.system() == "Linux":
        wayland_display = os.environ.get('WAYLAND_DISPLAY')
        logger.debug(f"[get_display] WAYLAND_DISPLAY: {wayland_display}")
        
        if wayland_display:
            # On Wayland, XWayland typically creates :0 or :1
            # Try to detect actual XWayland display
            logger.info(f"[get_display] Wayland session detected, searching for XWayland sockets in {X11_SOCKET_DIR}")
            
            # List all available displays
            available_displays = []
            if os.path.exists(X11_SOCKET_DIR):
                try:
                    sockets = os.listdir(X11_SOCKET_DIR)
                    logger.debug(f"[get_display] Found X11 sockets: {sockets}")
                    available_displays = [s for s in sockets if s.startswith('X')]
                except Exception as e:
                    logger.error(f"[get_display] Failed to list {X11_SOCKET_DIR}: {e}")
            
            for display_num in range(0, 10):
                x11_socket = f"{X11_SOCKET_DIR}/X{display_num}"
                if os.path.exists(x11_socket):
                    logger.info(f"[get_display] ✓ Detected XWayland display :{display_num} (socket: {x11_socket})")
                    return f":{display_num}"
                else:
                    logger.debug(f"[get_display] ✗ Display :{display_num} socket not found: {x11_socket}")
            
            # If no X11 socket found but Wayland is running
            logger.warning(f"[get_display] Wayland detected but no XWayland socket found in {X11_SOCKET_DIR}")
            if available_displays:
                logger.warning(f"[get_display] Available sockets: {available_displays}")
            else:
                logger.warning("[get_display] No X11 sockets found")
            logger.warning("[get_display] Install xwayland package:")
            logger.warning("  Gentoo: emerge --ask x11-base/xwayland")
            return None
    
    # Return existing DISPLAY or fallback to :0 if we're on X11
    result = display if display else ':0'
    logger.debug(f"[get_display] Returning DISPLAY: {result}")
    return result


def setup_xhost_permissions():
    """
    Setup xhost permissions for X11 access
    
    Returns:
        bool: True if successful or not needed
    """
    system = platform.system()
    
    if system not in ["Darwin", "Linux"]:
        return True  # Not needed on other systems
    
    # Check if xhost is available
    try:
        subprocess.run(['which', 'xhost'], 
                      capture_output=True, 
                      timeout=1,
                      check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("xhost not found. Install it for better X11 access control:")
        logger.warning("  Debian/Ubuntu: apt install x11-xserver-utils")
        logger.warning("  Fedora: dnf install xorg-x11-server-utils")
        logger.warning("  Gentoo: emerge --ask x11-apps/xhost")
        # Don't fail - containers can still work without xhost in some cases
        return True
    
    try:
        # Add localhost permissions
        subprocess.run(['xhost', '+localhost'], 
                     capture_output=True, timeout=2, check=False)
        subprocess.run(['xhost', '+127.0.0.1'], 
                     capture_output=True, timeout=2, check=False)
        
        # For better security on Linux, use +local: instead of +localhost
        if system == "Linux":
            subprocess.run(['xhost', '+local:'], 
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
        # Don't fail completely - container might still work
        return True


def verify_display_socket():
    """
    Verify DISPLAY socket exists and is accessible
    
    Returns:
        tuple: (bool, str) - (success, message)
    """
    display = get_display()
    logger.info(f"[verify_display_socket] Verifying DISPLAY: {display}")
    
    if not display:
        # Check if we're on Wayland without XWayland
        if platform.system() == "Linux" and os.environ.get('WAYLAND_DISPLAY'):
            logger.error("[verify_display_socket] Wayland detected but no DISPLAY found")
            return False, "Wayland detected but XWayland is not running. Install xwayland package:\n" \
                         "  Debian/Ubuntu: apt install xwayland\n" \
                         "  Fedora: dnf install xorg-x11-server-Xwayland\n" \
                         "  Gentoo: emerge --ask x11-base/xwayland"
        logger.error("[verify_display_socket] DISPLAY environment variable not set")
        return False, "DISPLAY environment variable not set"
    
    # On Linux (X11 or Wayland+XWayland), check X11 socket
    if platform.system() == "Linux":
        # Extract display number (e.g., :0 -> 0, :1 -> 1)
        display_num = display.split(':')[-1].split('.')[0]
        x11_socket = f"{X11_SOCKET_DIR}/X{display_num}"
        
        logger.debug(f"[verify_display_socket] Checking socket: {x11_socket}")
        
        # List all available X11 sockets for debugging
        if os.path.exists(X11_SOCKET_DIR):
            try:
                available = os.listdir(X11_SOCKET_DIR)
                logger.info(f"[verify_display_socket] Available X11 sockets: {available}")
            except Exception as e:
                logger.warning(f"[verify_display_socket] Could not list {X11_SOCKET_DIR}: {e}")
        
        if not os.path.exists(x11_socket):
            wayland_display = os.environ.get('WAYLAND_DISPLAY')
            logger.error(f"[verify_display_socket] Socket not found: {x11_socket}")
            
            if wayland_display:
                return False, f"Wayland session detected but X11 socket missing: {x11_socket}\n" \
                             "XWayland may not be running. Try:\n" \
                             "  1. Restart your Wayland session\n" \
                             "  2. Install xwayland package\n" \
                             "  3. Check logs: journalctl --user -xe | grep -i xwayland"
            else:
                return False, f"X11 socket not found: {x11_socket}\n" \
                             "Is X server running?"
        
        logger.info(f"[verify_display_socket] ✓ X11 socket verified: {x11_socket}")
        return True, f"DISPLAY configured correctly ({display})"
    
    # On macOS with XQuartz, check socket path
    elif platform.system() == "Darwin" and ':' in display:
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

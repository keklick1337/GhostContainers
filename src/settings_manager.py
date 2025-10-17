"""
Settings Manager for GhostContainers
Manages application settings stored in JSON file
"""

import json
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manager for application settings"""
    
    DEFAULT_SETTINGS = {
        'language': 'en',  # Language: en, ru
        'launch_mode': 'api',  # Launch mode: terminal, api, custom (default: api)
        'custom_terminal_command': '',  # Custom command for terminal launch
        'theme': 'system',  # Theme: system, light, dark
        'auto_refresh_interval': 5,  # Auto-refresh interval in seconds
        'show_all_containers_default': False,  # Default state for "Show all containers"
        'log_level': 'INFO',  # Logging level
        'docker_socket_path': '',  # Custom Docker socket path (empty = auto-detect)
        'show_success_messages': True,  # Show success message boxes
        'show_logs_window': True,  # Show logs window when using API mode
    }
    
    def __init__(self, settings_file: str = 'config/settings.json'):
        """
        Initialize settings manager
        
        Args:
            settings_file: Path to settings JSON file
        """
        self.settings_file = settings_file
        self.settings: Dict[str, Any] = {}
        
        # Ensure config directory exists
        config_dir = os.path.dirname(settings_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        # Load settings
        self.load()
    
    def load(self):
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Merge with defaults
                self.settings = self.DEFAULT_SETTINGS.copy()
                self.settings.update(loaded_settings)
                
                logger.info(f"Settings loaded from {self.settings_file}")
            else:
                # Use defaults
                self.settings = self.DEFAULT_SETTINGS.copy()
                logger.info("Using default settings")
                
                # Save defaults to file
                self.save()
        
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = self.DEFAULT_SETTINGS.copy()
    
    def save(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Settings saved to {self.settings_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting value
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value
        """
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any, save: bool = True):
        """
        Set setting value
        
        Args:
            key: Setting key
            value: Setting value
            save: Save to file immediately
        """
        self.settings[key] = value
        
        if save:
            self.save()
    
    def update(self, settings_dict: Dict[str, Any], save: bool = True):
        """
        Update multiple settings
        
        Args:
            settings_dict: Dictionary of settings to update
            save: Save to file immediately
        """
        self.settings.update(settings_dict)
        
        if save:
            self.save()
    
    def reset_to_defaults(self, save: bool = True):
        """
        Reset all settings to defaults
        
        Args:
            save: Save to file immediately
        """
        self.settings = self.DEFAULT_SETTINGS.copy()
        
        if save:
            self.save()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        return self.settings.copy()

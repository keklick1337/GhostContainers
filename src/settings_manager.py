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
    
    # Template file in repository
    TEMPLATE_FILE = 'config/settings.json'
    
    # User settings file location
    @staticmethod
    def get_user_settings_path() -> str:
        """Get path to user settings file"""
        if os.name == 'nt':  # Windows
            base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
            data_dir = os.path.join(base_dir, 'ghost-containers')
        else:  # macOS, Linux
            data_dir = os.path.join(
                os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')),
                'ghost-containers'
            )
        
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'settings.json')
    
    def __init__(self):
        """Initialize settings manager"""
        self.template_file = self.TEMPLATE_FILE
        self.settings_file = self.get_user_settings_path()
        self.settings: Dict[str, Any] = {}
        
        # Load settings
        self.load()
    
    def _load_template_settings(self) -> Dict[str, Any]:
        """Load default settings from template file"""
        try:
            if os.path.exists(self.template_file):
                with open(self.template_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load template settings: {e}")
        
        # Fallback defaults if template file missing
        return {
            'language': 'en',
            'launch_mode': 'api',
            'custom_terminal_command': '',
            'theme': 'system',
            'auto_refresh_interval': 5,
            'show_all_containers_default': False,
            'log_level': 'INFO',
            'docker_socket_path': '',
            'show_success_messages': True,
            'show_logs_window': True,
        }
    
    def load(self):
        """Load settings from user file"""
        try:
            default_settings = self._load_template_settings()
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Merge with defaults (user settings override defaults)
                self.settings = default_settings.copy()
                self.settings.update(loaded_settings)
                
                logger.info(f"Settings loaded from {self.settings_file}")
            else:
                # Use defaults from template
                self.settings = default_settings.copy()
                logger.info(f"Using default settings from {self.template_file}")
                
                # Save defaults to user file
                self.save()
        
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = self._load_template_settings()
    
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
        Reset all settings to defaults from template
        
        Args:
            save: Save to file immediately
        """
        self.settings = self._load_template_settings()
        
        if save:
            self.save()
            logger.info(f"Settings reset to defaults from {self.template_file}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        return self.settings.copy()

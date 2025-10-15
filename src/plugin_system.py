"""
GhostContainers Plugin System
Base classes for creating plugins
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import importlib.util

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Base class for all GhostContainers plugins
    
    Plugins extend functionality of GhostContainers without modifying core code.
    Each plugin must implement required abstract methods.
    """
    
    def __init__(self):
        self.name: str = "Unknown Plugin"
        self.version: str = "1.0.0"
        self.description: str = "No description"
        self.author: str = "Unknown"
        self.enabled: bool = True
        
    @abstractmethod
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """
        Initialize plugin with application context
        
        Args:
            app_context: Dictionary containing app references:
                - docker_manager: DockerManager instance
                - template_manager: TemplateManager instance
                - network_manager: NetworkManager instance
                - database: Database instance
                - config: Application configuration
                
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, str]:
        """
        Get plugin information
        
        Returns:
            Dictionary with plugin metadata
        """
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author
        }
    
    def shutdown(self):
        """Called when plugin is being unloaded"""
        pass


class FileViewerPlugin(BasePlugin):
    """
    Base class for file viewer/editor plugins
    
    File viewer plugins handle displaying and editing files from containers.
    """
    
    @abstractmethod
    def can_handle(self, file_path: str, mime_type: Optional[str] = None) -> bool:
        """
        Check if this plugin can handle the file
        
        Args:
            file_path: Path to file
            mime_type: MIME type if known
            
        Returns:
            True if plugin can handle this file type
        """
        pass
    
    @abstractmethod
    def view_file(self, container_name: str, file_path: str, content: bytes) -> Any:
        """
        Display file content
        
        Args:
            container_name: Name of container
            file_path: Path to file in container
            content: File content as bytes
            
        Returns:
            Widget or window object (framework-dependent)
        """
        pass
    
    def edit_file(self, container_name: str, file_path: str, content: bytes) -> Optional[bytes]:
        """
        Edit file content (optional)
        
        Args:
            container_name: Name of container
            file_path: Path to file in container  
            content: File content as bytes
            
        Returns:
            Modified content if changed, None if cancelled
        """
        return None
        
    def get_priority(self) -> int:
        """
        Get plugin priority for handling files.
        Higher priority plugins are tried first when multiple can handle same file.
        
        Returns:
            Priority (0-100, default 50)
        """
        return 50


class NetworkPlugin(BasePlugin):
    """
    Base class for network-related plugins
    
    Network plugins can extend networking capabilities.
    """
    
    @abstractmethod
    def setup_network(self, network_name: str, options: Dict[str, Any]) -> bool:
        """
        Set up custom network configuration
        
        Args:
            network_name: Name of network
            options: Configuration options
            
        Returns:
            True if successful
        """
        pass


class TemplatePlugin(BasePlugin):
    """
    Base class for custom container template plugins
    
    Template plugins add new container templates dynamically.
    """
    
    @abstractmethod
    def get_templates(self) -> list:
        """
        Get list of templates provided by this plugin
        
        Returns:
            List of template dicts with keys: id, name, description, dockerfile, config
        """
        pass


class UIPlugin(BasePlugin):
    """
    Base class for UI extension plugins
    
    UI plugins add menu items, toolbars, panels to main interface.
    """
    
    @abstractmethod
    def get_menu_items(self) -> list:
        """
        Get menu items to add to main menu
        
        Returns:
            List of menu item dicts with keys: label, callback, icon, shortcut
        """
        pass


class PluginManager:
    """
    Manages plugin loading, initialization, and lifecycle
    """
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.file_viewers: list[FileViewerPlugin] = []
        
    def load_plugins_from_directory(self, plugin_dir: str, app_context: Dict[str, Any]):
        """
        Load all plugins from directory
        
        Args:
            plugin_dir: Directory containing plugin modules
            app_context: Application context to pass to plugins
        """
        import os
        import importlib.util
        
        if not os.path.exists(plugin_dir):
            logger.warning(f"Plugin directory not found: {plugin_dir}")
            return
            
        for filename in os.listdir(plugin_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                plugin_path = os.path.join(plugin_dir, filename)
                self._load_plugin_file(plugin_path, app_context)
                
    def _load_plugin_file(self, plugin_path: str, app_context: Dict[str, Any]):
        """Load a single plugin file"""
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find plugin classes in module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BasePlugin) and 
                        attr != BasePlugin and
                        not attr.__name__.startswith('Base')):
                        
                        # Instantiate plugin
                        plugin = attr()
                        if plugin.initialize(app_context):
                            self.plugins[plugin.name] = plugin
                            
                            # Register file viewers
                            if isinstance(plugin, FileViewerPlugin):
                                self.file_viewers.append(plugin)
                                
                            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
                        else:
                            logger.error(f"Failed to initialize plugin: {attr_name}")
                            
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_path}: {e}")
            
    def get_file_viewer(self, file_path: str, mime_type: Optional[str] = None) -> Optional[FileViewerPlugin]:
        """Find suitable file viewer for file"""
        for viewer in self.file_viewers:
            if viewer.can_handle(file_path, mime_type):
                return viewer
        return None
        
    def shutdown_all(self):
        """Shutdown all plugins"""
        for plugin in self.plugins.values():
            try:
                plugin.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {plugin.name}: {e}")

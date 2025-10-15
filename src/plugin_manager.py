"""
GhostContainers Plugin Manager

Handles plugin discovery, loading, lifecycle management.
"""

import os
import sys
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from src.plugin_system import BasePlugin, FileViewerPlugin, NetworkPlugin, TemplatePlugin, UIPlugin
from src.plugin_api import GUIPlugin, TabPlugin, PluginAPI

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages plugin lifecycle and provides plugin API.
    """
    
    def __init__(self, plugins_dir: str = "plugins"):
        """
        Initialize plugin manager.
        
        Args:
            plugins_dir: Directory containing plugins
        """
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, BasePlugin] = {}
        self.app_context: Optional[Dict[str, Any]] = None
        
        # Plugin API for GUI plugins
        self.plugin_api = PluginAPI()
        
        # Plugin categorization (legacy)
        self.file_viewers: List[FileViewerPlugin] = []
        self.network_plugins: List[NetworkPlugin] = []
        self.template_plugins: List[TemplatePlugin] = []
        self.ui_plugins: List[UIPlugin] = []
        
        # New GUI plugins
        self.gui_plugins: List[GUIPlugin] = []
        self.tab_plugins: List[TabPlugin] = []
        
        logger.info(f"Plugin Manager initialized with plugins directory: {self.plugins_dir}")
        
    def set_app_context(self, context: Dict[str, Any]) -> None:
        """
        Set application context for plugins.
        
        Args:
            context: Application context dict
        """
        self.app_context = context
        logger.info("Application context set for plugin manager")
        
    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in plugins directory.
        
        Returns:
            List of discovered plugin module names
        """
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created plugins directory: {self.plugins_dir}")
            return []
            
        discovered = []
        
        # Look for Python files and packages
        for item in self.plugins_dir.iterdir():
            # Skip __pycache__ and hidden files
            if item.name.startswith('_') or item.name.startswith('.'):
                continue
                
            # Python file
            if item.is_file() and item.suffix == '.py':
                discovered.append(item.stem)
                
            # Python package (directory with __init__.py)
            elif item.is_dir() and (item / '__init__.py').exists():
                discovered.append(item.name)
                
        logger.info(f"Discovered {len(discovered)} potential plugins: {discovered}")
        return discovered
        
    def load_plugin(self, module_name: str) -> Optional[BasePlugin]:
        """
        Load a single plugin module.
        
        Args:
            module_name: Name of plugin module to load
            
        Returns:
            Loaded plugin instance or None if failed
        """
        try:
            # Build module path
            module_path = self.plugins_dir / f"{module_name}.py"
            if not module_path.exists():
                # Try as package
                module_path = self.plugins_dir / module_name / "__init__.py"
                if not module_path.exists():
                    logger.error(f"Plugin module not found: {module_name}")
                    return None
                    
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(
                f"plugins.{module_name}",
                module_path
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load spec for plugin: {module_name}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugins.{module_name}"] = module
            spec.loader.exec_module(module)
            
            # Find plugin class
            # First try explicit 'Plugin' attribute
            plugin_class = None
            if hasattr(module, 'Plugin'):
                plugin_class = getattr(module, 'Plugin')
                if not isinstance(plugin_class, type):
                    plugin_class = None
            
            # Fall back to searching for BasePlugin subclass
            if plugin_class is None:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    try:
                        if (isinstance(attr, type) and 
                            issubclass(attr, BasePlugin) and 
                            attr is not BasePlugin):
                            plugin_class = attr
                            break
                    except TypeError:
                        # issubclass() arg 1 must be a class
                        continue
                    
            if plugin_class is None:
                logger.error(f"No plugin class found in module: {module_name}")
                return None
                
            # Instantiate plugin
            plugin = plugin_class()
            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
            
            return plugin
            
        except Exception as e:
            logger.error(f"Error loading plugin {module_name}: {e}", exc_info=True)
            return None
            
    def load_all_plugins(self) -> int:
        """
        Discover and load all available plugins.
        
        Returns:
            Number of successfully loaded plugins
        """
        discovered = self.discover_plugins()
        loaded_count = 0
        
        for module_name in discovered:
            plugin = self.load_plugin(module_name)
            if plugin:
                self.plugins[module_name] = plugin
                loaded_count += 1
                
        logger.info(f"Loaded {loaded_count}/{len(discovered)} plugins")
        return loaded_count
        
    def initialize_plugins(self) -> int:
        """
        Initialize all loaded plugins with app context.
        
        Returns:
            Number of successfully initialized plugins
        """
        if self.app_context is None:
            logger.error("Cannot initialize plugins: app context not set")
            return 0
            
        initialized_count = 0
        
        for plugin_name, plugin in self.plugins.items():
            try:
                if plugin.initialize(self.app_context):
                    initialized_count += 1
                    
                    # Categorize plugin (legacy)
                    if isinstance(plugin, FileViewerPlugin):
                        self.file_viewers.append(plugin)
                        self.file_viewers.sort(key=lambda p: p.get_priority(), reverse=True)
                        
                    if isinstance(plugin, NetworkPlugin):
                        self.network_plugins.append(plugin)
                        
                    if isinstance(plugin, TemplatePlugin):
                        self.template_plugins.append(plugin)
                        
                    if isinstance(plugin, UIPlugin):
                        self.ui_plugins.append(plugin)
                    
                    # Categorize new GUI plugins
                    if isinstance(plugin, GUIPlugin):
                        self.gui_plugins.append(plugin)
                        self.plugin_api.register_plugin(plugin)
                        
                    if isinstance(plugin, TabPlugin):
                        self.tab_plugins.append(plugin)
                        
                    logger.info(f"Initialized plugin: {plugin.name}")
                else:
                    logger.warning(f"Plugin initialization failed: {plugin.name}")
                    plugin.enabled = False
                    
            except Exception as e:
                logger.error(f"Error initializing plugin {plugin_name}: {e}", exc_info=True)
                plugin.enabled = False
                
        logger.info(f"Initialized {initialized_count}/{len(self.plugins)} plugins")
        self._log_plugin_categories()
        return initialized_count
        
    def _log_plugin_categories(self):
        """Log categorized plugins"""
        logger.info(f"File Viewer Plugins: {len(self.file_viewers)}")
        logger.info(f"Network Plugins: {len(self.network_plugins)}")
        logger.info(f"Template Plugins: {len(self.template_plugins)}")
        logger.info(f"UI Plugins: {len(self.ui_plugins)}")
        logger.info(f"GUI Plugins: {len(self.gui_plugins)}")
        logger.info(f"Tab Plugins: {len(self.tab_plugins)}")
        
    def shutdown_plugins(self) -> None:
        """Shutdown all plugins gracefully"""
        logger.info("Shutting down plugins...")
        
        for plugin_name, plugin in self.plugins.items():
            try:
                plugin.shutdown()
                logger.info(f"Plugin shutdown: {plugin.name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {plugin_name}: {e}")
                
        self.plugins.clear()
        self.file_viewers.clear()
        self.network_plugins.clear()
        self.template_plugins.clear()
        self.ui_plugins.clear()
        self.gui_plugins.clear()
        self.tab_plugins.clear()
        
    def get_file_viewer(self, file_path: str, mime_type: Optional[str] = None) -> Optional[FileViewerPlugin]:
        """
        Find appropriate file viewer plugin for file.
        
        Args:
            file_path: Path to file
            mime_type: Optional MIME type
            
        Returns:
            FileViewerPlugin that can handle file, or None
        """
        for plugin in self.file_viewers:
            if plugin.enabled and plugin.can_handle(file_path, mime_type):
                return plugin
        return None
        
    def get_all_plugins(self) -> List[BasePlugin]:
        """Get list of all loaded plugins"""
        return list(self.plugins.values())
        
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get specific plugin by name"""
        for plugin in self.plugins.values():
            if plugin.name == plugin_name:
                return plugin
        return None
        
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a disabled plugin"""
        plugin = self.get_plugin(plugin_name)
        if plugin and not plugin.enabled:
            plugin.enabled = True
            if self.app_context:
                return plugin.initialize(self.app_context)
        return False
        
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable an enabled plugin"""
        plugin = self.get_plugin(plugin_name)
        if plugin and plugin.enabled:
            plugin.shutdown()
            plugin.enabled = False
            return True
        return False

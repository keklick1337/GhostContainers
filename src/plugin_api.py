"""
Extended Plugin API for GUI Integration
Allows plugins to add tabs, menus, toolbars, and hook into various parts of the application
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable
from PyQt6.QtWidgets import QWidget, QMenu


class PluginHook:
    """Represents a hook point in the application"""
    
    def __init__(self, name: str):
        self.name = name
        self.callbacks: List[Callable] = []
    
    def register(self, callback: Callable):
        """Register a callback for this hook"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
    
    def unregister(self, callback: Callable):
        """Unregister a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def execute(self, *args, **kwargs):
        """Execute all registered callbacks"""
        results = []
        for callback in self.callbacks:
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                import logging
                logging.error(f"Error executing hook {self.name}: {e}")
        return results


class GUIPlugin(ABC):
    """
    Base class for plugins that integrate with the GUI
    
    Plugins can:
    - Add tabs to the main window
    - Add menu items
    - Add context menu items
    - Hook into application events
    - Access application state
    """
    
    def __init__(self):
        self.name: str = "Unknown Plugin"
        self.version: str = "1.0.0"
        self.description: str = "No description"
        self.author: str = "Unknown"
        self.enabled: bool = True
        
        # Application context (set during initialization)
        self.docker_manager = None
        self.file_browser = None
        self.db = None
        self.main_window = None
        self.plugin_api = None
        
        # Plugin UI components
        self.tabs: List[Dict[str, Any]] = []  # List of {widget, title, icon}
        self.menu_items: List[Dict[str, Any]] = []
        self.toolbar_items: List[Dict[str, Any]] = []
        self.context_menu_hooks: Dict[str, List[Callable]] = {}
        self._registered_hooks: Dict[str, Callable] = {}
    
    def register_hook(self, hook_name: str, callback: Callable):
        """Register a callback for a hook"""
        self._registered_hooks[hook_name] = callback
        if self.plugin_api:
            self.plugin_api.add_hook(hook_name, callback)
        
    @abstractmethod
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """
        Initialize plugin with application context
        
        Args:
            app_context: Dictionary containing:
                - docker_manager: DockerManager instance
                - file_browser: FileBrowser instance
                - db: DatabaseManager instance
                - main_window: Main GUI window instance
                - plugin_api: PluginAPI instance for registering hooks
                
        Returns:
            True if initialization successful
        """
        # Store context
        self.docker_manager = app_context.get('docker_manager')
        self.file_browser = app_context.get('file_browser')
        self.db = app_context.get('db')
        self.main_window = app_context.get('main_window')
        self.plugin_api = app_context.get('plugin_api')
        
        return True
    
    def get_info(self) -> Dict[str, str]:
        """Get plugin metadata"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author
        }
    
    def add_tab(self, widget: QWidget, title: str, icon: Optional[str] = None):
        """
        Add a tab to the main window
        
        Args:
            widget: Widget to display in the tab
            title: Tab title
            icon: Optional icon path
        """
        self.tabs.append({
            'widget': widget,
            'title': title,
            'icon': icon
        })
    
    def add_menu_item(self, menu_path: str, title: str, callback: Callable, 
                     icon: Optional[str] = None, shortcut: Optional[str] = None):
        """
        Add a menu item
        
        Args:
            menu_path: Path like "File/Export" or "Tools"
            title: Menu item title
            callback: Function to call when clicked
            icon: Optional icon path
            shortcut: Optional keyboard shortcut
        """
        self.menu_items.append({
            'menu_path': menu_path,
            'title': title,
            'callback': callback,
            'icon': icon,
            'shortcut': shortcut
        })
    
    def add_context_menu_hook(self, context_type: str, callback: Callable):
        """
        Register a context menu hook
        
        Args:
            context_type: Type of context menu ('file', 'container', etc.)
            callback: Function that returns list of menu actions
                     callback(context: Dict) -> List[QAction]
        """
        if hasattr(self, 'context_menu_hooks'):
            if context_type not in self.context_menu_hooks:
                self.context_menu_hooks[context_type] = []
            self.context_menu_hooks[context_type].append(callback)
    
    def shutdown(self):
        """Called when plugin is being unloaded"""
        pass


class TabPlugin(GUIPlugin):
    """
    Simplified base class for plugins that primarily add a single tab
    """
    
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """Initialize plugin with application context"""
        # Call parent initialization
        super().initialize(app_context)
        
        # Store plugin_api reference
        self.plugin_api = app_context.get('plugin_api')
        
        # Register any hooks that were added before initialization
        if self.plugin_api and self._registered_hooks:
            for hook_name, callback in self._registered_hooks.items():
                self.plugin_api.add_hook(hook_name, callback)
        
        return True
    
    @abstractmethod
    def create_tab_widget(self) -> QWidget:
        """
        Create and return the tab widget
        
        Returns:
            QWidget to display in the tab
        """
        pass
    
    @abstractmethod
    def get_tab_title(self) -> str:
        """Get the tab title"""
        pass
    
    def get_tab_icon(self) -> Optional[str]:
        """Get optional tab icon"""
        return None
    
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """Initialize and create tab"""
        if not super().initialize(app_context):
            return False
        
        # Create and add tab
        try:
            widget = self.create_tab_widget()
            title = self.get_tab_title()
            icon = self.get_tab_icon()
            
            self.add_tab(widget, title, icon)
            return True
            
        except Exception as e:
            import logging
            logging.error(f"Error creating tab for {self.name}: {e}")
            return False
    
    def on_tab_activated(self):
        """Called when tab becomes active"""
        pass
    
    def on_tab_deactivated(self):
        """Called when tab becomes inactive"""
        pass
    
    def refresh(self):
        """Refresh tab content"""
        pass


class PluginAPI:
    """
    API for managing plugins and hooks
    Provides centralized hook management and plugin coordination
    """
    
    def __init__(self):
        self.hooks: Dict[str, PluginHook] = {}
        self.plugins: List[GUIPlugin] = []
    
    def register_hook(self, hook_name: str) -> PluginHook:
        """Register a new hook point"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = PluginHook(hook_name)
        return self.hooks[hook_name]
    
    def get_hook(self, hook_name: str) -> Optional[PluginHook]:
        """Get a hook by name"""
        return self.hooks.get(hook_name)
    
    def execute_hook(self, hook_name: str, *args, **kwargs):
        """Execute all callbacks registered to a hook"""
        hook = self.get_hook(hook_name)
        if hook:
            return hook.execute(*args, **kwargs)
        return []
    
    def register_plugin(self, plugin: GUIPlugin):
        """Register a plugin"""
        if plugin not in self.plugins:
            self.plugins.append(plugin)
    
    def get_plugins(self) -> List[GUIPlugin]:
        """Get all registered plugins"""
        return self.plugins
    
    def get_plugins_by_type(self, plugin_class) -> List[GUIPlugin]:
        """Get plugins of a specific type"""
        return [p for p in self.plugins if isinstance(p, plugin_class)]


# Standard hook names
HOOK_CONTAINER_SELECTED = "container_selected"
HOOK_CONTAINER_STARTED = "container_started"
HOOK_CONTAINER_STOPPED = "container_stopped"
HOOK_CONTAINER_CREATED = "container_created"
HOOK_CONTAINER_REMOVED = "container_removed"
HOOK_FILE_CONTEXT_MENU = "file_context_menu"
HOOK_CONTAINER_CONTEXT_MENU = "container_context_menu"
HOOK_APPLICATION_STARTUP = "application_startup"
HOOK_APPLICATION_SHUTDOWN = "application_shutdown"

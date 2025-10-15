"""
File Browser Plugin Package
"""

from .plugin import FileBrowserPlugin

# Export as Plugin for plugin manager
Plugin = FileBrowserPlugin

__all__ = ['Plugin', 'FileBrowserPlugin']

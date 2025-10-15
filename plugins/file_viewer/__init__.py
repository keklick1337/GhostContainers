"""
File Viewer Plugin
"""

from .plugin import FileViewerPlugin

# Make plugin discoverable by plugin manager
Plugin = FileViewerPlugin

__all__ = ['FileViewerPlugin', 'Plugin']

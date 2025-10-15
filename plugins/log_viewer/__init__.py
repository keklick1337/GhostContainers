"""
Log Viewer Plugin
"""

from .plugin import LogViewerPlugin

# Make plugin discoverable by plugin manager
Plugin = LogViewerPlugin

__all__ = ['LogViewerPlugin', 'Plugin']

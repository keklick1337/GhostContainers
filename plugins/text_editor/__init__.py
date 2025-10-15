"""
Text Editor Plugin for GhostContainers
Provides text editing capabilities for files in containers
"""

from .plugin import TextEditorPlugin

# Make plugin discoverable by plugin manager
Plugin = TextEditorPlugin

__version__ = "1.0.0"
__all__ = ['TextEditorPlugin', 'Plugin']

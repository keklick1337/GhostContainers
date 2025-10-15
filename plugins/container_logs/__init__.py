"""
Container Logs Plugin Package
"""

from .plugin import ContainerLogsPlugin

# Export as Plugin for plugin manager
Plugin = ContainerLogsPlugin

__all__ = ['Plugin', 'ContainerLogsPlugin']

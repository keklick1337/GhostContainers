"""
Image Manager Plugin
Manage ghostcontainers images
"""

from .plugin import ImageManagerPlugin

# Make plugin discoverable by plugin manager
Plugin = ImageManagerPlugin

__all__ = ['ImageManagerPlugin', 'Plugin']

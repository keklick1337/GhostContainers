"""
Custom Docker API - Pure Python implementation without external dependencies
Works with Docker daemon via Unix socket (Linux/macOS)
"""

from .client import DockerClient
from .exceptions import (
    DockerException,
    ImageNotFound,
    ContainerNotFound,
    APIError
)

__all__ = [
    'DockerClient',
    'DockerException',
    'ImageNotFound',
    'ContainerNotFound',
    'APIError'
]

__version__ = '1.0.0'

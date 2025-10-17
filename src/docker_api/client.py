"""
Docker Client - Main API entry point
"""

from typing import Optional
from .http_client import DockerHTTPClient
from .images import ImageCollection
from .containers import ContainerCollection
from .networks import NetworkCollection


class DockerClient:
    """
    Docker API Client
    Pure Python implementation without external dependencies
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 60):
        """
        Initialize Docker client
        
        Args:
            base_url: Docker socket path (default: auto-detect)
            timeout: Request timeout in seconds
        """
        self.http = DockerHTTPClient(base_url=base_url, timeout=timeout)
        self.images = ImageCollection(self)
        self.containers = ContainerCollection(self)
        self.networks = NetworkCollection(self)
    
    def version(self) -> dict:
        """Get Docker version info"""
        return self.http.get('/version')
    
    def info(self) -> dict:
        """Get Docker system info"""
        return self.http.get('/info')
    
    def ping(self) -> str:
        """Ping Docker daemon"""
        return self.http.get('/_ping')
    
    def close(self):
        """Close client (no-op for compatibility)"""
        pass

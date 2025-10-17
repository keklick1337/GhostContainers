"""
HTTP Client for Docker Unix Socket
Pure Python implementation using http.client and socket
"""

import socket
import http.client
import json
import platform
import os
from typing import Optional, Dict, Any
from urllib.parse import quote


class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP connection over Unix socket"""
    
    def __init__(self, socket_path: str, timeout: int = 60):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = socket_path
    
    def connect(self):
        """Connect to Unix socket"""
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class DockerHTTPClient:
    """HTTP client for Docker daemon"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 60):
        """
        Initialize Docker HTTP client
        
        Args:
            base_url: Docker socket path (default: auto-detect)
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        
        # Auto-detect Docker socket
        if base_url is None:
            system = platform.system()
            if system == "Darwin":  # macOS
                self.socket_path = os.path.expanduser('~/.docker/run/docker.sock')
                # Fallback to default Unix socket
                if not os.path.exists(self.socket_path):
                    self.socket_path = '/var/run/docker.sock'
            else:  # Linux
                self.socket_path = '/var/run/docker.sock'
        else:
            # Remove unix:// prefix if present
            self.socket_path = base_url.replace('unix://', '')
        
        if not os.path.exists(self.socket_path):
            raise FileNotFoundError(f"Docker socket not found: {self.socket_path}")
    
    def request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None,
                params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                stream: bool = False) -> Any:
        """
        Make HTTP request to Docker daemon
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API path
            data: JSON data for request body, or raw bytes
            params: URL query parameters
            headers: HTTP headers
            stream: If True, return response object for streaming
            
        Returns:
            Parsed JSON response or response object if stream=True
        """
        # Build URL with query params
        url = path
        if params:
            query_parts = []
            for key, value in params.items():
                if isinstance(value, bool):
                    value = 'true' if value else 'false'
                elif isinstance(value, (list, dict)):
                    value = json.dumps(value)
                query_parts.append(f"{key}={quote(str(value))}")
            if query_parts:
                url = f"{path}?{'&'.join(query_parts)}"
        
        # Prepare headers
        req_headers = {'Host': 'localhost'}
        if headers:
            req_headers.update(headers)
        
        # Prepare body
        body = None
        if data is not None:
            if isinstance(data, bytes):
                # Raw bytes data (e.g., tar archive)
                body = data
                if 'Content-Length' not in req_headers:
                    req_headers['Content-Length'] = str(len(body))
            else:
                # JSON data
                body = json.dumps(data).encode('utf-8')
                req_headers['Content-Type'] = 'application/json'
                req_headers['Content-Length'] = str(len(body))
        
        # Make request
        conn = UnixHTTPConnection(self.socket_path, timeout=self.timeout)
        try:
            conn.request(method, url, body=body, headers=req_headers)
            response = conn.getresponse()
            
            # Check status code
            if response.status >= 400:
                error_body = response.read().decode('utf-8')
                try:
                    error_data = json.loads(error_body)
                    error_msg = error_data.get('message', error_body)
                except:
                    error_msg = error_body
                
                from .exceptions import APIError
                raise APIError(
                    f"Docker API error: {error_msg}",
                    response=response,
                    status_code=response.status
                )
            
            # Stream response - DON'T close connection yet
            if stream:
                # Return response without closing connection
                # Caller is responsible for reading and closing
                return response
            
            # Parse JSON response
            response_data = response.read()
            if not response_data:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(response_data.decode('utf-8'))
            except json.JSONDecodeError:
                # Return raw data if not JSON
                return response_data.decode('utf-8')
        
        finally:
            # Only close if not streaming
            if not stream:
                conn.close()
    
    def get(self, path: str, **kwargs) -> Any:
        """Make GET request"""
        return self.request('GET', path, **kwargs)
    
    def post(self, path: str, **kwargs) -> Any:
        """Make POST request"""
        return self.request('POST', path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> Any:
        """Make DELETE request"""
        return self.request('DELETE', path, **kwargs)
    
    def put(self, path: str, **kwargs) -> Any:
        """Make PUT request"""
        return self.request('PUT', path, **kwargs)

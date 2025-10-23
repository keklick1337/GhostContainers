"""
Docker Containers API
"""

from typing import List, Dict, Any, Optional
from .exceptions import ContainerNotFound


class Container:
    """Docker Container object"""
    
    def __init__(self, attrs: Dict[str, Any], client):
        self.attrs = attrs
        self.client = client
        self.id = attrs.get('Id', '')
        self.short_id = self.id[:12] if self.id else ''
        self.name = attrs.get('Name', attrs.get('Names', [''])[0] if attrs.get('Names') else '').lstrip('/')
        
        # Handle different status formats
        state = attrs.get('State', {})
        if isinstance(state, dict):
            self.status = state.get('Status', 'unknown')
        else:
            self.status = attrs.get('Status', state if isinstance(state, str) else 'unknown')
        
        self.image = attrs.get('Image', attrs.get('ImageID', ''))
        self.labels = attrs.get('Labels', {})
        self.ports = attrs.get('Ports', {})
    
    def __repr__(self):
        return f"<Container: {self.name or self.short_id}>"
    
    def start(self):
        """Start this container"""
        return self.client.start(self.id)
    
    def stop(self, timeout: int = 10):
        """Stop this container"""
        return self.client.stop(self.id, timeout=timeout)
    
    def restart(self, timeout: int = 10):
        """Restart this container"""
        return self.client.restart(self.id, timeout=timeout)
    
    def remove(self, force: bool = False, v: bool = False):
        """Remove this container"""
        return self.client.remove(self.id, force=force, v=v)
    
    def kill(self, signal: str = 'SIGKILL'):
        """Kill this container"""
        return self.client.kill(self.id, signal=signal)
    
    def exec_run(self, cmd: str, stdout: bool = True, stderr: bool = True,
                 stdin: bool = False, tty: bool = False, privileged: bool = False,
                 user: str = '', environment: Optional[Dict[str, str]] = None,
                 workdir: str = '', detach: bool = False):
        """Execute command in container"""
        return self.client.exec_run(
            self.id, cmd, stdout=stdout, stderr=stderr, stdin=stdin,
            tty=tty, privileged=privileged, user=user, environment=environment,
            workdir=workdir, detach=detach
        )
    
    def logs(self, stdout: bool = True, stderr: bool = True, stream: bool = False,
             timestamps: bool = False, tail: str = 'all', since: Optional[int] = None,
             follow: bool = False):
        """Get container logs"""
        return self.client.logs(
            self.id, stdout=stdout, stderr=stderr, stream=stream,
            timestamps=timestamps, tail=tail, since=since, follow=follow
        )
    
    def put_archive(self, path: str, data: bytes):
        """Upload tar archive to container"""
        return self.client.put_archive(self.id, path, data)
    
    def get_archive(self, path: str) -> bytes:
        """Download path from container as tar archive"""
        return self.client.get_archive(self.id, path)


class ContainerCollection:
    """Docker Containers collection"""
    
    def __init__(self, client):
        self.client = client
    
    def list(self, all: bool = False, limit: Optional[int] = None,
             filters: Optional[Dict[str, Any]] = None) -> List[Container]:
        """
        List containers
        
        Args:
            all: Show all containers (including stopped)
            limit: Maximum number of containers to return
            filters: Filters to apply
            
        Returns:
            List of Container objects
        """
        params = {'all': all}
        if limit:
            params['limit'] = limit
        if filters:
            params['filters'] = filters
        
        containers_data = self.client.http.get('/containers/json', params=params)
        return [Container(c_data, self) for c_data in containers_data]
    
    def get(self, container_id: str) -> Container:
        """
        Get container by ID or name
        
        Args:
            container_id: Container ID or name
            
        Returns:
            Container object
            
        Raises:
            ContainerNotFound: If container not found
        """
        try:
            container_data = self.client.http.get(f'/containers/{container_id}/json')
            return Container(container_data, self)
        except Exception as e:
            raise ContainerNotFound(f"Container not found: {container_id}") from e
    
    def create(self, image: str, name: Optional[str] = None,
               command: Optional[str] = None, environment: Optional[Dict[str, str]] = None,
               volumes: Optional[Dict[str, Dict[str, str]]] = None,
               ports: Optional[Dict[str, int]] = None, detach: bool = True,
               stdin_open: bool = False, tty: bool = False,
               network_mode: Optional[str] = None, hostname: Optional[str] = None,
               auto_remove: bool = False, platform: Optional[str] = None,
               **kwargs) -> Container:
        """
        Create container
        
        Args:
            image: Image name or ID
            name: Container name
            command: Command to run
            environment: Environment variables
            volumes: Volume mounts {host_path: {'bind': container_path, 'mode': 'rw'}}
            ports: Port bindings
            detach: Run in background
            stdin_open: Keep STDIN open
            tty: Allocate TTY
            network_mode: Network mode
            hostname: Container hostname
            auto_remove: Auto-remove when stopped
            platform: Platform (e.g., linux/amd64)
            **kwargs: Additional parameters
            
        Returns:
            Container object
        """
        # Build config
        config = {
            'Image': image,
            'Tty': tty,
            'OpenStdin': stdin_open,
            'StdinOnce': False,
            'AttachStdin': stdin_open,
            'AttachStdout': True,
            'AttachStderr': True,
        }
        
        if command:
            if isinstance(command, str):
                config['Cmd'] = ['sh', '-c', command]
            else:
                config['Cmd'] = command
        
        if environment:
            config['Env'] = [f"{k}={v}" for k, v in environment.items()]
        
        if hostname:
            config['Hostname'] = hostname
        
        # Host config
        host_config = {}
        
        if auto_remove:
            host_config['AutoRemove'] = auto_remove
        
        if network_mode:
            host_config['NetworkMode'] = network_mode
        
        if volumes:
            binds = []
            for host_path, mount_info in volumes.items():
                container_path = mount_info.get('bind', '')
                mode = mount_info.get('mode', 'rw')
                binds.append(f"{host_path}:{container_path}:{mode}")
            host_config['Binds'] = binds
        
        if ports:
            port_bindings = {}
            exposed_ports = {}
            for container_port, host_port in ports.items():
                port_key = f"{container_port}/tcp"
                exposed_ports[port_key] = {}
                port_bindings[port_key] = [{'HostPort': str(host_port)}]
            config['ExposedPorts'] = exposed_ports
            host_config['PortBindings'] = port_bindings
        
        if host_config:
            config['HostConfig'] = host_config
        
        # Merge additional kwargs
        config.update(kwargs)
        
        # Create container
        params = {}
        if name:
            params['name'] = name
        if platform:
            params['platform'] = platform
        
        result = self.client.http.post('/containers/create', params=params, data=config)
        container_id = result.get('Id')
        
        return self.get(container_id)
    
    def run(self, image: str, command: Optional[str] = None, **kwargs) -> Container:
        """
        Create and start container
        
        Args:
            image: Image name
            command: Command to run
            **kwargs: Additional create parameters
            
        Returns:
            Container object
        """
        container = self.create(image, command=command, **kwargs)
        container.start()
        return container
    
    def start(self, container_id: str):
        """Start container"""
        return self.client.http.post(f'/containers/{container_id}/start')
    
    def stop(self, container_id: str, timeout: int = 10):
        """Stop container"""
        params = {'t': timeout}
        return self.client.http.post(f'/containers/{container_id}/stop', params=params)
    
    def restart(self, container_id: str, timeout: int = 10):
        """Restart container"""
        params = {'t': timeout}
        return self.client.http.post(f'/containers/{container_id}/restart', params=params)
    
    def remove(self, container_id: str, force: bool = False, v: bool = False):
        """Remove container"""
        params = {'force': force, 'v': v}
        return self.client.http.delete(f'/containers/{container_id}', params=params)
    
    def kill(self, container_id: str, signal: str = 'SIGKILL'):
        """Kill container"""
        params = {'signal': signal}
        return self.client.http.post(f'/containers/{container_id}/kill', params=params)
    
    def exec_run(self, container_id: str, cmd: str, stdout: bool = True,
                 stderr: bool = True, stdin: bool = False, tty: bool = False,
                 privileged: bool = False, user: str = '',
                 environment: Optional[Dict[str, str]] = None,
                 workdir: str = '', detach: bool = False):
        """
        Execute command in running container
        
        Args:
            container_id: Container ID
            cmd: Command to execute
            stdout: Attach to stdout
            stderr: Attach to stderr
            stdin: Attach to stdin
            tty: Allocate TTY
            privileged: Run as privileged
            user: User to run as
            environment: Environment variables
            workdir: Working directory
            detach: Run in background
            
        Returns:
            Execution result
        """
        # Create exec instance
        exec_config = {
            'AttachStdout': stdout,
            'AttachStderr': stderr,
            'AttachStdin': stdin,
            'Tty': tty,
            'Privileged': privileged,
            'Cmd': cmd if isinstance(cmd, list) else ['sh', '-c', cmd],
        }
        
        if user:
            exec_config['User'] = user
        if environment:
            exec_config['Env'] = [f"{k}={v}" for k, v in environment.items()]
        if workdir:
            exec_config['WorkingDir'] = workdir
        
        exec_result = self.client.http.post(
            f'/containers/{container_id}/exec',
            data=exec_config
        )
        exec_id = exec_result.get('Id')
        
        # Start exec
        start_config = {'Detach': detach, 'Tty': tty}
        return self.client.http.post(f'/exec/{exec_id}/start', data=start_config)
    
    def logs(self, container_id: str, stdout: bool = True, stderr: bool = True,
             stream: bool = False, timestamps: bool = False, tail: str = 'all',
             since: Optional[int] = None, follow: bool = False):
        """
        Get container logs
        
        Args:
            container_id: Container ID
            stdout: Return stdout stream
            stderr: Return stderr stream
            stream: Stream logs
            timestamps: Show timestamps
            tail: Number of lines to show from end ('all' for all)
            since: Show logs since timestamp (Unix epoch)
            follow: Follow log output
            
        Returns:
            Log output (string if not stream, response object if stream)
        """
        params = {
            'stdout': stdout,
            'stderr': stderr,
            'timestamps': timestamps,
            'tail': tail,
            'follow': follow
        }
        if since:
            params['since'] = since
        
        return self.client.http.get(
            f'/containers/{container_id}/logs',
            params=params,
            stream=stream
        )
    
    def put_archive(self, container_id: str, path: str, data: bytes):
        """
        Upload tar archive to container
        
        Args:
            container_id: Container ID
            path: Path in container where to extract archive
            data: Tar archive as bytes
            
        Returns:
            True if successful
        """
        params = {'path': path}
        self.client.http.put(
            f'/containers/{container_id}/archive',
            params=params,
            data=data
        )
        return True
    
    def get_archive(self, container_id: str, path: str) -> bytes:
        """
        Download path from container as tar archive
        
        Args:
            container_id: Container ID
            path: Path in container to download
            
        Returns:
            Tar archive as bytes
        """
        params = {'path': path}
        return self.client.http.get(
            f'/containers/{container_id}/archive',
            params=params,
            stream=False
        )

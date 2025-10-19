"""
Network Manager - network settings management Docker
"""

import logging
from typing import List, Dict, Optional
from .docker_api.exceptions import APIError, NetworkNotFound

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetworkManager:
    """Docker network management"""
    
    def __init__(self, docker_client):
        """
        Initialize manager of networks
        
        Args:
            docker_client: Docker client
        """
        self.client = docker_client
    
    def list_networks(self) -> List[Dict[str, str]]:
        """
        Get list of Docker networks
        
        Returns:
            List of networks
        """
        try:
            networks = self.client.networks.list()
            result = []
            
            for network in networks:
                result.append({
                    'id': network.id[:12],
                    'name': network.name,
                    'driver': network.attrs.get('Driver', 'unknown'),
                    'scope': network.attrs.get('Scope', 'local'),
                    'containers': len(network.attrs.get('Containers', {}))
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting network list: {e}")
            return []
    
    def create_network(
        self,
        name: str,
        driver: str = 'bridge',
        internal: bool = False,
        **kwargs
    ) -> Optional[str]:
        """
        Create Docker network
        
        Args:
            name: Network name
            driver: Network driver (bridge, host, overlay, macvlan)
            internal: Isolated network (without internet access)
            **kwargs: Additional parameters
            
        Returns:
            Network ID or None
        """
        try:
            network = self.client.networks.create(
                name=name,
                driver=driver,
                internal=internal,
                **kwargs
            )
            logger.info(f"Network {name} created: {network.id[:12]}")
            return network.id
        except APIError as e:
            logger.error(f"Error creating network {name}: {e}")
            return None
    
    def remove_network(self, name: str) -> bool:
        """
        Remove network
        
        Args:
            name: Network name
            
        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(name)
            network.remove()
            logger.info(f"Network {name} removed")
            return True
        except NetworkNotFound:
            logger.error(f"Network {name} not found")
            return False
        except APIError as e:
            logger.error(f"Error removing network {name}: {e}")
            return False
    
    def connect_container(self, network_name: str, container_name: str) -> bool:
        """
        Connect container to network
        
        Args:
            network_name: Network name
            container_name: Container name
            
        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_name)
            network.connect(container_name)
            logger.info(f"Container {container_name} connected to network {network_name}")
            return True
        except NetworkNotFound as e:
            logger.error(f"Network or container not found: {e}")
            return False
        except APIError as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def disconnect_container(self, network_name: str, container_name: str) -> bool:
        """
        Disconnect container from network
        
        Args:
            network_name: Network name
            container_name: Container name
            
        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_name)
            network.disconnect(container_name)
            logger.info(f"Container {container_name} disconnected from network {network_name}")
            return True
        except NetworkNotFound as e:
            logger.error(f"Network or container not found: {e}")
            return False
        except APIError as e:
            logger.error(f"Disconnection error: {e}")
            return False
    
    def create_isolated_network(self, name: str) -> Optional[str]:
        """
        Create isolated network (without internet access)
        
        Args:
            name: Network name
            
        Returns:
            Network ID or None
        """
        return self.create_network(name=name, driver='bridge', internal=True)
    
    def create_whonix_network(self, gateway_container: str) -> Optional[str]:
        """
        Create network for Whonix (routing through Tor gateway)
        
        Args:
            gateway_container: Container name Whonix Gateway
            
        Returns:
            Network ID or None
        """
        network_name = f"whonix-{gateway_container}"
        
        # Creating network
        network_id = self.create_network(
            name=network_name,
            driver='bridge',
            internal=False  # Gateway needs internet access
        )
        
        if network_id:
            # Connecting gateway to this network
            self.connect_container(network_name, gateway_container)
            logger.info(f"Whonix network {network_name} created with gateway {gateway_container}")
        
        return network_id
    
    def get_network_info(self, name: str) -> Optional[Dict]:
        """
        Get network information
        
        Args:
            name: Network name
            
        Returns:
            Dict with information or None
        """
        try:
            network = self.client.networks.get(name)
            return {
                'id': network.id[:12],
                'name': network.name,
                'driver': network.attrs.get('Driver'),
                'scope': network.attrs.get('Scope'),
                'internal': network.attrs.get('Internal', False),
                'ipam': network.attrs.get('IPAM'),
                'containers': network.attrs.get('Containers', {})
            }
        except NetworkNotFound:
            logger.error(f"Network {name} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting network information {name}: {e}")
            return None
    
    def setup_shared_network(self, containers: List[str]) -> Optional[str]:
        """
        Create common network for container group
        
        Args:
            containers: List of container names
            
        Returns:
            Network ID or None
        """
        if not containers:
            return None
        
        network_name = f"shared-{'-'.join(containers[:3])}"
        
        # Creating network
        network_id = self.create_network(
            name=network_name,
            driver='bridge'
        )
        
        if network_id:
            # Connecting all containers
            for container in containers:
                self.connect_container(network_name, container)
            
            logger.info(f"Common network {network_name} created for {len(containers)} containers")
        
        return network_id

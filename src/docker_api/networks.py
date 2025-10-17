"""
Docker Networks API
"""

from typing import List, Dict, Optional, Any
from .exceptions import APIError, DockerException


class Network:
    """Docker Network object"""
    
    def __init__(self, client, attrs: dict):
        self.client = client
        self.attrs = attrs
        self.id = attrs.get('Id', '')
        self.name = attrs.get('Name', '')
    
    def reload(self):
        """Reload network data"""
        data = self.client.http.get(f'/networks/{self.id}')
        self.attrs = data
        return self
    
    def remove(self):
        """Remove network"""
        self.client.http.delete(f'/networks/{self.id}')


class NetworkCollection:
    """Docker Networks Collection"""
    
    def __init__(self, client):
        self.client = client
    
    def list(self, **kwargs) -> List[Network]:
        """
        List networks
        
        Args:
            filters: dict of filters (e.g., {'name': 'mynet'})
        
        Returns:
            List of Network objects
        """
        try:
            params = {}
            if 'filters' in kwargs:
                import json
                params['filters'] = json.dumps(kwargs['filters'])
            
            data = self.client.http.get('/networks', params=params)
            return [Network(self.client, net) for net in data]
        except Exception as e:
            raise APIError(f"Failed to list networks: {e}")
    
    def get(self, network_id: str) -> Network:
        """
        Get network by ID or name
        
        Args:
            network_id: Network ID or name
        
        Returns:
            Network object
        """
        try:
            data = self.client.http.get(f'/networks/{network_id}')
            return Network(self.client, data)
        except Exception as e:
            raise APIError(f"Failed to get network {network_id}: {e}")
    
    def create(self, name: str, **kwargs) -> Network:
        """
        Create network
        
        Args:
            name: Network name
            driver: Network driver (default: bridge)
            internal: Internal network (default: False)
            attachable: Attachable (default: True)
            options: Driver options dict
            labels: Labels dict
        
        Returns:
            Network object
        """
        try:
            data = {
                'Name': name,
                'Driver': kwargs.get('driver', 'bridge'),
                'Internal': kwargs.get('internal', False),
                'Attachable': kwargs.get('attachable', True),
                'CheckDuplicate': True
            }
            
            if 'options' in kwargs:
                data['Options'] = kwargs['options']
            
            if 'labels' in kwargs:
                data['Labels'] = kwargs['labels']
            
            if 'ipam' in kwargs:
                data['IPAM'] = kwargs['ipam']
            
            result = self.client.http.post('/networks/create', json=data)
            return self.get(result['Id'])
        except Exception as e:
            raise APIError(f"Failed to create network {name}: {e}")
    
    def prune(self, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Remove unused networks
        
        Args:
            filters: Filters to use
        
        Returns:
            Dict with deleted networks info
        """
        try:
            params = {}
            if filters:
                import json
                params['filters'] = json.dumps(filters)
            
            return self.client.http.post('/networks/prune', params=params)
        except Exception as e:
            raise APIError(f"Failed to prune networks: {e}")

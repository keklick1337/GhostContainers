"""
Docker Images API
"""

import json
import tarfile
import io
import os
from typing import List, Dict, Any, Optional, Callable
from .exceptions import ImageNotFound, BuildError


class Image:
    """Docker Image object"""
    
    def __init__(self, attrs: Dict[str, Any], client):
        self.attrs = attrs
        self.client = client
        self.id = attrs.get('Id', '')
        self.short_id = self.id[:12] if self.id else ''
        self.tags = attrs.get('RepoTags', [])
    
    def __repr__(self):
        return f"<Image: {self.tags[0] if self.tags else self.short_id}>"
    
    def remove(self, force: bool = False, noprune: bool = False):
        """Remove this image"""
        return self.client.remove(self.id, force=force, noprune=noprune)


class ImageCollection:
    """Docker Images collection"""
    
    def __init__(self, client):
        self.client = client
    
    def list(self, name: Optional[str] = None, all: bool = False,
             filters: Optional[Dict[str, Any]] = None) -> List[Image]:
        """
        List images
        
        Args:
            name: Filter by image name
            all: Show all images (including intermediates)
            filters: Filters to apply
            
        Returns:
            List of Image objects
        """
        params = {'all': all}
        if filters:
            params['filters'] = filters
        
        images_data = self.client.http.get('/images/json', params=params)
        images = [Image(img_data, self) for img_data in images_data]
        
        # Filter by name if specified
        if name:
            images = [img for img in images if any(name in tag for tag in img.tags)]
        
        return images
    
    def get(self, name: str) -> Image:
        """
        Get image by name or ID
        
        Args:
            name: Image name or ID
            
        Returns:
            Image object
            
        Raises:
            ImageNotFound: If image not found
        """
        try:
            image_data = self.client.http.get(f'/images/{name}/json')
            return Image(image_data, self)
        except Exception as e:
            raise ImageNotFound(f"Image not found: {name}") from e
    
    def pull(self, repository: str, tag: str = 'latest', 
             platform: Optional[str] = None) -> Image:
        """
        Pull image from registry
        
        Args:
            repository: Repository name
            tag: Image tag
            platform: Platform (e.g., linux/amd64)
            
        Returns:
            Image object
        """
        params = {'fromImage': repository, 'tag': tag}
        if platform:
            params['platform'] = platform
        
        # Stream pull progress
        response = self.client.http.post('/images/create', params=params, stream=True)
        
        # Read all progress lines
        for line in response:
            if line:
                pass  # Could parse progress here
        
        # Get the pulled image
        full_name = f"{repository}:{tag}"
        return self.get(full_name)
    
    def build(self, path: str, tag: Optional[str] = None,
              dockerfile: str = 'Dockerfile', buildargs: Optional[Dict[str, str]] = None,
              platform: Optional[str] = None, rm: bool = True,
              callback: Optional[Callable[[str], None]] = None) -> Image:
        """
        Build image from Dockerfile
        
        Args:
            path: Build context path
            tag: Tag for the image
            dockerfile: Dockerfile name
            buildargs: Build arguments
            platform: Target platform
            rm: Remove intermediate containers
            callback: Callback for build output
            
        Returns:
            Built Image object
        """
        # Create tar archive of build context
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            # Add all files from path
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, path)
                    tar.add(file_path, arcname=arcname)
        
        tar_data = tar_stream.getvalue()
        
        # Prepare build params
        params = {'dockerfile': dockerfile, 'rm': rm}
        if tag:
            params['t'] = tag
        if buildargs:
            params['buildargs'] = buildargs
        if platform:
            params['platform'] = platform
        
        headers = {'Content-Type': 'application/x-tar'}
        
        # Start build
        try:
            response = self.client.http.request(
                'POST', '/build', 
                params=params,
                headers=headers,
                data=tar_data,
                stream=True
            )
            
            # Process build output
            # Response is http.client.HTTPResponse - read line by line
            image_id = None
            build_successful = False
            
            while True:
                line = response.readline()
                if not line:
                    break
                
                try:
                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue
                    
                    # Parse JSON line
                    data = json.loads(line_str)
                    
                    # Extract stream output
                    if 'stream' in data:
                        msg = data['stream'].strip()
                        if callback and msg:
                            callback(msg)
                        # Check for successful completion message
                        if 'Successfully built' in msg or 'Successfully tagged' in msg:
                            build_successful = True
                    
                    # Check for errors
                    if 'error' in data:
                        error_msg = data['error']
                        if 'errorDetail' in data:
                            error_msg = data['errorDetail'].get('message', error_msg)
                        raise BuildError(f"Build failed: {error_msg}")
                    
                    # Extract image ID from successful build
                    if 'aux' in data and 'ID' in data['aux']:
                        image_id = data['aux']['ID']
                        build_successful = True
                
                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    if callback:
                        callback(line.decode('utf-8', errors='ignore').strip())
            
            # If build was successful, return success
            # Don't try to get the image immediately as it might not be queryable yet
            if build_successful or image_id:
                # Return a dummy image object representing the built image
                return Image({
                    'Id': image_id or f'sha256:{tag}',
                    'RepoTags': [tag] if tag else [],
                    'Size': 0,
                    'Created': '',
                    'Architecture': 'unknown'
                }, self)
            
            # Build completed but no success indicator found
            raise BuildError("Build completed but no success confirmation received")
        
        except Exception as e:
            if isinstance(e, BuildError):
                raise
            raise BuildError(f"Build failed: {str(e)}") from e
    
    def remove(self, image: str, force: bool = False, noprune: bool = False):
        """
        Remove image
        
        Args:
            image: Image name or ID
            force: Force removal
            noprune: Don't delete untagged parents
        """
        params = {'force': force, 'noprune': noprune}
        return self.client.http.delete(f'/images/{image}', params=params)

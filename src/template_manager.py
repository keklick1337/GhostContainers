"""
Template Manager - template management Dockerfile
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemplateManager:
    """Container template management"""
    
    def __init__(self, templates_dir: str = "templates"):
        """
        Initialize template manager
        
        Args:
            templates_dir: Path to templates directory
        """
        self.templates_dir = templates_dir
        self._ensure_templates_dir()
    
    def _ensure_templates_dir(self):
        """Create templates directory if not exists"""
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
            logger.info(f"Created templates directory: {self.templates_dir}")
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of available templates
        
        Returns:
            List of templates with metadata
        """
        templates = []
        
        if not os.path.exists(self.templates_dir):
            return templates
        
        for item in os.listdir(self.templates_dir):
            template_path = os.path.join(self.templates_dir, item)
            
            # Check if it is a directory
            if not os.path.isdir(template_path):
                continue
            
            # Check for Dockerfile
            dockerfile_path = os.path.join(template_path, 'Dockerfile')
            if not os.path.exists(dockerfile_path):
                continue
            
            # Read configuration
            config_path = os.path.join(template_path, 'config.json')
            config = self._read_config(config_path)
            
            templates.append({
                'id': item,
                'name': config.get('name', item),
                'description': config.get('description', 'No description'),
                'path': template_path,
                'dockerfile': dockerfile_path,
                'config': config
            })
        
        return templates
    
    def _read_config(self, config_path: str) -> Dict:
        """
        Read template configuration
        
        Args:
            config_path: Path to config.json
            
        Returns:
            Dict with configuration
        """
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Read error {config_path}: {e}")
        
        return {}
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """
        Get template by ID
        
        Args:
            template_id: Template ID
            
        Returns:
            Dict with template data or None
        """
        templates = self.list_templates()
        for template in templates:
            if template['id'] == template_id:
                return template
        return None
    
    def get_dockerfile_content(self, template_id: str) -> Optional[str]:
        """
        Get Dockerfile content
        
        Args:
            template_id: Template ID
            
        Returns:
            Dockerfile content or None
        """
        template = self.get_template(template_id)
        if not template:
            return None
        
        try:
            with open(template['dockerfile'], 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            logger.error(f"Read error Dockerfile: {e}")
            return None
    
    def create_template(
        self,
        template_id: str,
        name: str,
        description: str,
        dockerfile_content: str,
        config: Optional[Dict] = None
    ) -> bool:
        """
        Create new template
        
        Args:
            template_id: Template ID (directory name)
            name: Template name
            description: Description
            dockerfile_content: Dockerfile content
            config: Additional configuration
            
        Returns:
            True if successful
        """
        template_path = os.path.join(self.templates_dir, template_id)
        
        # Check existence
        if os.path.exists(template_path):
            logger.error(f"Template {template_id} already exists")
            return False
        
        try:
            # Creating directory
            os.makedirs(template_path)
            
            # Creating Dockerfile
            dockerfile_path = os.path.join(template_path, 'Dockerfile')
            with open(dockerfile_path, 'w', encoding='utf-8') as f:
                f.write(dockerfile_content)
            
            # Creating config.json
            config_data = config or {}
            config_data.update({
                'name': name,
                'description': description
            })
            
            config_path = os.path.join(template_path, 'config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Template {template_id} created")
            return True
            
        except IOError as e:
            logger.error(f"Template creation error {template_id}: {e}")
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """
        Remove template
        
        Args:
            template_id: Template ID
            
        Returns:
            True if successful
        """
        template = self.get_template(template_id)
        if not template:
            logger.error(f"Template {template_id} not found")
            return False
        
        try:
            import shutil
            shutil.rmtree(template['path'])
            logger.info(f"Template {template_id} removed")
            return True
        except Exception as e:
            logger.error(f"Template removal error {template_id}: {e}")
            return False
    
    def get_build_args(self, template_id: str) -> Dict[str, str]:
        """
        Get build arguments from template configuration
        
        Args:
            template_id: Template ID
            
        Returns:
            Dict with build args
        """
        template = self.get_template(template_id)
        if not template:
            return {}
        
        return template['config'].get('build_args', {})
    
    def get_default_config(self, template_id: str) -> Dict:
        """
        Get default configuration for container
        
        Args:
            template_id: Template ID
            
        Returns:
            Dict with default settings
        """
        template = self.get_template(template_id)
        if not template:
            return {}
        
        config = template['config']
        
        return {
            'user': config.get('default_user', 'user'),
            'uid': config.get('default_uid', 1000),
            'gid': config.get('default_gid', 1000),
            'gui_support': config.get('gui_support', True),
            'packages': config.get('packages', []),
            'environment': config.get('environment', {}),
            'volumes': config.get('volumes', {}),
            'network': config.get('network', 'bridge')
        }

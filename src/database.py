"""
Database manager for Docker Software Manager
Tracks user-created containers separately from development containers
"""

import sqlite3
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database for tracking user containers"""
    
    # Database version for migrations
    CURRENT_DB_VERSION = 2
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file. Defaults to ~/.local/share/docker-software-manager/containers.db
        """
        if db_path is None:
            # Use XDG Base Directory specification
            data_home = os.environ.get('XDG_DATA_HOME')
            if not data_home:
                data_home = os.path.expanduser('~/.local/share')
            
            app_dir = os.path.join(data_home, 'docker-software-manager')
            os.makedirs(app_dir, exist_ok=True)
            
            db_path = os.path.join(app_dir, 'containers.db')
        
        self.db_path = db_path
        self._init_database()
        self._run_migrations()
        logger.info(f"Database initialized at {self.db_path}")
    
    def _get_connection(self):
        """Get database connection with proper settings for multithreading"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Table for tracking containers created by this app
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS containers (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                template TEXT,
                disposable BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_started TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Table for container labels/tags
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS container_labels (
                container_id TEXT,
                key TEXT,
                value TEXT,
                FOREIGN KEY (container_id) REFERENCES containers(id) ON DELETE CASCADE,
                PRIMARY KEY (container_id, key)
            )
        ''')
        
        # Table for shared folders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shared_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id TEXT,
                host_path TEXT,
                container_path TEXT,
                FOREIGN KEY (container_id) REFERENCES containers(id) ON DELETE CASCADE
            )
        ''')
        
        # Table for application settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Note: container_apps table is created in migrations (version 2)
        
        conn.commit()
        conn.close()
    
    def _run_migrations(self):
        """Run database migrations if needed"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current database version
        try:
            cursor.execute("SELECT value FROM settings WHERE key = 'db_version'")
            result = cursor.fetchone()
            current_version = int(result[0]) if result else 0
        except sqlite3.Error:
            current_version = 0
        
        logger.info(f"Current DB version: {current_version}, Target version: {self.CURRENT_DB_VERSION}")
        
        # Run migrations
        if current_version < 1:
            logger.info("Running migration to version 1...")
            # Version 1: Initial schema - already created in _init_database
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES ('db_version', '1', CURRENT_TIMESTAMP)
            ''')
            current_version = 1
        
        if current_version < 2:
            logger.info("Running migration to version 2: Adding container_apps table...")
            # Version 2: Add container_apps table
            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS container_apps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        container_name TEXT NOT NULL,
                        app_name TEXT NOT NULL,
                        app_command TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(container_name, app_name)
                    )
                ''')
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES ('db_version', '2', CURRENT_TIMESTAMP)
                ''')
                logger.info("Migration to version 2 completed successfully")
            except sqlite3.Error as e:
                logger.error(f"Migration to version 2 failed: {e}")
        
        conn.commit()
        conn.close()
    
    def add_container(
        self,
        container_id: str,
        name: str,
        template: Optional[str] = None,
        disposable: bool = False,
        metadata: Optional[str] = None
    ) -> bool:
        """
        Add container to tracking database
        
        Args:
            container_id: Docker container ID
            name: Container name
            template: Template used (if any)
            disposable: Whether container is disposable
            metadata: Optional JSON metadata
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO containers (id, name, template, disposable, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (container_id, name, template, disposable, metadata))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Container {name} added to database")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error adding container: {e}")
            return False
    
    def remove_container(self, container_id: str) -> bool:
        """
        Remove container from tracking database
        
        Args:
            container_id: Docker container ID
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM containers WHERE id = ?', (container_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Container {container_id} removed from database")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error removing container: {e}")
            return False
    
    def get_tracked_containers(self) -> List[str]:
        """
        Get list of container IDs tracked by this app
        
        Returns:
            List of container IDs
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM containers')
            results = cursor.fetchall()
            
            conn.close()
            
            return [row[0] for row in results]
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting tracked containers: {e}")
            return []
    
    def is_tracked(self, container_id: str) -> bool:
        """
        Check if container is tracked by this app
        
        Args:
            container_id: Docker container ID
            
        Returns:
            True if tracked
        """
        return container_id in self.get_tracked_containers()
    
    def update_last_started(self, container_id: str):
        """
        Update last_started timestamp for container
        
        Args:
            container_id: Docker container ID
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE containers 
                SET last_started = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (container_id,))
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Database error updating timestamp: {e}")
    
    def get_container_info(self, container_id: str) -> Optional[Dict]:
        """
        Get container information from database
        
        Args:
            container_id: Docker container ID
            
        Returns:
            Dict with container info or None
        """
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM containers WHERE id = ?', (container_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting container info: {e}")
            return None
    
    def add_shared_folder(
        self,
        container_id: str,
        host_path: str,
        container_path: str
    ) -> bool:
        """
        Add shared folder mapping to database
        
        Args:
            container_id: Docker container ID
            host_path: Path on host
            container_path: Path in container
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO shared_folders (container_id, host_path, container_path)
                VALUES (?, ?, ?)
            ''', (container_id, host_path, container_path))
            
            conn.commit()
            conn.close()
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error adding shared folder: {e}")
            return False
    
    def get_shared_folders(self, container_id: str) -> List[Dict]:
        """
        Get shared folders for container
        
        Args:
            container_id: Docker container ID
            
        Returns:
            List of shared folder mappings
        """
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT host_path, container_path 
                FROM shared_folders 
                WHERE container_id = ?
            ''', (container_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in results]
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting shared folders: {e}")
            return []
    
    def add_label(self, container_id: str, key: str, value: str) -> bool:
        """
        Add label to container
        
        Args:
            container_id: Docker container ID
            key: Label key
            value: Label value
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO container_labels (container_id, key, value)
                VALUES (?, ?, ?)
            ''', (container_id, key, value))
            
            conn.commit()
            conn.close()
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error adding label: {e}")
            return False
    
    def get_labels(self, container_id: str) -> Dict[str, str]:
        """
        Get labels for container
        
        Args:
            container_id: Docker container ID
            
        Returns:
            Dict of labels
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT key, value 
                FROM container_labels 
                WHERE container_id = ?
            ''', (container_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            return {row[0]: row[1] for row in results}
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting labels: {e}")
            return {}
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get application setting
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else default
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting setting {key}: {e}")
            return default
    
    def set_setting(self, key: str, value: str) -> bool:
        """
        Set application setting
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error setting {key}: {e}")
            return False
    
    # Container Apps Methods
    
    def add_container_app(self, container_name: str, app_name: str, app_command: str) -> bool:
        """
        Add custom app for a container
        
        Args:
            container_name: Container name
            app_name: Application name
            app_command: Application command
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO container_apps (container_name, app_name, app_command)
                VALUES (?, ?, ?)
            ''', (container_name, app_name, app_command))
            
            conn.commit()
            conn.close()
            logger.info(f"Added custom app '{app_name}' for container {container_name}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error adding container app: {e}")
            return False
    
    def get_container_apps(self, container_name: str) -> List[Dict]:
        """
        Get all custom apps for a container
        
        Args:
            container_name: Container name
            
        Returns:
            List of app dicts with name and command
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT app_name, app_command, created_at
                FROM container_apps
                WHERE container_name = ?
                ORDER BY app_name
            ''', (container_name,))
            
            apps = []
            for row in cursor.fetchall():
                apps.append({
                    'name': row[0],
                    'command': row[1],
                    'created_at': row[2]
                })
            
            conn.close()
            return apps
            
        except sqlite3.Error as e:
            logger.error(f"Database error getting container apps: {e}")
            return []
    
    def remove_container_app(self, container_name: str, app_name: str) -> bool:
        """
        Remove custom app from container
        
        Args:
            container_name: Container name
            app_name: Application name
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM container_apps
                WHERE container_name = ? AND app_name = ?
            ''', (container_name, app_name))
            
            conn.commit()
            conn.close()
            logger.info(f"Removed custom app '{app_name}' from container {container_name}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Database error removing container app: {e}")
            return False

"""
Image Manager Plugin - View and manage ghostcontainers images
"""

import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from src.plugin_api import TabPlugin
from src.localization import t


class ImageManagerPlugin(TabPlugin):
    """Plugin for managing Docker images"""
    
    def __init__(self):
        super().__init__()
        self.name = "Image Manager"
        self.version = "1.0.0"
        self.description = "Manage Docker images"
        self.author = "GhostContainers"
        self.icon = "🖼️"
        self.widget = None
        self.docker_manager = None
    
    def get_tab_title(self) -> str:
        """Get tab title"""
        return "🖼️ " + self.name
    
    def initialize(self, app_context):
        """Initialize plugin with dependencies"""
        # Call parent TabPlugin.initialize to create tab widget
        if not super().initialize(app_context):
            return False
        
        # Store additional dependencies
        self.docker_manager = app_context.get('docker_manager')
        self.db = app_context.get('db')
        return True
    
    def create_tab_widget(self) -> QWidget:
        """Create the image manager tab widget"""
        # Create widget
        self.widget = QWidget()
        layout = QVBoxLayout(self.widget)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        # Show all images checkbox
        self.show_all_check = QCheckBox("Show all images")
        self.show_all_check.stateChanged.connect(self._refresh_images)
        controls_layout.addWidget(self.show_all_check)
        
        controls_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_images)
        controls_layout.addWidget(refresh_btn)
        
        # Delete button
        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)
        controls_layout.addWidget(self.delete_btn)
        
        layout.addLayout(controls_layout)
        
        # Images table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Image Name", "Tag", "Platform", "Size", "Created", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        # Info label
        self.info_label = QLabel()
        layout.addWidget(self.info_label)
        
        # Store as tab_widget for TabPlugin
        self.tab_widget = self.widget
        
        # Initial load
        self._refresh_images()
        
        return self.widget
    
    def _refresh_images(self):
        """Refresh images list"""
        if not self.docker_manager:
            return
        
        self.table.setRowCount(0)
        
        try:
            # Get all images
            all_images = self.docker_manager.client.images.list()
            
            show_all = self.show_all_check.isChecked()
            ghostcontainers_images = []
            
            for image in all_images:
                # Get image name
                tags = image.tags
                # Ensure tags is a list
                if not isinstance(tags, list):
                    tags = []
                if not tags:
                    continue
                
                for tag in tags:
                    # Ensure tag is a string
                    if not isinstance(tag, str):
                        continue
                    
                    # Filter ghostcontainers images
                    if 'ghostcontainers-' in tag or show_all:
                        # Get size safely
                        size = image.attrs.get('Size', 0)
                        if not isinstance(size, (int, float)):
                            size = 0
                        
                        ghostcontainers_images.append({
                            'tag': tag,
                            'id': image.short_id.replace('sha256:', ''),
                            'size': int(size),
                            'created': str(image.attrs.get('Created', '')),
                            'platform': str(image.attrs.get('Architecture', 'unknown'))
                        })
            
            # Populate table
            self.table.setRowCount(len(ghostcontainers_images))
            
            for row, img in enumerate(ghostcontainers_images):
                # Split tag into name and version
                full_tag = img['tag']
                if ':' in full_tag:
                    name, version = full_tag.rsplit(':', 1)
                else:
                    name = full_tag
                    version = 'latest'
                
                # Name
                self.table.setItem(row, 0, QTableWidgetItem(name))
                
                # Tag
                self.table.setItem(row, 1, QTableWidgetItem(version))
                
                # Platform
                self.table.setItem(row, 2, QTableWidgetItem(img['platform']))
                
                # Size (convert to MB)
                size_mb = img['size'] / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"
                self.table.setItem(row, 3, QTableWidgetItem(size_str))
                
                # Created (format timestamp)
                created = img['created'].split('T')[0] if 'T' in img['created'] else img['created']
                self.table.setItem(row, 4, QTableWidgetItem(created))
                
                # ID
                self.table.setItem(row, 5, QTableWidgetItem(img['id']))
            
            # Update info
            total_size = sum(img['size'] for img in ghostcontainers_images)
            total_size_mb = total_size / (1024 * 1024)
            self.info_label.setText(
                f"Total: {len(ghostcontainers_images)} images, {total_size_mb:.1f} MB"
            )
            
        except Exception as e:
            QMessageBox.critical(self.widget, "Error", f"Failed to load images: {str(e)}")
    
    def _on_selection_changed(self):
        """Handle selection change"""
        self.delete_btn.setEnabled(len(self.table.selectedItems()) > 0)
    
    def _delete_selected(self):
        """Delete selected images"""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        
        if not selected_rows:
            return
        
        # Confirm deletion
        count = len(selected_rows)
        reply = QMessageBox.question(
            self.widget,
            "Confirm Deletion",
            f"Delete {count} image(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Delete images
        errors = []
        for row in sorted(selected_rows, reverse=True):
            image_name = self.table.item(row, 0).text()
            image_tag = self.table.item(row, 1).text()
            full_tag = f"{image_name}:{image_tag}"
            
            try:
                self.docker_manager.client.images.remove(full_tag, force=True)
            except Exception as e:
                errors.append(f"{full_tag}: {str(e)}")
        
        # Show results
        if errors:
            QMessageBox.warning(
                self.widget,
                "Deletion Errors",
                "Failed to delete:\n" + "\n".join(errors)
            )
        else:
            QMessageBox.information(
                self.widget,
                "Success",
                f"Deleted {count} image(s) successfully"
            )
        
        # Refresh
        self._refresh_images()

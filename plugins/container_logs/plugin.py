"""
Container Logs Plugin
Provides log viewing interface for containers
Uses common LogViewerWidget for display
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QMessageBox, QCheckBox
)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.plugin_api import TabPlugin
from src.localization import t
from src.gui.log_viewer_widget import LogViewerWidget
import logging

class ContainerLogsPlugin(TabPlugin):
    """Container logs viewer plugin"""
    
    def __init__(self):
        super().__init__()
        self.name = "Container Logs"
        self.version = "2.0.0"
        self.description = "View container logs with color coding"
        self.author = "GhostContainers"
        
        self.tab_widget = None
        self.log_container_combo = None
        self.log_viewer = None
        self.show_all_check = None
        
        # Register for container updates hook
        self.register_hook('HOOK_CONTAINERS_UPDATED', self.update_containers)
    
    def get_tab_title(self) -> str:
        return t('tabs.logs')
    
    def create_tab_widget(self) -> QWidget:
        """Create the logs viewer tab"""
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Container selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel(t('labels.container') + ":", widget))
        
        self.log_container_combo = QComboBox(widget)  # Set parent to widget
        self.log_container_combo.setMinimumWidth(200)
        selector_layout.addWidget(self.log_container_combo)
        
        show_btn = QPushButton(t('labels.show_logs'), widget)
        show_btn.clicked.connect(self.show_logs)
        selector_layout.addWidget(show_btn)
        
        selector_layout.addStretch()
        
        # Show all containers checkbox
        self.show_all_check = QCheckBox(t('labels.show_all_containers'), widget)
        self.show_all_check.stateChanged.connect(self.refresh_container_list)
        selector_layout.addWidget(self.show_all_check)
        
        # Refresh button
        refresh_btn = QPushButton(t('buttons.refresh'), widget)
        refresh_btn.clicked.connect(self.refresh_container_list)
        selector_layout.addWidget(refresh_btn)
        
        layout.addLayout(selector_layout)
        
        # Use common log viewer widget
        self.log_viewer = LogViewerWidget(parent=widget, show_controls=True)
        layout.addWidget(self.log_viewer)
        
        self.tab_widget = widget
        return widget
    
    def refresh_container_list(self):
        """Refresh container list with current show_all setting"""
        if not self.plugin_api:
            return
        
        # Get show_all state from this plugin's checkbox
        show_all = self.show_all_check.isChecked() if self.show_all_check else False
        
        # Get containers using PluginAPI with our show_all setting
        containers = self.plugin_api.get_containers(all_containers=True, show_all=show_all)
        self.update_containers(containers)
    
    def update_containers(self, containers):
        """Update container list (called by hook)"""
        
        # Check for None explicitly, not bool() because PyQt6 deleted widgets return False
        if self.log_container_combo is None:
            return
        
        # Additional check: try to access the widget to see if it's been deleted
        try:
            _ = self.log_container_combo.count()
        except RuntimeError:
            return
        
        current_selection = self.log_container_combo.currentText()
        self.log_container_combo.clear()
        all_names = [c['name'] for c in containers]
        self.log_container_combo.addItems(all_names)
        
        # Restore selection
        if current_selection:
            index = self.log_container_combo.findText(current_selection)
            if index >= 0:
                self.log_container_combo.setCurrentIndex(index)
    
    def refresh(self):
        """Refresh logs"""
        self.show_logs()
    
    def show_logs(self):
        """Show container logs with color coding"""
        if not self.log_container_combo or not self.log_viewer:
            return
            
        container = self.log_container_combo.currentText()
        if not container:
            QMessageBox.warning(self.tab_widget, t('dialogs.warning_title'), 
                              t('messages.select_container'))
            return
        
        logs = self.docker_manager.get_container_logs(container, tail=500)
        if logs:
            self.log_viewer.clear()
            
            # Append each line with ANSI color support
            for line in logs.split('\n'):
                if line:
                    self.log_viewer.append_line(line)
        else:
            QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                               t('messages.failed_get_logs').format(container=container))

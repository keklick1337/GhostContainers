"""
Container Logs Plugin
Provides log viewing interface for containers
Uses common LogViewerWidget for display
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QMessageBox
)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.plugin_api import TabPlugin
from src.localization import t
from src.gui.log_viewer_widget import LogViewerWidget


class ContainerLogsPlugin(TabPlugin):
    """Container logs viewer plugin"""
    
    def __init__(self):
        super().__init__()
        self.name = "Container Logs"
        self.version = "2.0.0"
        self.description = "View container logs with color coding"
        self.author = "GhostContainers Team"
        
        self.tab_widget = None
        self.log_container_combo = None
        self.log_viewer = None
        
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
        selector_layout.addWidget(QLabel(t('labels.container') + ":"))
        
        self.log_container_combo = QComboBox()
        selector_layout.addWidget(self.log_container_combo)
        
        show_btn = QPushButton(t('labels.show_logs'))
        show_btn.clicked.connect(self.show_logs)
        selector_layout.addWidget(show_btn)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Use common log viewer widget
        self.log_viewer = LogViewerWidget(parent=widget, show_controls=True)
        layout.addWidget(self.log_viewer)
        
        self.tab_widget = widget
        return widget
    
    def update_containers(self, containers):
        """Update container list"""
        if not self.log_container_combo:
            return
            
        self.log_container_combo.clear()
        all_names = [c['name'] for c in containers]
        self.log_container_combo.addItems(all_names)
    
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

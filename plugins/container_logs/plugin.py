"""
Container Logs Plugin
Provides log viewing interface for containers
"""

import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QCheckBox, QTextEdit, QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QTextCursor

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.plugin_api import TabPlugin
from src.localization import t


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
        self.logs_text = None
        self.auto_scroll_check = None
        
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
        
        clear_btn = QPushButton(t('buttons.clear'))
        clear_btn.clicked.connect(self.clear_logs)
        selector_layout.addWidget(clear_btn)
        
        self.auto_scroll_check = QCheckBox(t('labels.auto_scroll'))
        self.auto_scroll_check.setChecked(True)
        selector_layout.addWidget(self.auto_scroll_check)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Logs text
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Monaco", 10))
        self.logs_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.logs_text)
        
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
        if not self.log_container_combo:
            return
            
        container = self.log_container_combo.currentText()
        if not container:
            QMessageBox.warning(self.tab_widget, t('dialogs.warning_title'), 
                              t('messages.select_container'))
            return
        
        logs = self.docker_manager.get_container_logs(container, tail=500)
        if logs:
            self.logs_text.clear()
            
            cursor = self.logs_text.textCursor()
            
            for line in logs.split('\n'):
                if not line:
                    continue
                
                # Determine color based on log level
                if re.search(r'\b(ERROR|FATAL|CRITICAL)\b', line, re.IGNORECASE):
                    color = '#ff5555'
                elif re.search(r'\bWARN(ING)?\b', line, re.IGNORECASE):
                    color = '#ffb86c'
                elif re.search(r'\bINFO\b', line, re.IGNORECASE):
                    color = '#50fa7b'
                elif re.search(r'\bDEBUG\b', line, re.IGNORECASE):
                    color = '#8be9fd'
                else:
                    color = '#d4d4d4'
                
                cursor.movePosition(QTextCursor.MoveOperation.End)
                fmt = cursor.charFormat()
                fmt.setForeground(QColor(color))
                cursor.setCharFormat(fmt)
                cursor.insertText(line + '\n')
            
            if self.auto_scroll_check.isChecked():
                scrollbar = self.logs_text.verticalScrollBar()
                if scrollbar:
                    scrollbar.setValue(scrollbar.maximum())
        else:
            QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                               t('messages.failed_get_logs').format(container=container))
    
    def clear_logs(self):
        """Clear logs display"""
        if self.logs_text:
            self.logs_text.clear()

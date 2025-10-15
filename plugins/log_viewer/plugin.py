"""
Log Viewer Plugin for GhostContainers
Provides enhanced log viewing with auto-scroll, color coding, and filtering
"""

import sys
import os
import re
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from plugin_system import UIPlugin
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                              QPushButton, QLineEdit, QLabel, QCheckBox)
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import Qt, QTimer
import logging

logger = logging.getLogger(__name__)


class LogViewerWidget(QWidget):
    """Enhanced log viewer widget with auto-scroll and filtering"""
    
    def __init__(self, docker_manager=None):
        super().__init__()
        self.docker_manager = docker_manager
        self.current_container = None
        self.auto_scroll_enabled = True
        self.user_scrolled = False
        self.log_buffer = []
        
        self._init_ui()
        
        # Timer for live log updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._fetch_new_logs)
        self.update_timer.setInterval(1000)  # Update every 1 second
        
    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        
        # Control bar
        control_layout = QHBoxLayout()
        
        # Auto-scroll toggle
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.toggled.connect(self._toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_checkbox)
        
        # Filter input
        control_layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Enter text to filter...")
        self.filter_input.textChanged.connect(self._apply_filter)
        control_layout.addWidget(self.filter_input)
        
        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_logs)
        control_layout.addWidget(clear_button)
        
        # Live toggle
        self.live_checkbox = QCheckBox("Live")
        self.live_checkbox.setChecked(False)
        self.live_checkbox.toggled.connect(self._toggle_live_logs)
        control_layout.addWidget(self.live_checkbox)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monaco", 10))
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Connect scroll event to detect user scrolling
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll)
        
        layout.addWidget(self.log_text)
        
    def set_container(self, container_name: str):
        """Set the container to view logs from"""
        self.current_container = container_name
        self._clear_logs()
        self._load_initial_logs()
        
    def _load_initial_logs(self):
        """Load initial logs from container"""
        if not self.current_container or not self.docker_manager:
            return
        
        try:
            # Get last 100 lines of logs
            logs = self.docker_manager.get_logs(self.current_container, tail=100)
            if logs:
                self._append_logs(logs)
        except Exception as e:
            logger.error(f"Failed to load logs: {e}")
            self.log_text.append(f"Error loading logs: {str(e)}")
    
    def _fetch_new_logs(self):
        """Fetch new logs (for live mode)"""
        if not self.current_container or not self.docker_manager:
            return
        
        try:
            # Get logs since last update
            logs = self.docker_manager.get_logs(self.current_container, tail=50)
            if logs:
                # Only append if different from last logs
                self._append_logs(logs, check_duplicate=True)
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
    
    def _append_logs(self, logs: str, check_duplicate: bool = False):
        """Append logs with color coding"""
        lines = logs.strip().split('\n')
        
        for line in lines:
            if not line:
                continue
            
            # Skip duplicate lines if requested
            if check_duplicate and self.log_buffer and line == self.log_buffer[-1]:
                continue
            
            self.log_buffer.append(line)
            
            # Apply color based on log level
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            
            fmt = QTextCharFormat()
            
            # Detect log level and apply color
            if re.search(r'\b(ERROR|FATAL|CRITICAL)\b', line, re.IGNORECASE):
                fmt.setForeground(QColor("#FF5555"))  # Red for errors
            elif re.search(r'\bWARN(ING)?\b', line, re.IGNORECASE):
                fmt.setForeground(QColor("#FFB86C"))  # Orange for warnings
            elif re.search(r'\bINFO\b', line, re.IGNORECASE):
                fmt.setForeground(QColor("#50FA7B"))  # Green for info
            elif re.search(r'\bDEBUG\b', line, re.IGNORECASE):
                fmt.setForeground(QColor("#8BE9FD"))  # Cyan for debug
            else:
                fmt.setForeground(QColor("#F8F8F2"))  # Default white
            
            cursor.setCharFormat(fmt)
            cursor.insertText(line + '\n')
            
        # Auto-scroll to bottom if enabled and user hasn't scrolled
        if self.auto_scroll_enabled and not self.user_scrolled:
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
    
    def _on_scroll(self, value):
        """Detect if user has manually scrolled"""
        scrollbar = self.log_text.verticalScrollBar()
        
        # If user scrolls up from bottom, disable auto-scroll temporarily
        if value < scrollbar.maximum() - 10:  # 10px tolerance
            self.user_scrolled = True
        else:
            # User scrolled to bottom, re-enable auto-scroll
            self.user_scrolled = False
    
    def _toggle_auto_scroll(self, checked):
        """Toggle auto-scroll feature"""
        self.auto_scroll_enabled = checked
        if checked:
            self.user_scrolled = False
            # Scroll to bottom immediately
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
    
    def _toggle_live_logs(self, checked):
        """Toggle live log streaming"""
        if checked:
            self.update_timer.start()
        else:
            self.update_timer.stop()
    
    def _apply_filter(self, filter_text):
        """Filter logs based on text"""
        # Simple implementation: hide lines that don't match
        # For better performance, this could be optimized
        pass  # TODO: Implement filtering
    
    def _clear_logs(self):
        """Clear log display"""
        self.log_text.clear()
        self.log_buffer.clear()


class LogViewerPlugin(UIPlugin):
    """Plugin for enhanced log viewing"""
    
    def __init__(self):
        super().__init__()
        self.name = "Log Viewer"
        self.version = "1.0.0"
        self.description = "Enhanced log viewer with auto-scroll and color coding"
        self.author = "GhostContainers"
        self.app_context = None
        self.log_widgets = {}
        
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """Initialize plugin"""
        self.app_context = app_context
        logger.info("Log Viewer plugin initialized")
        return True
        
    def get_info(self) -> Dict[str, str]:
        """Get plugin info"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author
        }
    
    def create_log_viewer(self, docker_manager=None) -> LogViewerWidget:
        """Create a log viewer widget"""
        widget = LogViewerWidget(docker_manager)
        return widget
    
    def get_widget(self, widget_type: str, parent=None) -> Optional[QWidget]:
        """Get a widget of specified type"""
        if widget_type == "log_viewer":
            docker_manager = self.app_context.get('docker_manager') if self.app_context else None
            return self.create_log_viewer(docker_manager)
        return None
    
    def get_menu_items(self) -> list:
        """Get menu items to add to main menu"""
        return []
    
    def shutdown(self):
        """Cleanup"""
        self.log_widgets.clear()

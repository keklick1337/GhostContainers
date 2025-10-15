"""
Logs Viewer Tab Widget
"""

import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QCheckBox, QTextEdit, QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QTextCursor

from ..localization import t


class LogsTab(QWidget):
    """Container logs viewer tab"""
    
    def __init__(self, parent, docker_manager):
        super().__init__(parent)
        self.parent_window = parent
        self.docker_manager = docker_manager
        
        self._create_ui()
    
    def _create_ui(self):
        """Create logs tab UI"""
        layout = QVBoxLayout(self)
        
        # Container selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel(t('labels.container') + ":"))
        
        self.log_container_combo = QComboBox()
        selector_layout.addWidget(self.log_container_combo)
        
        show_btn = QPushButton(t('labels.show_logs'))
        show_btn.clicked.connect(self.parent_window.show_logs)
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
    
    def update_containers(self, containers):
        """Update container combo"""
        self.log_container_combo.clear()
        all_names = [c['name'] for c in containers]
        self.log_container_combo.addItems(all_names)
    
    def show_logs(self):
        """Show container logs with color coding"""
        container = self.log_container_combo.currentText()
        if not container:
            QMessageBox.warning(self, t('dialogs.warning_title'), t('messages.select_container'))
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
            QMessageBox.critical(self, t('dialogs.error_title'), 
                               t('messages.failed_get_logs').format(container=container))
    
    def clear_logs(self):
        """Clear logs display"""
        self.logs_text.clear()

"""
Container Logs Window - Real-time container output viewer
Uses common LogViewerWidget for display
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from .log_viewer_widget import LogViewerWidget, ContainerLogsReaderThread
import logging

logger = logging.getLogger(__name__)


class ContainerLogsWindow(QDialog):
    """Window for displaying container logs with ANSI color support"""
    
    def __init__(self, docker_manager, container_id, container_name, parent=None):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.container_id = container_id
        self.container_name = container_name
        self.logs_thread = None
        
        self.setWindowTitle(f"Container Logs - {container_name}")
        self.setMinimumSize(900, 600)
        
        self.init_ui()
        self.start_logs()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Info bar
        info_layout = QHBoxLayout()
        
        self.status_label = QLabel("📄 Reading logs...")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("✖ Close")
        close_btn.clicked.connect(self.close)
        info_layout.addWidget(close_btn)
        
        layout.addLayout(info_layout)
        
        # Use common log viewer widget
        self.log_viewer = LogViewerWidget(parent=self, show_controls=True)
        layout.addWidget(self.log_viewer)
        
        self.setLayout(layout)
    
    def start_logs(self):
        """Start reading logs"""
        if self.logs_thread:
            return
        
        self.logs_thread = ContainerLogsReaderThread(
            self.docker_manager,
            self.container_id,
            follow=True
        )
        
        self.logs_thread.log_line.connect(self.log_viewer.append_line)
        self.logs_thread.finished_signal.connect(self._on_logs_finished)
        self.logs_thread.start()
    
    def _on_logs_finished(self, success: bool, message: str):
        """Handle logs stream end"""
        if success:
            self.status_label.setText(f"✓ {message}")
        else:
            self.status_label.setText(f"✗ {message}")
        
        self.logs_thread = None
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.logs_thread:
            self.logs_thread.stop()
            self.logs_thread.wait(1000)
        
        # Remove reference from main window to allow garbage collection
        parent = self.parent()
        if parent and hasattr(parent, '_active_logs_windows'):
            try:
                parent._active_logs_windows.remove(self)
            except (ValueError, AttributeError):
                pass
        
        event.accept()

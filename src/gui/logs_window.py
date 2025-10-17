"""
Container Logs Window - Real-time container output viewer
Uses common LogViewerWidget for display
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from .log_viewer_widget import LogViewerWidget, ContainerLogsReaderThread
from ..localization import t
import logging

logger = logging.getLogger(__name__)


class LogCaptureHandler(logging.Handler):
    """Custom logging handler to capture logs and send to UI"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        
        # Format with level colors
        self.level_colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
    
    def emit(self, record):
        """Emit log record"""
        try:
            # Format: [LEVEL] module: message
            level_name = record.levelname
            color = self.level_colors.get(level_name, '')
            reset = '\033[0m' if color else ''
            
            log_msg = f"{color}[{level_name}]\033[0m {record.name}: {record.getMessage()}"
            self.callback(log_msg)
        except Exception:
            self.handleError(record)


class ContainerLogsWindow(QDialog):
    """Window for displaying container logs with ANSI color support"""
    
    def __init__(self, docker_manager, container_id, container_name, parent=None):
        # Create as independent window without parent to prevent auto-close
        super().__init__(None)
        
        # Store parent reference for cleanup list
        self._parent_window = parent
        
        self.docker_manager = docker_manager
        self.container_id = container_id
        self.container_name = container_name
        self.logs_thread = None
        self.log_handler = None
        
        # Make window independent and prevent auto-deletion
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        self.setWindowTitle(f"Container Logs - {container_name}")
        self.setMinimumSize(900, 600)
        
        self.init_ui()
        self.start_logs()
        self.setup_log_capture()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Info bar
        info_layout = QHBoxLayout()
        
        self.status_label = QLabel("Reading logs...")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        
        # Kill button (for stopping hung processes)
        kill_btn = QPushButton("Kill Process")
        kill_btn.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
        kill_btn.setToolTip("Send SIGKILL to main process (use if hung)")
        kill_btn.clicked.connect(self._kill_process)
        info_layout.addWidget(kill_btn)
        
        # Close button
        close_btn = QPushButton(t('buttons.close'))
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
    
    def setup_log_capture(self):
        """Setup logging capture to display app logs in window"""
        # Create handler that sends logs to viewer
        self.log_handler = LogCaptureHandler(self._on_app_log)
        self.log_handler.setLevel(logging.DEBUG)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        
        # Add separator with ANSI colors
        self.log_viewer.append_line("\n" + "="*60)
        self.log_viewer.append_line("\033[36m[APPLICATION LOGS]\033[0m Real-time system events")
        self.log_viewer.append_line("="*60 + "\n")
    
    def _on_app_log(self, log_message: str):
        """Handle application log message"""
        self.log_viewer.append_line(log_message)
    
    def _on_logs_finished(self, success: bool, message: str):
        """Handle logs stream end"""
        if success:
            self.status_label.setText(f"[OK] {message}")
        else:
            self.status_label.setText(f"[ERROR] {message}")
        
        self.logs_thread = None
    
    def _kill_process(self):
        """Force kill the main process inside container"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Confirm Kill",
            f"Send SIGKILL (kill -9) to the main process in '{self.container_name}'?\n\n"
            "This will forcefully terminate the process if it's hung.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get container
                container = self.docker_manager.client.containers.get(self.container_id)
                
                # Execute kill -9 1 (PID 1 is the main process in container)
                exec_result = container.exec_run("kill -9 1", privileged=True)
                
                # Add kill notification with ANSI colors (red)
                self.log_viewer.append_line("\n" + "="*60)
                self.log_viewer.append_line("\033[31;1m[SIGKILL]\033[0m Sent SIGKILL to main process (PID 1)")
                self.log_viewer.append_line("="*60 + "\n")
                self.status_label.setText("Process killed (SIGKILL sent)")
                
                logger.info(f"SIGKILL sent to main process in container {self.container_name}")
                
            except Exception as e:
                self.log_viewer.append_line(f"\n\033[31m[ERROR]\033[0m Failed to kill process: {e}\n")
                self.status_label.setText(f"Kill failed: {e}")
                logger.error(f"Failed to kill process in container {self.container_name}: {e}")
    
    def closeEvent(self, event):
        """Handle window close"""
        # Stop container logs thread
        if self.logs_thread:
            self.logs_thread.stop()
            self.logs_thread.wait(1000)
        
        # Remove logging handler
        if self.log_handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)
            self.log_handler = None
        
        # Remove reference from main window to allow garbage collection
        if self._parent_window and hasattr(self._parent_window, '_active_logs_windows'):
            try:
                self._parent_window._active_logs_windows.remove(self)
            except (ValueError, AttributeError):
                pass
        
        event.accept()

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
        kill_btn = QPushButton("Stop (Ctrl+C)")
        kill_btn.setStyleSheet("background-color: #ffb86c; color: black; font-weight: bold;")
        kill_btn.setToolTip("Send SIGINT (Ctrl+C) to main process")
        kill_btn.clicked.connect(self._send_sigint)
        info_layout.addWidget(kill_btn)
        
        # Force Kill button (for really hung processes)
        force_kill_btn = QPushButton("Force Kill")
        force_kill_btn.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
        force_kill_btn.setToolTip("Send SIGKILL (kill -9) if Ctrl+C doesn't work")
        force_kill_btn.clicked.connect(self._send_sigkill)
        info_layout.addWidget(force_kill_btn)
        
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
        # Check container status to determine why logs ended
        try:
            container = self.docker_manager.client.containers.get(self.container_id)
            container.reload()
            status = container.attrs.get('State', {})
            
            container_status = status.get('Status', 'unknown')
            exit_code = status.get('ExitCode', 0)
            
            # Display container status in logs
            self.log_viewer.append_line("\n" + "="*60)
            
            if container_status == 'exited':
                if exit_code == 0:
                    self.log_viewer.append_line("\033[32m[CONTAINER STOPPED]\033[0m Exited successfully (code 0)")
                    self.status_label.setText("[OK] Container exited successfully")
                else:
                    self.log_viewer.append_line(f"\033[31m[CONTAINER STOPPED]\033[0m Exited with error code {exit_code}")
                    self.status_label.setText(f"[ERROR] Container exited with code {exit_code}")
            elif container_status == 'running':
                self.log_viewer.append_line("\033[36m[INFO]\033[0m Container is still running, logs stream ended")
                self.status_label.setText("[OK] Logs stream ended (container running)")
            else:
                self.log_viewer.append_line(f"\033[33m[CONTAINER STOPPED]\033[0m Status: {container_status}")
                self.status_label.setText(f"[INFO] Container {container_status}")
            
            self.log_viewer.append_line("="*60 + "\n")
            
        except Exception as e:
            # Container might be removed (disposable)
            self.log_viewer.append_line("\n" + "="*60)
            self.log_viewer.append_line("\033[35m[CONTAINER REMOVED]\033[0m Container has been removed (disposable)")
            self.log_viewer.append_line("="*60 + "\n")
            self.status_label.setText("[OK] Container removed")
            logger.info(f"Container {self.container_name} was removed (disposable)")
        
        self.logs_thread = None
    
    def _send_sigint(self):
        """Send SIGINT (Ctrl+C) to main process"""
        from PyQt6.QtWidgets import QMessageBox
        
        try:
            # Get container
            container = self.docker_manager.client.containers.get(self.container_id)
            
            # Send SIGINT to PID 1 (main process)
            result = container.exec_run("kill -INT 1", privileged=True)
            
            # Log the action
            self.log_viewer.append_line("\n" + "="*60)
            self.log_viewer.append_line("\033[33m[SIGINT]\033[0m Sent Ctrl+C to main process")
            self.log_viewer.append_line("="*60 + "\n")
            self.status_label.setText("SIGINT sent (Ctrl+C)")
            
            logger.info(f"SIGINT sent to main process in container {self.container_name}")
            
        except Exception as e:
            self.log_viewer.append_line(f"\n\033[31m[ERROR]\033[0m Failed to send SIGINT: {e}\n")
            self.status_label.setText(f"SIGINT failed: {e}")
            logger.error(f"Failed to send SIGINT to container {self.container_name}: {e}")
    
    def _send_sigkill(self):
        """Force kill all processes (last resort)"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.warning(
            self,
            "Confirm Force Kill",
            f"Send SIGKILL (kill -9) to all processes in '{self.container_name}'?\n\n"
            "⚠️ This is a last resort! Try 'Stop (Ctrl+C)' first.\n"
            "SIGKILL forcefully terminates processes without cleanup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get container
                container = self.docker_manager.client.containers.get(self.container_id)
                
                killed_count = 0
                
                try:
                    # Try to find and kill all processes except PID 1
                    # Get process list
                    ps_result = container.exec_run("ps aux", privileged=True)
                    
                    if ps_result.exit_code == 0 and ps_result.output:
                        # Decode with multiple fallbacks
                        try:
                            output_text = ps_result.output.decode('utf-8', errors='replace')
                        except:
                            try:
                                output_text = ps_result.output.decode('latin-1', errors='replace')
                            except:
                                output_text = str(ps_result.output)
                        
                        processes = output_text.split('\n')
                        
                        for line in processes[1:]:  # Skip header
                            if line.strip():
                                try:
                                    parts = line.split(None, 10)
                                    if len(parts) >= 2:
                                        pid = parts[1]
                                        # Skip PID 1 (init process) and ps command
                                        if pid.isdigit() and pid != '1':
                                            kill_result = container.exec_run(f"kill -9 {pid}", privileged=True)
                                            if kill_result.exit_code == 0 or kill_result.exit_code == 1:  # 1 = already dead
                                                killed_count += 1
                                                self.log_viewer.append_line(f"\033[33m[SIGKILL]\033[0m Killed PID {pid}")
                                except Exception as parse_err:
                                    # Skip malformed lines
                                    continue
                    
                except Exception as ps_err:
                    logger.warning(f"Failed to parse ps output: {ps_err}, falling back to killall")
                    # Fallback: use killall to kill all processes
                    try:
                        container.exec_run("killall -9 firefox", privileged=True)
                        container.exec_run("killall -9 chrome", privileged=True)
                        container.exec_run("killall -9 chromium", privileged=True)
                        killed_count = 1  # At least tried
                    except:
                        pass
                
                # Show results
                if killed_count > 0:
                    self.log_viewer.append_line("\n" + "="*60)
                    self.log_viewer.append_line(f"\033[31;1m[KILLED]\033[0m Terminated {killed_count} process(es)")
                    self.log_viewer.append_line("="*60 + "\n")
                    self.status_label.setText(f"Killed {killed_count} process(es)")
                    logger.info(f"Killed {killed_count} process(es) in container {self.container_name}")
                else:
                    # Last resort: kill PID 1
                    container.exec_run("kill -9 1", privileged=True)
                    self.log_viewer.append_line("\n" + "="*60)
                    self.log_viewer.append_line("\033[31;1m[SIGKILL]\033[0m Sent SIGKILL to main process")
                    self.log_viewer.append_line("="*60 + "\n")
                    self.status_label.setText("Process killed")
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

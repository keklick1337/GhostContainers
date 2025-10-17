"""
Container Logs Window - Real-time container output viewer
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
import re
import logging

logger = logging.getLogger(__name__)


class LogsReaderThread(QThread):
    """Thread for reading container logs in real-time"""
    
    log_line = pyqtSignal(str)  # Emits each log line
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, docker_manager, container_id, follow=True):
        super().__init__()
        self.docker_manager = docker_manager
        self.container_id = container_id
        self.follow = follow
        self.running = True
    
    def run(self):
        """Read logs from container"""
        try:
            # Get logs with streaming
            response = self.docker_manager.client.containers.logs(
                self.container_id,
                stdout=True,
                stderr=True,
                stream=True,
                follow=self.follow,
                timestamps=False
            )
            
            # Read logs line by line
            while self.running:
                try:
                    line = response.readline()
                    if not line:
                        break
                    
                    # Decode and emit
                    line_str = line.decode('utf-8', errors='ignore').rstrip()
                    if line_str:
                        self.log_line.emit(line_str)
                
                except Exception as e:
                    logger.error(f"Error reading log line: {e}")
                    break
            
            self.finished_signal.emit(True, "Logs stream ended")
            
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            self.finished_signal.emit(False, f"Error: {e}")
    
    def stop(self):
        """Stop reading logs"""
        self.running = False


class ContainerLogsWindow(QDialog):
    """Window for displaying container logs with ANSI color support"""
    
    def __init__(self, docker_manager, container_id, container_name, parent=None):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.container_id = container_id
        self.container_name = container_name
        self.logs_thread = None
        self.auto_scroll = True
        
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
        
        # Import translation
        from ..localization import t
        
        # Wrap logs checkbox
        from PyQt6.QtWidgets import QCheckBox
        self.wrap_logs_check = QCheckBox(t('labels.wrap_logs'))
        self.wrap_logs_check.setChecked(True)  # Enable by default
        self.wrap_logs_check.stateChanged.connect(self._on_wrap_logs_changed)
        info_layout.addWidget(self.wrap_logs_check)
        
        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox(t('labels.auto_scroll'))
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self._on_auto_scroll_changed)
        info_layout.addWidget(self.auto_scroll_check)
        
        # Clear button
        clear_btn = QPushButton("🗑️ " + t('buttons.clear'))
        clear_btn.clicked.connect(self._clear_logs)
        info_layout.addWidget(clear_btn)
        
        # Close button
        close_btn = QPushButton("✖ Close")
        close_btn.clicked.connect(self.close)
        info_layout.addWidget(close_btn)
        
        layout.addLayout(info_layout)
        
        # Logs text area
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # Enable wrap by default
        
        # Set monospace font
        font = QFont("Monaco, Menlo, Courier New, monospace")
        font.setPointSize(11)
        self.logs_text.setFont(font)
        
        # Dark background for logs
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)
        
        layout.addWidget(self.logs_text)
        
        self.setLayout(layout)
        
        # ANSI color mapping
        self.ansi_colors = {
            '30': QColor(0, 0, 0),        # Black
            '31': QColor(205, 49, 49),    # Red
            '32': QColor(13, 188, 121),   # Green
            '33': QColor(229, 229, 16),   # Yellow
            '34': QColor(36, 114, 200),   # Blue
            '35': QColor(188, 63, 188),   # Magenta
            '36': QColor(17, 168, 205),   # Cyan
            '37': QColor(229, 229, 229),  # White
            '90': QColor(102, 102, 102),  # Bright Black (Gray)
            '91': QColor(241, 76, 76),    # Bright Red
            '92': QColor(35, 209, 139),   # Bright Green
            '93': QColor(245, 245, 67),   # Bright Yellow
            '94': QColor(59, 142, 234),   # Bright Blue
            '95': QColor(214, 112, 214),  # Bright Magenta
            '96': QColor(41, 184, 219),   # Bright Cyan
            '97': QColor(229, 229, 229),  # Bright White
        }
    
    def start_logs(self):
        """Start reading logs"""
        if self.logs_thread:
            return
        
        self.logs_thread = LogsReaderThread(
            self.docker_manager,
            self.container_id,
            follow=True
        )
        
        self.logs_thread.log_line.connect(self._append_log_line)
        self.logs_thread.finished_signal.connect(self._on_logs_finished)
        self.logs_thread.start()
    
    def _append_log_line(self, line: str):
        """Append log line with ANSI color support"""
        # Parse ANSI escape codes for colors
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Remove ANSI codes and extract colors
        ansi_pattern = re.compile(r'\x1b\[([0-9;]+)m')
        
        current_format = QTextCharFormat()
        current_format.setForeground(QColor(212, 212, 212))  # Default color
        
        last_pos = 0
        for match in ansi_pattern.finditer(line):
            # Insert text before this code
            if match.start() > last_pos:
                text = line[last_pos:match.start()]
                cursor.insertText(text, current_format)
            
            # Parse color code
            codes = match.group(1).split(';')
            for code in codes:
                if code == '0':  # Reset
                    current_format.setForeground(QColor(212, 212, 212))
                elif code in self.ansi_colors:
                    current_format.setForeground(self.ansi_colors[code])
            
            last_pos = match.end()
        
        # Insert remaining text
        if last_pos < len(line):
            text = line[last_pos:]
            cursor.insertText(text, current_format)
        
        # Add newline
        cursor.insertText('\n', current_format)
        
        # Auto-scroll if enabled
        if self.auto_scroll:
            scrollbar = self.logs_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_wrap_logs_changed(self, state):
        """Handle wrap logs checkbox change"""
        if state == Qt.CheckState.Checked.value:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    
    def _on_auto_scroll_changed(self, state):
        """Handle auto-scroll checkbox change"""
        self.auto_scroll = (state == Qt.CheckState.Checked.value)
    
    def _clear_logs(self):
        """Clear logs display"""
        self.logs_text.clear()
    
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
        
        event.accept()

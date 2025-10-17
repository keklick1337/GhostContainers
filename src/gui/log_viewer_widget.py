"""
Common Log Viewer Widget with ANSI color support
Can be used for container logs, build logs, etc.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QCheckBox
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
import re
import logging

logger = logging.getLogger(__name__)


# ANSI color mapping (shared across all log viewers)
ANSI_COLORS = {
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


class LogViewerWidget(QWidget):
    """
    Reusable log viewer widget with ANSI color support
    Features:
    - ANSI color code parsing
    - Word wrap toggle
    - Auto-scroll toggle
    - Clear button
    - Dark theme
    """
    
    def __init__(self, parent=None, show_controls=True):
        """
        Initialize log viewer widget
        
        Args:
            parent: Parent widget
            show_controls: Show control buttons (wrap, auto-scroll, clear)
        """
        super().__init__(parent)
        self.auto_scroll = True
        self.show_controls = show_controls
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Control bar (optional)
        if self.show_controls:
            from ..localization import t
            
            controls_layout = QHBoxLayout()
            
            # Wrap logs checkbox
            self.wrap_logs_check = QCheckBox(t('labels.wrap_logs'))
            self.wrap_logs_check.setChecked(True)  # Enable by default
            self.wrap_logs_check.stateChanged.connect(self._on_wrap_logs_changed)
            controls_layout.addWidget(self.wrap_logs_check)
            
            # Auto-scroll checkbox
            self.auto_scroll_check = QCheckBox(t('labels.auto_scroll'))
            self.auto_scroll_check.setChecked(True)
            self.auto_scroll_check.stateChanged.connect(self._on_auto_scroll_changed)
            controls_layout.addWidget(self.auto_scroll_check)
            
            controls_layout.addStretch()
            
            # Clear button
            clear_btn = QPushButton("🗑️ " + t('buttons.clear'))
            clear_btn.clicked.connect(self.clear)
            controls_layout.addWidget(clear_btn)
            
            layout.addLayout(controls_layout)
        
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
    
    def append_line(self, line: str):
        """
        Append log line with ANSI color support
        
        Args:
            line: Log line (may contain ANSI escape codes)
        """
        # Parse ANSI escape codes for colors
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # ANSI pattern for color codes
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
                elif code in ANSI_COLORS:
                    current_format.setForeground(ANSI_COLORS[code])
            
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
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
    
    def append_text(self, text: str):
        """
        Append plain text without processing ANSI codes
        
        Args:
            text: Plain text to append
        """
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        
        # Auto-scroll if enabled
        if self.auto_scroll:
            scrollbar = self.logs_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
    
    def clear(self):
        """Clear logs display"""
        self.logs_text.clear()
    
    def set_auto_scroll(self, enabled: bool):
        """Set auto-scroll enabled/disabled"""
        self.auto_scroll = enabled
        if self.show_controls:
            self.auto_scroll_check.setChecked(enabled)
    
    def set_wrap_mode(self, enabled: bool):
        """Set word wrap enabled/disabled"""
        if enabled:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        if self.show_controls:
            self.wrap_logs_check.setChecked(enabled)
    
    def _on_wrap_logs_changed(self, state):
        """Handle wrap logs checkbox change"""
        if state == Qt.CheckState.Checked.value:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.logs_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    
    def _on_auto_scroll_changed(self, state):
        """Handle auto-scroll checkbox change"""
        self.auto_scroll = (state == Qt.CheckState.Checked.value)


class ContainerLogsReaderThread(QThread):
    """Thread for reading container logs in real-time"""
    
    log_line = pyqtSignal(str)  # Emits each log line
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, docker_manager, container_id, follow=True, tail='all'):
        super().__init__()
        self.docker_manager = docker_manager
        self.container_id = container_id
        self.follow = follow
        self.tail = tail
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
                timestamps=False,
                tail=self.tail
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
                
                except TimeoutError:
                    # Timeout is normal when following logs with no output
                    continue
                except Exception as e:
                    # Only log real errors, not timeouts
                    if 'timed out' not in str(e).lower():
                        logger.error(f"Error reading log line: {e}")
                    break
            
            self.finished_signal.emit(True, "Logs stream ended")
            
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            self.finished_signal.emit(False, f"Error: {e}")
    
    def stop(self):
        """Stop reading logs"""
        self.running = False

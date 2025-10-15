"""
Text Editor Plugin
"""

import sys
import os
from typing import Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from plugin_system import FileViewerPlugin
from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget, QMenuBar, QMenu, QMessageBox
from PyQt6.QtGui import QAction, QFont, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QRegularExpression
import logging

logger = logging.getLogger(__name__)


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """Simple Python syntax highlighter"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#CC7832"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = [
            'def', 'class', 'import', 'from', 'if', 'else', 'elif',
            'for', 'while', 'return', 'try', 'except', 'finally',
            'with', 'as', 'pass', 'break', 'continue', 'True', 'False',
            'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield'
        ]
        
        self.highlighting_rules = []
        for keyword in keywords:
            pattern = QRegularExpression(f'\\b{keyword}\\b')
            self.highlighting_rules.append((pattern, keyword_format))
        
        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#6A8759"))
        self.highlighting_rules.append((QRegularExpression('"[^"]*"'), string_format))
        self.highlighting_rules.append((QRegularExpression("'[^']*'"), string_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression('#[^\n]*'), comment_format))
        
    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class EditorWindow(QMainWindow):
    """Editor window for editing files"""
    
    def __init__(self, container_name: str, file_path: str, content: bytes, callback=None):
        super().__init__()
        self.container_name = container_name
        self.file_path = file_path
        self.original_content = content
        self.save_callback = callback
        self.modified = False
        
        self.setWindowTitle(f"Edit: {container_name}:{file_path}")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Monaco", 12))
        
        # Try to decode content
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text_content = content.decode('latin-1')
            except:
                text_content = str(content)
        
        self.text_edit.setPlainText(text_content)
        self.text_edit.textChanged.connect(self._on_text_changed)
        
        # Syntax highlighting for Python files
        if file_path.endswith('.py'):
            self.highlighter = PythonSyntaxHighlighter(self.text_edit.document())
        
        layout.addWidget(self.text_edit)
        
        # Menu bar
        self._create_menu()
        
    def _create_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        file_menu.addAction(save_action)
        
        close_action = QAction("Close", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.text_edit.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.triggered.connect(self.text_edit.redo)
        edit_menu.addAction(redo_action)
        
    def _on_text_changed(self):
        self.modified = True
        self.setWindowTitle(f"*Edit: {self.container_name}:{self.file_path}")
        
    def _save(self):
        if self.save_callback:
            content = self.text_edit.toPlainText().encode('utf-8')
            success = self.save_callback(self.container_name, self.file_path, content)
            if success:
                self.modified = False
                self.setWindowTitle(f"Edit: {self.container_name}:{self.file_path}")
                QMessageBox.information(self, "Saved", "File saved successfully")
            else:
                QMessageBox.critical(self, "Error", "Failed to save file")
                
    def closeEvent(self, event):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "File has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


class TextEditorPlugin(FileViewerPlugin):
    """Plugin for editing text files"""
    
    def __init__(self):
        super().__init__()
        self.name = "Text Editor"
        self.version = "1.0.0"
        self.description = "Edit text files from containers"
        self.author = "GhostContainers"
        self.app_context = None
        self.editor_windows = []
        
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """Initialize plugin"""
        self.app_context = app_context
        logger.info("Text Editor plugin initialized")
        return True
        
    def get_info(self) -> Dict[str, str]:
        """Get plugin info"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author
        }
        
    def can_handle(self, file_path: str, mime_type: Optional[str] = None) -> bool:
        """Check if can handle file"""
        text_extensions = [
            '.txt', '.py', '.js', '.json', '.xml', '.html', '.css',
            '.md', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
            '.sh', '.bash', '.zsh', '.c', '.cpp', '.h', '.java',
            '.go', '.rs', '.rb', '.php', '.pl', '.lua', '.sql'
        ]
        
        return any(file_path.lower().endswith(ext) for ext in text_extensions)
        
    def view_file(self, container_name: str, file_path: str, content: bytes) -> Any:
        """View file (opens in editor)"""
        return self.edit_file(container_name, file_path, content)
        
    def edit_file(self, container_name: str, file_path: str, content: bytes) -> Optional[bytes]:
        """Edit file"""
        def save_callback(container, path, new_content):
            # Call docker_manager to save file
            if self.app_context and 'file_browser' in self.app_context:
                file_browser = self.app_context['file_browser']
                return file_browser.write_file(container, path, new_content.decode('utf-8'))
            return False
            
        window = EditorWindow(container_name, file_path, content, save_callback)
        window.show()
        self.editor_windows.append(window)
        return None
        
    def get_priority(self) -> int:
        """Priority for text files"""
        return 70
        
    def shutdown(self):
        """Cleanup"""
        for window in self.editor_windows:
            window.close()
        self.editor_windows.clear()

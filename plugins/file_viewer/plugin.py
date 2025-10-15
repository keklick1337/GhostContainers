"""
File Viewer Plugin for GhostContainers
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from plugin_system import FileViewerPlugin as BaseFileViewerPlugin
from PyQt6.QtWidgets import (QMainWindow, QLabel, QVBoxLayout, QWidget, 
                              QScrollArea, QTextEdit, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional
import logging
import tarfile
import zipfile
import io

logger = logging.getLogger(__name__)


class ImageViewerWindow(QMainWindow):
    """Window for viewing images"""
    
    def __init__(self, container_name: str, file_path: str, content: bytes):
        super().__init__()
        self.setWindowTitle(f"Image: {container_name}:{file_path}")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget with scroll area
        scroll_area = QScrollArea()
        self.setCentralWidget(scroll_area)
        
        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load image from bytes
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            # Scale to fit if too large
            if pixmap.width() > 1200 or pixmap.height() > 900:
                pixmap = pixmap.scaled(1200, 900, Qt.AspectRatioMode.KeepAspectRatio, 
                                      Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(pixmap)
        else:
            image_label.setText("Failed to load image")
        
        scroll_area.setWidget(image_label)


class ArchiveViewerWindow(QMainWindow):
    """Window for browsing archive contents"""
    
    def __init__(self, container_name: str, file_path: str, content: bytes):
        super().__init__()
        self.setWindowTitle(f"Archive: {container_name}:{file_path}")
        self.setGeometry(100, 100, 600, 500)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Tree widget for archive contents
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Size", "Type"])
        self.tree.setColumnWidth(0, 300)
        layout.addWidget(self.tree)
        
        # Parse archive based on extension
        self._load_archive(file_path, content)
        
    def _load_archive(self, file_path: str, content: bytes):
        """Load and display archive contents"""
        try:
            if file_path.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2')):
                self._load_tar(content)
            elif file_path.endswith('.zip'):
                self._load_zip(content)
            else:
                item = QTreeWidgetItem(["Unknown archive format", "", ""])
                self.tree.addTopLevelItem(item)
        except Exception as e:
            logger.error(f"Failed to load archive: {e}")
            item = QTreeWidgetItem([f"Error: {str(e)}", "", ""])
            self.tree.addTopLevelItem(item)
    
    def _load_tar(self, content: bytes):
        """Load tar archive contents"""
        with tarfile.open(fileobj=io.BytesIO(content)) as tar:
            for member in tar.getmembers():
                file_type = "Dir" if member.isdir() else "File"
                size = str(member.size) if member.isfile() else ""
                item = QTreeWidgetItem([member.name, size, file_type])
                self.tree.addTopLevelItem(item)
    
    def _load_zip(self, content: bytes):
        """Load zip archive contents"""
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                file_type = "Dir" if info.is_dir() else "File"
                size = str(info.file_size) if not info.is_dir() else ""
                item = QTreeWidgetItem([info.filename, size, file_type])
                self.tree.addTopLevelItem(item)


class HexViewerWindow(QMainWindow):
    """Window for viewing binary files in hex"""
    
    def __init__(self, container_name: str, file_path: str, content: bytes):
        super().__init__()
        self.setWindowTitle(f"Hex Viewer: {container_name}:{file_path}")
        self.setGeometry(100, 100, 900, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Text editor for hex display
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Monaco", 10))
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        # Format as hex dump
        self._display_hex(content)
    
    def _display_hex(self, content: bytes):
        """Display binary content as hex dump"""
        lines = []
        max_bytes = min(len(content), 10000)  # Limit to first 10KB for performance
        
        for i in range(0, max_bytes, 16):
            chunk = content[i:i+16]
            
            # Offset
            offset = f"{i:08x}"
            
            # Hex bytes
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            hex_part = hex_part.ljust(48)  # Pad to 16 bytes worth
            
            # ASCII representation
            ascii_part = "".join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            
            lines.append(f"{offset}  {hex_part}  {ascii_part}")
        
        if len(content) > max_bytes:
            lines.append(f"\n... ({len(content) - max_bytes} more bytes)")
        
        self.text_edit.setPlainText("\n".join(lines))


class FileViewerPlugin(BaseFileViewerPlugin):
    """Plugin for viewing various file types"""
    
    def __init__(self):
        super().__init__()
        self.name = "File Viewer"
        self.version = "1.0.0"
        self.description = "View images, archives, and binary files"
        self.author = "GhostContainers"
        self.app_context = None
        self.viewer_windows = []
        
    def initialize(self, app_context: Dict[str, Any]) -> bool:
        """Initialize plugin"""
        self.app_context = app_context
        logger.info("File Viewer plugin initialized")
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
        # Image files
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico']
        
        # Archive files
        archive_extensions = ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.zip', '.gz']
        
        # PDF files (basic support)
        pdf_extensions = ['.pdf']
        
        file_lower = file_path.lower()
        
        return (any(file_lower.endswith(ext) for ext in image_extensions) or
                any(file_lower.endswith(ext) for ext in archive_extensions) or
                any(file_lower.endswith(ext) for ext in pdf_extensions))
        
    def view_file(self, container_name: str, file_path: str, content: bytes) -> Any:
        """View file"""
        file_lower = file_path.lower()
        
        # Determine file type and create appropriate viewer
        if any(file_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico']):
            window = ImageViewerWindow(container_name, file_path, content)
        elif any(file_lower.endswith(ext) for ext in ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.zip']):
            window = ArchiveViewerWindow(container_name, file_path, content)
        elif file_lower.endswith('.pdf'):
            # For PDF, show hex viewer for now (PDF rendering requires additional dependencies)
            window = HexViewerWindow(container_name, file_path, content)
        else:
            # Default to hex viewer
            window = HexViewerWindow(container_name, file_path, content)
        
        window.show()
        self.viewer_windows.append(window)
        return window
        
    def edit_file(self, container_name: str, file_path: str, content: bytes) -> Optional[bytes]:
        """Not editable - view only"""
        return None
        
    def get_priority(self) -> int:
        """Priority for file types"""
        return 60  # Lower than text editor (70) for text files
        
    def shutdown(self):
        """Cleanup"""
        for window in self.viewer_windows:
            window.close()
        self.viewer_windows.clear()

"""
File Browser Plugin
Provides file management interface for containers
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QFileDialog, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.plugin_api import TabPlugin
from src.localization import t


class FileBrowserPlugin(TabPlugin):
    """File browser and manager plugin"""
    
    def __init__(self):
        super().__init__()
        self.name = "File Browser"
        self.version = "2.0.0"
        self.description = "Browse and manage files in containers"
        self.author = "GhostContainers Team"
        
        self.tab_widget = None
        self.file_container_combo = None
        self.file_path_edit = None
        self.files_tree = None
        
        # Register for container updates hook
        self.register_hook('HOOK_CONTAINERS_UPDATED', self.update_containers)
    
    def get_tab_title(self) -> str:
        return t('tabs.files')
    
    def create_tab_widget(self) -> QWidget:
        """Create the file browser tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Container selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel(t('labels.container') + ":"))
        
        self.file_container_combo = QComboBox()
        selector_layout.addWidget(self.file_container_combo)
        
        browse_btn = QPushButton(t('buttons.browse'))
        browse_btn.clicked.connect(self.browse_files)
        selector_layout.addWidget(browse_btn)
        
        upload_btn = QPushButton("⬆ " + t('labels.upload_file'))
        upload_btn.clicked.connect(self.upload_file)
        selector_layout.addWidget(upload_btn)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(t('labels.path') + ":"))
        
        self.file_path_edit = QLineEdit("/")
        self.file_path_edit.returnPressed.connect(self.browse_files)
        path_layout.addWidget(self.file_path_edit)
        
        layout.addLayout(path_layout)
        
        # Files tree
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels([
            t('labels.name'),
            t('labels.type'),
            t('labels.size'),
            t('labels.permissions')
        ])
        self.files_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tree.customContextMenuRequested.connect(self._show_file_context_menu)
        self.files_tree.itemDoubleClicked.connect(self._file_double_click)
        layout.addWidget(self.files_tree)
        
        self.tab_widget = widget
        return widget
    
    def update_containers(self, containers):
        """Update container list"""
        if not self.file_container_combo:
            return
            
        self.file_container_combo.clear()
        running = [c['name'] for c in containers if c['status'] == 'running']
        self.file_container_combo.addItems(running)
    
    def refresh(self):
        """Refresh file list"""
        self.browse_files()
    
    def browse_files(self):
        """Browse container files"""
        if not self.file_container_combo:
            return
            
        container = self.file_container_combo.currentText()
        if not container:
            QMessageBox.warning(self.tab_widget, t('dialogs.warning_title'), 
                              t('messages.select_container'))
            return
        
        path = self.file_path_edit.text()
        files = self.file_browser.list_files(container, path)
        
        if files is None:
            QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                               t('messages.failed_read_directory').format(path=path))
            return
        
        self.files_tree.clear()
        
        # Add parent directory entry if not root
        if path != '/':
            parent_item = QTreeWidgetItem(['..', 'd', '', ''])
            parent_item.setForeground(0, QColor('#8be9fd'))
            self.files_tree.addTopLevelItem(parent_item)
        
        for file in files:
            item = QTreeWidgetItem([
                file['name'],
                file['type'],
                file['size'],
                file['permissions']
            ])
            if file['type'] == 'd' or file['type'] == 'directory':
                item.setForeground(0, QColor('#50fa7b'))
            self.files_tree.addTopLevelItem(item)
    
    def _file_double_click(self, item, column):
        """Handle file double-click"""
        name = item.text(0)
        file_type = item.text(1)
        
        if file_type == 'd' or file_type == 'directory':
            current_path = self.file_path_edit.text()
            
            if name == '..':
                new_path = '/'.join(current_path.rstrip('/').split('/')[:-1])
                if not new_path:
                    new_path = '/'
            else:
                new_path = current_path.rstrip('/') + '/' + name
            
            self.file_path_edit.setText(new_path)
            self.browse_files()
    
    def _show_file_context_menu(self, position):
        """Show context menu for file operations"""
        item = self.files_tree.itemAt(position)
        if not item:
            return
        
        filename = item.text(0)
        file_type = item.text(1)
        
        if filename == '..':
            return
        
        menu = QMenu(self.tab_widget)
        
        # File-specific actions
        if file_type == 'f' or file_type == 'file' or file_type == '-':
            open_action = menu.addAction("📄 " + t('context_menu.open_in_editor'))
            open_action.triggered.connect(lambda: self._open_file_in_editor(filename))
            
            download_action = menu.addAction("⬇ " + t('context_menu.download'))
            download_action.triggered.connect(lambda: self._download_file(filename))
        
        delete_action = menu.addAction("🗑 " + t('context_menu.delete'))
        delete_action.triggered.connect(lambda: self._delete_file(filename))
        
        menu.exec(self.files_tree.viewport().mapToGlobal(position))
    
    def _open_file_in_editor(self, filename):
        """Open file in text editor plugin"""
        container = self.file_container_combo.currentText()
        if not container:
            return
        
        path = self.file_path_edit.text().rstrip('/') + '/' + filename
        
        # Get plugin manager from main window
        plugin_manager = getattr(self.main_window, 'plugin_manager', None)
        if not plugin_manager:
            return
        
        # Find text editor plugin
        text_editor_plugin = None
        for plugin in plugin_manager.file_viewers:
            if hasattr(plugin, 'name') and 'Text Editor' in plugin.name:
                text_editor_plugin = plugin
                break
        
        if text_editor_plugin:
            try:
                text_editor_plugin.view_file(container, path)
            except Exception as e:
                QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                   t('messages.text_editor_not_available'))
        else:
            QMessageBox.warning(self.tab_widget, t('dialogs.warning_title'), 
                              t('messages.text_editor_not_available'))
    
    def _download_file(self, filename):
        """Download file from container"""
        container = self.file_container_combo.currentText()
        if not container:
            return
        
        container_path = self.file_path_edit.text().rstrip('/') + '/' + filename
        
        save_path, _ = QFileDialog.getSaveFileName(
            self.tab_widget,
            t('dialogs.save_file'),
            filename,
            t('messages.all_files')
        )
        
        if save_path:
            try:
                content = self.file_browser.read_file(container, container_path)
                if content:
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    QMessageBox.information(self.tab_widget, t('dialogs.success_title'), 
                                          t('messages.file_downloaded').format(path=save_path))
                else:
                    QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                       t('messages.failed_read_file'))
            except Exception as e:
                QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                   t('messages.failed_download_file').format(error=str(e)))
    
    def _delete_file(self, filename):
        """Delete file from container"""
        container = self.file_container_combo.currentText()
        if not container:
            return
        
        reply = QMessageBox.question(
            self.tab_widget,
            t('dialogs.confirm_delete_title'),
            t('dialogs.confirm_delete_file').format(filename=filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            path = self.file_path_edit.text().rstrip('/') + '/' + filename
            
            try:
                result = self.docker_manager.execute_command(
                    container,
                    f"rm -rf '{path}'",
                    user='root'
                )
                
                if result:
                    QMessageBox.information(self.tab_widget, t('dialogs.success_title'), 
                                          t('messages.file_deleted').format(filename=filename))
                    self.browse_files()
                else:
                    QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                       t('messages.failed_delete_file'))
            except Exception as e:
                QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                   t('messages.failed_delete_file').format(error=str(e)))
    
    def upload_file(self):
        """Upload file to container"""
        container = self.file_container_combo.currentText()
        if not container:
            QMessageBox.warning(self.tab_widget, t('dialogs.warning_title'), 
                              t('messages.select_container'))
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.tab_widget,
            t('dialogs.select_file_upload'),
            "",
            t('messages.all_files')
        )
        
        if file_path:
            try:
                current_path = self.file_path_edit.text()
                filename = os.path.basename(file_path)
                container_path = current_path.rstrip('/') + '/' + filename
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                if self.file_browser.write_file(container, container_path, content):
                    QMessageBox.information(self.tab_widget, t('dialogs.success_title'), 
                                          t('messages.file_uploaded').format(filename=filename))
                    self.browse_files()
                else:
                    QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                       t('messages.failed_upload_file'))
            except Exception as e:
                QMessageBox.critical(self.tab_widget, t('dialogs.error_title'), 
                                   t('messages.failed_upload_file').format(error=str(e)))

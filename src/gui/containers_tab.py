"""
Containers Tab Widget
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QCheckBox, QHeaderView, QMessageBox
)
from PyQt6.QtGui import QColor

from ..localization import t


class ContainersTab(QWidget):
    """Containers management tab"""
    
    def __init__(self, parent, docker_manager):
        super().__init__(parent)
        self.parent_window = parent
        self.docker_manager = docker_manager
        self.toolbar_layout = None  # Will store toolbar reference
        
        self._create_ui()
    
    def _create_ui(self):
        """Create containers tab UI"""
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.toolbar_layout = toolbar  # Store reference
        
        create_btn = QPushButton(t('buttons.create'))
        create_btn.clicked.connect(self.parent_window.create_container)
        toolbar.addWidget(create_btn)
        
        start_btn = QPushButton(t('buttons.start'))
        start_btn.clicked.connect(self.parent_window.start_container)
        toolbar.addWidget(start_btn)
        
        stop_btn = QPushButton(t('buttons.stop'))
        stop_btn.clicked.connect(self.parent_window.stop_container)
        toolbar.addWidget(stop_btn)
        
        remove_btn = QPushButton(t('buttons.remove'))
        remove_btn.clicked.connect(self.parent_window.remove_container)
        toolbar.addWidget(remove_btn)
        
        toolbar.addWidget(QLabel("|"))
        
        shell_btn = QPushButton(t('labels.shell_user'))
        shell_btn.clicked.connect(lambda: self.parent_window.open_shell('user'))
        toolbar.addWidget(shell_btn)
        
        shell_root_btn = QPushButton(t('labels.shell_root'))
        shell_root_btn.clicked.connect(lambda: self.parent_window.open_shell('root'))
        toolbar.addWidget(shell_root_btn)
        
        gui_btn = QPushButton(t('labels.run_gui_app'))
        gui_btn.clicked.connect(self.parent_window.run_gui_app)
        toolbar.addWidget(gui_btn)
        
        toolbar.addStretch()
        
        # Show all checkbox
        self.show_all_check = QCheckBox(t('labels.show_all_containers'))
        self.show_all_check.stateChanged.connect(self.parent_window.refresh_containers)
        toolbar.addWidget(self.show_all_check)
        
        refresh_btn = QPushButton(t('buttons.refresh'))
        refresh_btn.clicked.connect(self.parent_window.refresh_containers)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.containers_table = QTableWidget()
        self.containers_table.setColumnCount(6)
        self.containers_table.setHorizontalHeaderLabels([
            t('labels.name'),
            t('labels.status'),
            t('labels.network'),
            t('labels.image'),
            t('labels.id'),
            '📍 ' + t('labels.tracked')
        ])
        
        header = self.containers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.containers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.containers_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        layout.addWidget(self.containers_table)
    
    def refresh(self, containers):
        """Refresh containers table"""
        self.containers_table.setRowCount(len(containers))
        
        for row, container in enumerate(containers):
            # Name
            name_item = QTableWidgetItem(container['name'])
            self.containers_table.setItem(row, 0, name_item)
            
            # Status
            status = container['status']
            status_item = QTableWidgetItem(status)
            if status == 'running':
                status_item.setForeground(QColor('#50fa7b'))
            elif status in ['exited', 'stopped']:
                status_item.setForeground(QColor('#ff5555'))
            self.containers_table.setItem(row, 1, status_item)
            
            # Network
            network = container.get('network', ['bridge'])
            if isinstance(network, list):
                network = ', '.join(network[:2])
            network_item = QTableWidgetItem(str(network))
            self.containers_table.setItem(row, 2, network_item)
            
            # Image
            image_item = QTableWidgetItem(container['image'])
            self.containers_table.setItem(row, 3, image_item)
            
            # ID
            id_item = QTableWidgetItem(container['id'])
            self.containers_table.setItem(row, 4, id_item)
            
            # Tracked
            tracked = '✓' if container.get('tracked', False) else ''
            tracked_item = QTableWidgetItem(tracked)
            self.containers_table.setItem(row, 5, tracked_item)
    
    def get_selected_container(self) -> Optional[str]:
        """Get selected container name"""
        row = self.containers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, t('dialogs.warning_title'), t('messages.select_container'))
            return None
        
        name_item = self.containers_table.item(row, 0)
        return name_item.text() if name_item else None
    
    def update_container_status(self, container_name: str, status: str, color: Optional[str] = None):
        """Update status of specific container in table"""
        for row in range(self.containers_table.rowCount()):
            name_item = self.containers_table.item(row, 0)
            if name_item and name_item.text() == container_name:
                status_item = self.containers_table.item(row, 1)
                if status_item:
                    status_item.setText(status)
                    if color:
                        status_item.setForeground(QColor(color))
                break
    
    def set_buttons_enabled(self, enabled: bool):
        """Enable/disable all operation buttons"""
        # Use stored toolbar reference to find buttons
        if self.toolbar_layout:
            for i in range(self.toolbar_layout.count()):
                widget = self.toolbar_layout.itemAt(i).widget()
                if widget and isinstance(widget, QPushButton):
                    widget.setEnabled(enabled)

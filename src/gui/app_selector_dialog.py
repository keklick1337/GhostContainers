"""
GUI App Selector Dialog
Select and manage GUI applications for containers
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QInputDialog, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class AppSelectorDialog(QDialog):
    """Dialog for selecting GUI application to run"""
    
    def __init__(self, parent, docker_manager, template_manager, db, container_name):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.template_manager = template_manager
        self.db = db
        self.container_name = container_name
        self.selected_app = None
        
        self.setWindowTitle(f"Run GUI App - {container_name}")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel("Select an application to run:")
        layout.addWidget(info_label)
        
        # Apps table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Application", "Command", "Source"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self._run_selected)
        layout.addWidget(self.table)
        
        # Custom apps controls
        custom_layout = QHBoxLayout()
        
        add_custom_btn = QPushButton("➕ Add Custom App")
        add_custom_btn.clicked.connect(self._add_custom_app)
        custom_layout.addWidget(add_custom_btn)
        
        self.remove_custom_btn = QPushButton("➖ Remove Custom App")
        self.remove_custom_btn.clicked.connect(self._remove_custom_app)
        self.remove_custom_btn.setEnabled(False)
        custom_layout.addWidget(self.remove_custom_btn)
        
        custom_layout.addStretch()
        layout.addLayout(custom_layout)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        run_btn = QPushButton("▶️ Run")
        run_btn.setDefault(True)
        run_btn.clicked.connect(self._run_selected)
        buttons_layout.addWidget(run_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # Load apps
        self._load_apps()
        
        # Connect selection change
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_apps(self):
        """Load apps from template config and custom apps from database"""
        self.table.setRowCount(0)
        
        # Get container info to find template
        try:
            container = self.docker_manager.get_container(self.container_name)
            if not container:
                return
            
            # Try to get template from container labels
            labels = container.get('labels', {})
            template_id = labels.get('template')
            
            # Load template apps
            template_apps = []
            if template_id:
                template = self.template_manager.get_template(template_id)
                if template:
                    import os
                    import json
                    config_path = os.path.join(template['path'], 'config.json')
                    try:
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                        template_apps = config.get('apps', [])
                    except:
                        pass
            
            # Load custom apps from database
            custom_apps = self.db.get_container_apps(self.container_name)
            
            # Combine and display
            row = 0
            
            # Add template apps
            for app in template_apps:
                self.table.insertRow(row)
                
                name_item = QTableWidgetItem(app.get('name', ''))
                name_item.setBackground(QColor(240, 248, 255))  # Light blue for template apps
                name_item.setData(Qt.ItemDataRole.UserRole, app.get('command', ''))
                self.table.setItem(row, 0, name_item)
                
                self.table.setItem(row, 1, QTableWidgetItem(app.get('command', '')))
                
                source_item = QTableWidgetItem("Template")
                source_item.setForeground(QColor(100, 100, 100))
                self.table.setItem(row, 2, source_item)
                
                row += 1
            
            # Add custom apps
            for app in custom_apps:
                self.table.insertRow(row)
                
                name_item = QTableWidgetItem(app['name'])
                name_item.setBackground(QColor(255, 248, 240))  # Light orange for custom apps
                name_item.setData(Qt.ItemDataRole.UserRole, app['command'])
                self.table.setItem(row, 0, name_item)
                
                self.table.setItem(row, 1, QTableWidgetItem(app['command']))
                
                source_item = QTableWidgetItem("Custom")
                source_item.setForeground(QColor(255, 140, 0))
                self.table.setItem(row, 2, source_item)
                
                row += 1
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load apps: {str(e)}")
    
    def _on_selection_changed(self):
        """Handle selection change"""
        selected_rows = self.table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            source = self.table.item(row, 2).text()
            self.remove_custom_btn.setEnabled(source == "Custom")
        else:
            self.remove_custom_btn.setEnabled(False)
    
    def _add_custom_app(self):
        """Add custom application"""
        # Get app name
        name, ok = QInputDialog.getText(
            self,
            "Add Custom App",
            "Application name:"
        )
        
        if not ok or not name.strip():
            return
        
        # Get app command
        command, ok = QInputDialog.getText(
            self,
            "Add Custom App",
            "Application command:",
            text="firefox"
        )
        
        if not ok or not command.strip():
            return
        
        # Save to database
        if self.db.add_container_app(self.container_name, name.strip(), command.strip()):
            QMessageBox.information(self, "Success", "Custom app added successfully")
            self._load_apps()
        else:
            QMessageBox.critical(self, "Error", "Failed to add custom app")
    
    def _remove_custom_app(self):
        """Remove custom application"""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        source = self.table.item(row, 2).text()
        
        if source != "Custom":
            QMessageBox.warning(self, "Warning", "Can only remove custom apps")
            return
        
        app_name = self.table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Remove custom app '{app_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.remove_container_app(self.container_name, app_name):
                QMessageBox.information(self, "Success", "Custom app removed successfully")
                self._load_apps()
            else:
                QMessageBox.critical(self, "Error", "Failed to remove custom app")
    
    def _run_selected(self):
        """Run selected application"""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select an application")
            return
        
        row = selected_rows[0].row()
        name_item = self.table.item(row, 0)
        
        # Get command from UserRole data
        command = name_item.data(Qt.ItemDataRole.UserRole)
        
        if command:
            self.selected_app = {
                'name': name_item.text(),
                'command': command
            }
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Invalid application command")
    
    def get_selected_app(self):
        """Get selected application"""
        return self.selected_app

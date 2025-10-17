"""
Settings Dialog for GhostContainers
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QLineEdit,
    QPushButton, QGroupBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import logging

from ..localization import t
from ..settings_manager import SettingsManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog window"""
    
    settings_changed = pyqtSignal()  # Emitted when settings are saved
    
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        
        self.setWindowTitle(t('settings.title'))
        self.setMinimumWidth(500)
        self.setModal(True)
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout()
        
        # General settings
        general_group = QGroupBox(t('settings.general'))
        general_layout = QFormLayout()
        
        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItem('English', 'en')
        self.language_combo.addItem('Русский', 'ru')
        general_layout.addRow(
            t('settings.language') + ':',
            self.language_combo
        )
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(t('settings.theme_system'), 'system')
        self.theme_combo.addItem(t('settings.theme_light'), 'light')
        self.theme_combo.addItem(t('settings.theme_dark'), 'dark')
        general_layout.addRow(
            t('settings.theme') + ':',
            self.theme_combo
        )
        
        # Auto-refresh interval
        self.refresh_spinbox = QSpinBox()
        self.refresh_spinbox.setMinimum(1)
        self.refresh_spinbox.setMaximum(60)
        self.refresh_spinbox.setSuffix(' ' + t('settings.seconds'))
        general_layout.addRow(
            t('settings.refresh_interval') + ':',
            self.refresh_spinbox
        )
        
        # Show all containers by default
        self.show_all_checkbox = QCheckBox(
            t('settings.show_all_containers')
        )
        general_layout.addRow('', self.show_all_checkbox)
        
        # Show success messages
        self.show_success_checkbox = QCheckBox(
            "Show success message boxes"
        )
        general_layout.addRow('', self.show_success_checkbox)
        
        # Show logs window (for API mode)
        self.show_logs_checkbox = QCheckBox(
            "Show logs window (API mode)"
        )
        general_layout.addRow('', self.show_logs_checkbox)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # Container launch settings
        launch_group = QGroupBox(t('settings.container_launch'))
        launch_layout = QFormLayout()
        
        # Launch mode
        self.launch_mode_combo = QComboBox()
        self.launch_mode_combo.addItem(
            t('settings.launch_terminal'),
            'terminal'
        )
        self.launch_mode_combo.addItem(
            t('settings.launch_api'),
            'api'
        )
        self.launch_mode_combo.addItem(
            t('settings.launch_custom'),
            'custom'
        )
        self.launch_mode_combo.currentIndexChanged.connect(self.on_launch_mode_changed)
        launch_layout.addRow(
            t('settings.launch_mode') + ':',
            self.launch_mode_combo
        )
        
        # Custom terminal command
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText(
            t('settings.custom_command_placeholder')
        )
        self.custom_command_label = QLabel(
            t('settings.custom_command') + ':'
        )
        launch_layout.addRow(self.custom_command_label, self.custom_command_edit)
        
        # Help text for custom command
        help_text = QLabel(
            t('settings.custom_command_help')
        )
        help_text.setStyleSheet('color: gray; font-size: 10px;')
        help_text.setWordWrap(True)
        launch_layout.addRow('', help_text)
        
        launch_group.setLayout(launch_layout)
        layout.addWidget(launch_group)
        
        # Docker settings
        docker_group = QGroupBox(t('settings.docker'))
        docker_layout = QFormLayout()
        
        # Docker socket path
        self.socket_path_edit = QLineEdit()
        self.socket_path_edit.setPlaceholderText(
            t('settings.socket_placeholder')
        )
        docker_layout.addRow(
            t('settings.socket_path') + ':',
            self.socket_path_edit
        )
        
        docker_group.setLayout(docker_layout)
        layout.addWidget(docker_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton(t('settings.reset'))
        self.reset_button.clicked.connect(self.on_reset)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QPushButton(t('settings.cancel'))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton(t('settings.save'))
        self.save_button.clicked.connect(self.on_save)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Update UI state
        self.on_launch_mode_changed()
    
    def load_settings(self):
        """Load current settings into UI"""
        settings = self.settings_manager.get_all()
        
        # Language
        lang = settings.get('language', 'en')
        index = self.language_combo.findData(lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        
        # Theme
        theme = settings.get('theme', 'system')
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        
        # Refresh interval
        refresh = settings.get('auto_refresh_interval', 5)
        self.refresh_spinbox.setValue(refresh)
        
        # Show all containers
        show_all = settings.get('show_all_containers_default', False)
        self.show_all_checkbox.setChecked(show_all)
        
        # Show success messages
        show_success = settings.get('show_success_messages', True)
        self.show_success_checkbox.setChecked(show_success)
        
        # Show logs window
        show_logs = settings.get('show_logs_window', True)
        self.show_logs_checkbox.setChecked(show_logs)
        
        # Launch mode
        launch_mode = settings.get('launch_mode', 'api')
        index = self.launch_mode_combo.findData(launch_mode)
        if index >= 0:
            self.launch_mode_combo.setCurrentIndex(index)
        
        # Custom command
        custom_cmd = settings.get('custom_terminal_command', '')
        self.custom_command_edit.setText(custom_cmd)
        
        # Docker socket
        socket_path = settings.get('docker_socket_path', '')
        self.socket_path_edit.setText(socket_path)
    
    def on_launch_mode_changed(self):
        """Handle launch mode change"""
        mode = self.launch_mode_combo.currentData()
        is_custom = (mode == 'custom')
        
        self.custom_command_label.setEnabled(is_custom)
        self.custom_command_edit.setEnabled(is_custom)
    
    def on_save(self):
        """Save settings"""
        try:
            # Gather settings
            new_settings = {
                'language': self.language_combo.currentData(),
                'theme': self.theme_combo.currentData(),
                'auto_refresh_interval': self.refresh_spinbox.value(),
                'show_all_containers_default': self.show_all_checkbox.isChecked(),
                'show_success_messages': self.show_success_checkbox.isChecked(),
                'show_logs_window': self.show_logs_checkbox.isChecked(),
                'launch_mode': self.launch_mode_combo.currentData(),
                'custom_terminal_command': self.custom_command_edit.text().strip(),
                'docker_socket_path': self.socket_path_edit.text().strip(),
            }
            
            # Validate custom command if mode is custom
            if new_settings['launch_mode'] == 'custom':
                if not new_settings['custom_terminal_command']:
                    QMessageBox.warning(
                        self,
                        t('settings.error'),
                        t('settings.custom_command_required')
                    )
                    return
                
                if '{command}' not in new_settings['custom_terminal_command']:
                    QMessageBox.warning(
                        self,
                        t('settings.error'),
                        t('settings.custom_command_placeholder_required')
                    )
                    return
            
            # Save settings
            self.settings_manager.update(new_settings)
            
            # Show restart message if language changed
            old_lang = self.settings_manager.get('language')
            if old_lang != new_settings['language']:
                QMessageBox.information(
                    self,
                    t('settings.restart_required'),
                    t('settings.restart_message')
                )
            
            # Emit signal and close
            self.settings_changed.emit()
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self,
                t('settings.error'),
                t('settings.save_error', error=str(e))
            )
    
    def on_reset(self):
        """Reset to default settings"""
        reply = QMessageBox.question(
            self,
            t('settings.reset_confirm'),
            t('settings.reset_message'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.reset_to_defaults()
            self.load_settings()

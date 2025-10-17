"""
Container Creation Dialog
"""

import os
import json
import random
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QLabel, QProgressBar, QTextEdit,
    QDialogButtonBox, QMessageBox, QWidget, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..localization import t
from .threads import ContainerCreateThread
from .logs_window import ContainerLogsWindow
from ..settings_manager import SettingsManager
import subprocess
import platform as platform_module


class CreateContainerDialog(QDialog):
    """Container creation dialog with live log"""
    
    def __init__(self, parent, docker_manager, template_manager, network_manager, db):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.template_manager = template_manager
        self.network_manager = network_manager
        self.db = db
        self.create_thread = None
        
        self.setWindowTitle(t('dialogs.create_container'))
        self.setMinimumSize(700, 800)
        
        layout = QVBoxLayout(self)
        
        # Form
        form_layout = QFormLayout()
        
        # Template
        self.template_combo = QComboBox()
        templates = template_manager.list_templates()
        for tmpl in templates:
            self.template_combo.addItem(tmpl['name'], tmpl['id'])
        form_layout.addRow(t('labels.template') + ":", self.template_combo)
        
        # Name with generate button
        name_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        generate_name_btn = QPushButton("🔄")
        generate_name_btn.setMaximumWidth(40)
        generate_name_btn.setToolTip("Generate random name")
        generate_name_btn.clicked.connect(self._generate_random_name)
        name_layout.addWidget(generate_name_btn)
        form_layout.addRow(t('labels.name') + ":", name_layout)
        
        # Hostname with generate button
        hostname_layout = QHBoxLayout()
        self.hostname_edit = QLineEdit()
        hostname_layout.addWidget(self.hostname_edit)
        generate_hostname_btn = QPushButton("🔄")
        generate_hostname_btn.setMaximumWidth(40)
        generate_hostname_btn.setToolTip("Generate random hostname")
        generate_hostname_btn.clicked.connect(self._generate_random_hostname)
        hostname_layout.addWidget(generate_hostname_btn)
        form_layout.addRow(t('labels.hostname') + ":", hostname_layout)
        
        # User
        self.user_edit = QLineEdit("user")
        form_layout.addRow(t('labels.user') + ":", self.user_edit)
        
        # UID
        self.uid_spin = QSpinBox()
        self.uid_spin.setRange(1000, 65535)
        self.uid_spin.setValue(1000)
        form_layout.addRow(t('labels.uid') + ":", self.uid_spin)
        
        # Network
        network_layout = QHBoxLayout()
        self.network_combo = QComboBox()
        network_layout.addWidget(self.network_combo)
        
        self.show_all_networks = QCheckBox(t('labels.show_all'))
        self.show_all_networks.stateChanged.connect(self._load_networks)
        network_layout.addWidget(self.show_all_networks)
        
        self._load_networks()
        form_layout.addRow(t('labels.network') + ":", network_layout)
        
        # Tor Gateway
        self.tor_gateway_check = QCheckBox("🔒 " + t('labels.tor_gateway'))
        self.tor_gateway_check.stateChanged.connect(self._toggle_tor)
        form_layout.addRow("", self.tor_gateway_check)
        
        # Disposable
        self.disposable_check = QCheckBox(t('labels.disposable'))
        self.disposable_check.stateChanged.connect(self._toggle_disposable_options)
        form_layout.addRow("", self.disposable_check)
        
        # Startup command selector (always visible)
        startup_layout = QVBoxLayout()
        
        app_selector_layout = QHBoxLayout()
        app_selector_layout.addWidget(QLabel(t('labels.app_to_run') + ":"))
        self.startup_app_combo = QComboBox()
        self.startup_app_combo.addItem("Default", "default")
        self.startup_app_combo.addItem("Custom", "custom")
        self.startup_app_combo.currentIndexChanged.connect(self._on_startup_app_changed)
        app_selector_layout.addWidget(self.startup_app_combo)
        startup_layout.addLayout(app_selector_layout)
        
        # Custom command input (initially hidden)
        self.custom_command_edit = QLineEdit()
        self.custom_command_edit.setPlaceholderText("e.g., firefox, bash -c 'echo Hello'")
        self.custom_command_edit.setVisible(False)
        startup_layout.addWidget(self.custom_command_edit)
        
        self.external_terminal_check = QCheckBox(t('labels.external_terminal'))
        self.external_terminal_check.setChecked(False)  # Use settings launch_mode by default
        self.external_terminal_check.setVisible(False)
        startup_layout.addWidget(self.external_terminal_check)
        
        form_layout.addRow("", startup_layout)
        
        # Connect template change to update app list
        self.template_combo.currentIndexChanged.connect(self._update_startup_apps)
        
        # GUI Support
        self.gui_check = QCheckBox(t('labels.gui_support'))
        self.gui_check.setChecked(True)
        form_layout.addRow("", self.gui_check)
        
        # Launch mode selector (for disposable containers)
        launch_mode_layout = QVBoxLayout()
        
        launch_mode_label_layout = QHBoxLayout()
        launch_mode_label_layout.addWidget(QLabel("Launch Mode:"))
        self.launch_mode_combo = QComboBox()
        self.launch_mode_combo.addItem("API (with logs)", "api")
        self.launch_mode_combo.addItem("Terminal", "terminal")
        self.launch_mode_combo.addItem("Custom", "custom")
        
        # Load default from settings
        settings = SettingsManager()
        settings.load()
        default_mode = settings.get('launch_mode', 'api')
        index = self.launch_mode_combo.findData(default_mode)
        if index >= 0:
            self.launch_mode_combo.setCurrentIndex(index)
        
        launch_mode_label_layout.addWidget(self.launch_mode_combo)
        launch_mode_layout.addLayout(launch_mode_label_layout)
        
        # Show logs window checkbox (for API mode)
        self.show_logs_check = QCheckBox("Show logs window")
        self.show_logs_check.setChecked(settings.get('show_logs_window', True))
        launch_mode_layout.addWidget(self.show_logs_check)
        
        form_layout.addRow("", launch_mode_layout)
        
        # Platform selector
        platform_layout = QHBoxLayout()
        self.platform_combo = QComboBox()
        self.platform_combo.addItem("Auto (Default)", "")
        self.platform_combo.addItem("linux/amd64", "linux/amd64")
        self.platform_combo.addItem("linux/arm64", "linux/arm64")
        self.platform_combo.addItem("linux/arm/v7", "linux/arm/v7")
        platform_layout.addWidget(self.platform_combo)
        
        # Show current host platform
        import platform as plat
        host_arch = plat.machine()
        platform_info = QLabel(f"(Host: {host_arch})")
        platform_info.setStyleSheet("color: #888;")
        platform_layout.addWidget(platform_info)
        platform_layout.addStretch()
        
        form_layout.addRow(t('labels.platform') + ":", platform_layout)
        
        # Shared folder checkbox
        self.shared_folder_check = QCheckBox(t('labels.shared_folder'))
        self.shared_folder_check.stateChanged.connect(self._toggle_shared_folder)
        form_layout.addRow("", self.shared_folder_check)
        
        # Shared folder section (initially hidden)
        self.shared_folder_widget = QWidget()
        shared_folder_layout = QFormLayout(self.shared_folder_widget)
        shared_folder_layout.setContentsMargins(20, 0, 0, 0)  # Indent
        
        # Host path with browse button
        host_path_layout = QHBoxLayout()
        self.host_path_edit = QLineEdit()
        self.host_path_edit.setPlaceholderText("Select folder on your computer")
        host_path_layout.addWidget(self.host_path_edit)
        
        browse_btn = QPushButton(t('buttons.browse'))
        browse_btn.clicked.connect(self._browse_host_folder)
        host_path_layout.addWidget(browse_btn)
        
        shared_folder_layout.addRow(t('labels.host_path') + ":", host_path_layout)
        
        # Container path
        self.container_path_edit = QLineEdit("/home/shared_folder")
        shared_folder_layout.addRow(t('labels.container_path') + ":", self.container_path_edit)
        
        # Read-only checkbox
        self.readonly_check = QCheckBox(t('labels.readonly'))
        shared_folder_layout.addRow("", self.readonly_check)
        
        # Add shared folder widget to main form
        form_layout.addRow("", self.shared_folder_widget)
        self.shared_folder_widget.setVisible(False)  # Hidden by default
        
        layout.addLayout(form_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Log output
        log_label = QLabel(t('labels.build_log') + ":")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monaco", 10))
        self.log_text.setMinimumHeight(300)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_text)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._create_container)
        button_box.rejected.connect(self.reject)
        self.button_box = button_box
        layout.addWidget(button_box)
        
        # Initialize startup apps list from first template
        self._update_startup_apps()
    
    def _generate_random_name(self):
        """Generate random container name from mnemonic wordlist"""
        from ..static.mnemonic import WORDLIST
        
        # Pick 2 random words and a random number
        word1 = random.choice(WORDLIST)
        word2 = random.choice(WORDLIST)
        number = random.randint(10, 99)
        
        # Random format: word1-word2-number or word1-number-word2
        if random.choice([True, False]):
            name = f"{word1}-{word2}-{number}"
        else:
            name = f"{word1}-{number}-{word2}"
        
        self.name_edit.setText(name)
    
    def _generate_random_hostname(self):
        """Generate random hostname from mnemonic wordlist"""
        from ..static.mnemonic import WORDLIST
        
        # Pick 2 random words and a random number
        word1 = random.choice(WORDLIST)
        word2 = random.choice(WORDLIST)
        number = random.randint(10, 99)
        
        # Random format for hostname
        if random.choice([True, False]):
            hostname = f"{word1}-{word2}-{number}"
        else:
            hostname = f"{word1}-{number}-{word2}"
        
        self.hostname_edit.setText(hostname)
    
    def _browse_host_folder(self):
        """Open folder browser dialog for host path"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            t('labels.host_path'),
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.host_path_edit.setText(folder)
    
    def _toggle_shared_folder(self, state):
        """Toggle shared folder options visibility"""
        self.shared_folder_widget.setVisible(state == 2)  # 2 = Qt.CheckState.Checked
        
    def _load_networks(self):
        """Load networks into combo"""
        self.network_combo.clear()
        
        show_all = self.show_all_networks.isChecked()
        
        if show_all:
            try:
                networks = self.network_manager.list_networks()
                for net in networks:
                    self.network_combo.addItem(net['name'])
            except:
                self.network_combo.addItems(['bridge', 'host', 'none'])
        else:
            self.network_combo.addItems(['bridge', 'host', 'none'])
            
            try:
                custom_networks = self.db.get_custom_networks() if hasattr(self.db, 'get_custom_networks') else []
                for net in custom_networks:
                    self.network_combo.addItem(net['name'])
            except:
                pass
        
        if self.network_combo.count() > 0:
            self.network_combo.setCurrentIndex(0)
    
    def _toggle_tor(self, state):
        """Toggle Tor Gateway network"""
        if state == Qt.CheckState.Checked:
            for i in range(self.network_combo.count()):
                name = self.network_combo.itemText(i)
                if 'tor' in name.lower() or 'gateway' in name.lower():
                    self.network_combo.setCurrentIndex(i)
                    return
            
            QMessageBox.information(
                self,
                t('dialogs.tor_gateway_title'),
                t('dialogs.tor_gateway_info')
            )
            self.tor_gateway_check.setChecked(False)
    
    def _toggle_disposable_options(self, state):
        """Toggle disposable container options - disable Default option"""
        is_disposable = state == Qt.CheckState.Checked
        
        # Find "Default" item and enable/disable it
        for i in range(self.startup_app_combo.count()):
            if self.startup_app_combo.itemData(i) == "default":
                # Use the view's model (QStandardItemModel)
                from PyQt6.QtGui import QStandardItemModel
                model = self.startup_app_combo.model()
                if isinstance(model, QStandardItemModel):
                    item = model.item(i)
                    if item:
                        if is_disposable:
                            # Disable Default option for disposable containers
                            item.setEnabled(False)
                            # Switch to first available app if Default is selected
                            if self.startup_app_combo.currentIndex() == i:
                                if self.startup_app_combo.count() > 2:  # Has apps beyond Default and Custom
                                    self.startup_app_combo.setCurrentIndex(2)  # Select first app
                                else:
                                    self.startup_app_combo.setCurrentIndex(1)  # Select Custom
                        else:
                            # Enable Default option for normal containers
                            item.setEnabled(True)
                break
    
    def _update_startup_apps(self):
        """Update startup app list from template apps"""
        template_id = self.template_combo.currentData()
        if not template_id:
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            return
        
        # Save current selection
        current_data = self.startup_app_combo.currentData()
        
        # Clear all items except Default and Custom
        while self.startup_app_combo.count() > 2:
            self.startup_app_combo.removeItem(2)
        
        # Load apps from config
        config_path = os.path.join(template['path'], 'config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Use apps array instead of packages
            apps = config.get('apps', [])
            for app in apps:
                app_name = app.get('name', '')
                app_command = app.get('command', '')
                if app_name and app_command:
                    # Store command as data, show name as label
                    self.startup_app_combo.addItem(app_name, app_command)
            
            # Fallback to packages if no apps defined (for backward compatibility)
            if not apps:
                packages = config.get('packages', [])
                for package in packages:
                    self.startup_app_combo.addItem(package, package)
        except Exception as e:
            pass
        
        # Restore selection if possible
        if current_data:
            index = self.startup_app_combo.findData(current_data)
            if index >= 0:
                self.startup_app_combo.setCurrentIndex(index)
    
    def _on_startup_app_changed(self, index):
        """Handle startup app selection change"""
        app_data = self.startup_app_combo.currentData()
        
        if app_data == "custom":
            # Show custom command input
            self.custom_command_edit.setVisible(True)
            self.external_terminal_check.setVisible(True)
        else:
            # Hide custom command input
            self.custom_command_edit.setVisible(False)
            self.external_terminal_check.setVisible(False)
    
    def _setup_xhost_permissions(self):
        """Setup xhost permissions for X11 access"""
        system = platform_module.system()
        
        if system in ["Darwin", "Linux"]:
            try:
                # Add localhost permissions
                subprocess.run(['xhost', '+localhost'], 
                             capture_output=True, timeout=2)
                subprocess.run(['xhost', '+127.0.0.1'], 
                             capture_output=True, timeout=2)
                
                # Add hostname permissions
                hostname_result = subprocess.run(['hostname'], 
                                               capture_output=True, 
                                               text=True, 
                                               timeout=2)
                if hostname_result.returncode == 0:
                    hostname = hostname_result.stdout.strip()
                    subprocess.run(['xhost', f'+{hostname}'], 
                                 capture_output=True, timeout=2)
                
                self.log_text.append("✓ X11 permissions configured")
            except Exception as e:
                self.log_text.append(f"⚠ Could not configure xhost: {e}")
    
    def _create_container(self):
        """Start container creation"""
        # Setup X11 permissions first if GUI is enabled
        if self.gui_check.isChecked():
            self._setup_xhost_permissions()
        
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, t('dialogs.error_title'), t('messages.enter_container_name'))
            return
        
        template_id = self.template_combo.currentData()
        if not template_id:
            QMessageBox.warning(self, t('dialogs.error_title'), t('messages.select_template'))
            return
        
        # CRITICAL: Validate disposable container must have startup app
        if self.disposable_check.isChecked():
            app_selection = self.startup_app_combo.currentData()
            if not app_selection or app_selection == "default":
                QMessageBox.warning(
                    self,
                    t('dialogs.error_title'),
                    t('messages.disposable_requires_app')
                )
                return
            
            # Also check custom command if selected
            if app_selection == "custom":
                custom_cmd = self.custom_command_edit.text().strip()
                if not custom_cmd:
                    QMessageBox.warning(
                        self,
                        t('dialogs.error_title'),
                        t('messages.disposable_requires_command')
                    )
                    return
        
        # Disable buttons
        self.button_box.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Prepare config
        config = {
            'name': name,
            'template_id': template_id,
            'hostname': self.hostname_edit.text() or name,
            'user': self.user_edit.text(),
            'uid': self.uid_spin.value(),
            'network': self.network_combo.currentText(),
            'disposable': self.disposable_check.isChecked(),
            'gui': self.gui_check.isChecked(),
            'environment': {},
            'platform': self.platform_combo.currentData() or None,
            'volumes': {}
        }
        
        # Add shared folder if enabled and specified
        if self.shared_folder_check.isChecked():
            host_path = self.host_path_edit.text().strip()
            container_path = self.container_path_edit.text().strip()
            
            if host_path and container_path:
                # Validate host path exists
                if not os.path.exists(host_path):
                    QMessageBox.warning(
                        self, 
                        t('dialogs.error_title'), 
                        t('messages.host_path_not_exist').format(path=host_path)
                    )
                    self.button_box.setEnabled(True)
                    self.progress_bar.setVisible(False)
                    return
                
                # Determine mode
                mode = 'ro' if self.readonly_check.isChecked() else 'rw'
                config['volumes'][host_path] = {'bind': container_path, 'mode': mode}
            elif not host_path:
                # Checkbox is checked but no path specified
                QMessageBox.warning(
                    self,
                    t('dialogs.error_title'),
                    t('messages.specify_host_path')
                )
                self.button_box.setEnabled(True)
                self.progress_bar.setVisible(False)
                return
        
        # Add DISPLAY if GUI
        if config['gui']:
            import platform
            display = os.environ.get('DISPLAY', ':0')
            
            # On macOS with XQuartz, use host.docker.internal
            if platform.system() == "Darwin" and display:
                # Keep full path for socket mounting, but use host.docker.internal for DISPLAY
                config['environment']['DISPLAY'] = display  # Keep for socket path
                config['environment']['DISPLAY_SOCKET'] = display  # Store original for mounting
                # Override DISPLAY for container
                if ':' in display:
                    display_num = display.split(':')[-1]
                    config['environment']['DISPLAY'] = f"host.docker.internal:{display_num}"
            else:
                config['environment']['DISPLAY'] = display
            
            config['environment']['XAUTHORITY'] = '/tmp/.Xauthority'
        
        # Get launch mode from UI
        selected_launch_mode = self.launch_mode_combo.currentData()
        config['launch_mode'] = selected_launch_mode
        config['show_logs_window'] = self.show_logs_check.isChecked()
        
        # Handle startup app selection
        app_selection = self.startup_app_combo.currentData()
        
        if app_selection == "custom":
            # Custom command
            custom_cmd = self.custom_command_edit.text().strip()
            if custom_cmd:
                config['startup_command'] = custom_cmd
                # Override with terminal mode if external terminal is checked
                if self.external_terminal_check.isChecked():
                    config['launch_mode'] = 'terminal'
        elif app_selection != "default" and app_selection:
            # Package/app from list
            config['startup_command'] = app_selection
            # Keep launch_mode from combo selection
        # If "default" - don't set startup_command, container will use Dockerfile CMD
        
        # Fix Firefox popup black screen issue on macOS with XQuartz
        # Add environment variables to disable hardware acceleration
        if config.get('gui') and config.get('startup_command'):
            startup_cmd = config['startup_command'].lower()
            if 'firefox' in startup_cmd or 'mozilla' in startup_cmd:
                config['environment']['MOZ_X11_EGL'] = '0'
                config['environment']['MOZ_DISABLE_CONTENT_SANDBOX'] = '1'
                config['environment']['LIBGL_ALWAYS_SOFTWARE'] = '1'
                config['environment']['MOZ_ACCELERATED'] = '0'
        
        # Create thread
        self.create_thread = ContainerCreateThread(
            self.docker_manager,
            self.template_manager,
            config
        )
        
        self.create_thread.log_signal.connect(self._append_log)
        self.create_thread.progress_signal.connect(self.progress_bar.setValue)
        self.create_thread.finished_signal.connect(self._creation_finished)
        self.create_thread.open_logs_signal.connect(self._open_logs_window)
        
        self.create_thread.start()
    
    def _append_log(self, message):
        """Append message to log"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def _open_logs_window(self, container_id, container_name):
        """Open logs window for the created container"""
        # Check if user wants to see logs window (from dialog checkbox)
        if self.show_logs_check.isChecked():
            # Create logs window WITHOUT parent so it stays open after dialog closes
            self.logs_window = ContainerLogsWindow(
                self.docker_manager,
                container_id,
                container_name,
                None  # No parent - window will be independent
            )
            self.logs_window.show()
    
    def _creation_finished(self, success, message):
        """Handle creation finished"""
        self.button_box.setEnabled(True)
        
        # Check if user wants to see success messages
        settings = SettingsManager()
        settings.load()
        show_success = settings.get('show_success_messages', True)
        
        if success:
            # Only show message box if enabled in settings
            # Don't close dialog automatically - let user review logs
            if show_success:
                QMessageBox.information(self, t('dialogs.success_title'), message)
            
            # Close dialog (logs window will remain open if it was shown)
            self.accept()
        else:
            QMessageBox.critical(self, t('dialogs.error_title'), message)

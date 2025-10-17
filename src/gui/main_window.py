"""
Main GUI Window
"""

import sys
import os
import logging
import subprocess
import platform
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QApplication,
    QDialog
)
from PyQt6.QtCore import QTimer

from ..docker_manager import DockerManager
from ..xserver_manager import XServerManager
from ..template_manager import TemplateManager
from ..network_manager import NetworkManager
from ..file_browser import FileBrowser
from ..database import DatabaseManager
from ..localization import t
from ..plugin_manager import PluginManager

from .create_dialog import CreateContainerDialog
from .containers_tab import ContainersTab
from .threads import ContainerOperationThread

logger = logging.getLogger(__name__)


class GhostContainersGUI(QMainWindow):
    """Main PyQt6 GUI Window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("GhostContainers")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize managers
        try:
            self.db = DatabaseManager()
            
            # Initialize localization with database support
            from ..localization import init_localization
            init_localization(database_manager=self.db)
            
            # Initialize settings manager
            from ..settings_manager import SettingsManager
            self.settings_manager = SettingsManager()
            
            self.docker_manager = DockerManager(database_manager=self.db)
            self.xserver_manager = XServerManager()
            self.template_manager = TemplateManager()
            self.network_manager = NetworkManager(self.docker_manager.client)
            self.file_browser = FileBrowser(self.docker_manager)
            
            # Operation thread tracking
            self.operation_thread = None
            
            # Active logs windows (keep references to prevent garbage collection)
            self._active_logs_windows = []
            self.status_timer = None
            self.status_dots = 0
            
            # Initialize plugin manager
            plugins_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'plugins')
            self.plugin_manager = PluginManager(plugins_dir=plugins_dir)
            
            plugin_context = {
                'docker_manager': self.docker_manager,
                'file_browser': self.file_browser,
                'db': self.db,
                'main_window': self,
                'plugin_api': self.plugin_manager.plugin_api
            }
            self.plugin_manager.set_app_context(plugin_context)
            self.plugin_manager.load_all_plugins()
            self.plugin_manager.initialize_plugins()
            
        except Exception as e:
            QMessageBox.critical(self, t('dialogs.error_title'), 
                               t('errors.init_failed').format(error=str(e)))
            sys.exit(1)
        
        self._create_ui()
        self._check_xserver()
        self.refresh_containers()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_containers)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
    
    def _create_ui(self):
        """Create main UI"""
        # Menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu(t('menu.file'))
        
        settings_action = file_menu.addAction(t('menu.file_settings'))
        settings_action.triggered.connect(self._show_settings)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction(t('menu.file_exit'))
        exit_action.triggered.connect(self.close)
        
        # Help menu
        help_menu = menubar.addMenu(t('menu.help'))
        
        xserver_action = help_menu.addAction("🖥 " + t('menu.help_xserver'))
        xserver_action.triggered.connect(self._show_xserver_help)
        
        help_menu.addSeparator()
        
        about_action = help_menu.addAction(t('menu.about'))
        about_action.triggered.connect(self._show_about)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create main containers tab
        self.containers_tab = ContainersTab(self, self.docker_manager)
        self.tabs.addTab(self.containers_tab, t('tabs.containers'))
        
        # Load tabs from plugins
        for tab_plugin in self.plugin_manager.tab_plugins:
            try:
                tab_widget = tab_plugin.create_tab_widget()
                if tab_widget:
                    # Get tab name from plugin's name property
                    tab_name = getattr(tab_plugin, 'name', 'Plugin Tab')
                    self.tabs.addTab(tab_widget, tab_name)
                    logger.info(f"Added plugin tab: {tab_name}")
            except Exception as e:
                logger.error(f"Failed to create tab from plugin {tab_plugin.__class__.__name__}: {e}")
        
        # Status bar
        self.statusBar().showMessage(t('status.ready'))
    
    def _check_xserver(self):
        """Check X Server status"""
        running, message = self.xserver_manager.check_xserver_running()
        if running:
            self.statusBar().showMessage(f"✓ {message}")
        else:
            self.statusBar().showMessage(f"⚠ {message}")
            QMessageBox.warning(
                self,
                t('dialogs.xserver_title'),
                t('dialogs.xserver_warning').format(message=message)
            )
    
    def refresh_containers(self):
        """Refresh containers list"""
        show_all = self.containers_tab.show_all_check.isChecked()
        containers = self.docker_manager.list_containers(all_containers=True, show_all=show_all)
        
        self.containers_tab.refresh(containers)
        
        # Notify plugins about container list update via hook
        if hasattr(self.plugin_manager, 'plugin_api'):
            self.plugin_manager.plugin_api.execute_hook('HOOK_CONTAINERS_UPDATED', containers)
        
        self.statusBar().showMessage(t('status.containers_count').format(count=len(containers)))
    
    def get_selected_container(self):
        """Get selected container from containers tab"""
        return self.containers_tab.get_selected_container()
    
    def create_container(self):
        """Show create container dialog"""
        dialog = CreateContainerDialog(
            self,
            self.docker_manager,
            self.template_manager,
            self.network_manager,
            self.db
        )
        
        if dialog.exec():
            self.refresh_containers()
    
    def start_container(self):
        """Start selected container"""
        name = self.get_selected_container()
        if not name:
            return
        
        self._run_container_operation('start', name)
    
    def stop_container(self):
        """Stop selected container"""
        name = self.get_selected_container()
        if not name:
            return
        
        self._run_container_operation('stop', name)
    
    def remove_container(self):
        """Remove selected container"""
        name = self.get_selected_container()
        if not name:
            return
        
        reply = QMessageBox.question(
            self,
            t('dialogs.confirm_title'),
            t('messages.remove_container_confirm').format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._run_container_operation('remove', name)
    
    def _run_container_operation(self, operation, container_name):
        """Run container operation in background thread with status animation"""
        # Disable buttons during operation
        self.containers_tab.set_buttons_enabled(False)
        
        # Update container status in table
        status_map = {
            'start': (t('messages.starting'), '#ffb86c'),
            'stop': (t('messages.stopping'), '#ffb86c'),
            'remove': (t('messages.removing'), '#ff5555'),
            'restart': (t('messages.restarting'), '#ffb86c')
        }
        status_text, status_color = status_map.get(operation, ('Working...', '#ffb86c'))
        self.containers_tab.update_container_status(container_name, status_text, status_color)
        
        # Create operation thread
        self.operation_thread = ContainerOperationThread(
            self.docker_manager,
            operation,
            container_name
        )
        
        # Connect signals
        self.operation_thread.status_signal.connect(self._update_operation_status)
        self.operation_thread.finished_signal.connect(self._operation_finished)
        
        # Start animated status
        self.status_dots = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._animate_status)
        self.status_timer.start(500)  # Update every 500ms
        
        # Start thread
        self.operation_thread.start()
    
    def _update_operation_status(self, status):
        """Update status bar with operation message"""
        self.current_status = status
        self._animate_status()
    
    def _animate_status(self):
        """Animate status message with dots"""
        if hasattr(self, 'current_status'):
            dots = '.' * (self.status_dots % 4)
            self.statusBar().showMessage(f"{self.current_status}{dots}")
            self.status_dots += 1
    
    def _operation_finished(self, success, message):
        """Handle operation completion"""
        # Stop animation
        if self.status_timer:
            self.status_timer.stop()
            self.status_timer = None
        
        # Re-enable buttons
        self.containers_tab.set_buttons_enabled(True)
        
        # Show result
        if success:
            QMessageBox.information(self, t('dialogs.success_title'), message)
            self.statusBar().showMessage(f"✓ {message}")
        else:
            QMessageBox.critical(self, t('dialogs.error_title'), message)
            self.statusBar().showMessage(f"✗ {message}")
        
        # Refresh containers list
        self.refresh_containers()
        
        # Clean up thread
        self.operation_thread = None
    
    def open_shell(self, user: str):
        """Open shell in new terminal window"""
        name = self.get_selected_container()
        if not name:
            return
        
        containers = self.docker_manager.list_containers(all_containers=True)
        container = next((c for c in containers if c['name'] == name), None)
        
        if not container:
            QMessageBox.warning(self, t('dialogs.error_title'), 
                              t('messages.container_not_found').format(name=name))
            return
        
        # Start if not running
        if container['status'] != 'running':
            if not self.docker_manager.start_container(name):
                QMessageBox.critical(self, t('dialogs.error_title'), 
                                   t('messages.failed_start_container').format(name=name))
                return
        
        # Detect OS and terminal
        system = platform.system()
        
        if system == "Darwin":  # macOS
            if subprocess.run(['which', 'iterm'], capture_output=True).returncode == 0:
                script = f'''
tell application "iTerm"
    create window with default profile
    tell current session of current window
        write text "docker exec -it -u {user} {name} /bin/bash"
    end tell
end tell
'''
                subprocess.Popen(['osascript', '-e', script])
            else:
                script = f'''
tell application "Terminal"
    do script "docker exec -it -u {user} {name} /bin/bash"
    activate
end tell
'''
                subprocess.Popen(['osascript', '-e', script])
        
        elif system == "Linux":
            terminals = [
                ('gnome-terminal', ['gnome-terminal', '--', 'docker', 'exec', '-it', '-u', user, name, '/bin/bash']),
                ('konsole', ['konsole', '-e', 'docker', 'exec', '-it', '-u', user, name, '/bin/bash']),
                ('xterm', ['xterm', '-e', 'docker', 'exec', '-it', '-u', user, name, '/bin/bash']),
            ]
            
            for term_name, cmd in terminals:
                if subprocess.run(['which', term_name], capture_output=True).returncode == 0:
                    subprocess.Popen(cmd)
                    return
            
            QMessageBox.warning(self, t('dialogs.error_title'), t('messages.no_supported_terminal'))
        else:
            QMessageBox.warning(self, t('dialogs.error_title'), 
                              t('messages.unsupported_os').format(os=system))
    
    def run_gui_app(self):
        """Run GUI application - show app selector dialog"""
        name = self.get_selected_container()
        if not name:
            return
        
        # Open app selector dialog
        from .app_selector_dialog import AppSelectorDialog
        
        dialog = AppSelectorDialog(
            self,
            self.docker_manager,
            self.template_manager,
            self.db,
            name
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_app = dialog.get_selected_app()
            if not selected_app:
                return
            
            app_command = selected_app['command']
            app_name = selected_app['name']
            
            # Check if container is running
            containers = self.docker_manager.list_containers(all_containers=True)
            container = next((c for c in containers if c['name'] == name), None)
            
            if not container:
                QMessageBox.warning(self, t('dialogs.error_title'), 
                                  t('messages.container_not_found').format(name=name))
                return
            
            if container['status'] != 'running':
                if not self.docker_manager.start_container(name):
                    QMessageBox.critical(self, t('dialogs.error_title'), 
                                       t('messages.failed_start_container').format(name=name))
                    return
            
            # Run the app
            if self.docker_manager.run_gui_app(name, app_command):
                self.statusBar().showMessage(t('messages.started_gui_app').format(app=app_name, name=name))
            else:
                QMessageBox.critical(self, t('dialogs.error_title'), 
                                   t('messages.failed_run_gui_app').format(app=app_name))
    
    def _show_xserver_help(self):
        """Show X Server setup instructions"""
        from PyQt6.QtWidgets import QDialog, QPushButton, QTextEdit
        from PyQt6.QtWidgets import QVBoxLayout as DialogVBoxLayout
        
        instructions = self.xserver_manager.get_setup_instructions()
        
        dialog = QDialog(self)
        dialog.setWindowTitle(t('dialogs.xserver_setup'))
        dialog.setMinimumSize(700, 500)
        
        layout = DialogVBoxLayout(dialog)
        
        text_browser = QTextEdit()
        text_browser.setReadOnly(True)
        text_browser.setMarkdown(instructions)
        layout.addWidget(text_browser)
        
        close_btn = QPushButton(t('buttons.close'))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _show_settings(self):
        """Show settings dialog"""
        from .settings_dialog import SettingsDialog
        from ..settings_manager import SettingsManager
        
        # Initialize settings manager if not exists
        if not hasattr(self, 'settings_manager'):
            self.settings_manager = SettingsManager()
        
        dialog = SettingsDialog(self.settings_manager, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
    
    def _on_settings_changed(self):
        """Handle settings changes"""
        # Reload containers list with new settings
        self.refresh_containers()
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            t('dialogs.about_title'),
            t('dialogs.about_message')
        )
    
    def _change_language(self, lang_code: str):
        """Change application language"""
        from ..localization import localization_manager
        
        if localization_manager.set_language(lang_code):
            lang_name = localization_manager.get_available_languages().get(lang_code, lang_code)
            QMessageBox.information(
                self,
                t('dialogs.success_title'),
                t('messages.language_changed').format(language=lang_name)
            )


def run_gui_qt():
    """Run PyQt6 GUI"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = GhostContainersGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    run_gui_qt()

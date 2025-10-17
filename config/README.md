# Configuration Template

This `settings.json` file serves as a **template** for default application settings.

## User Settings Location

Actual user settings are stored in:

- **macOS/Linux**: `~/.local/share/ghost-containers/settings.json`
- **Windows**: `%APPDATA%\ghost-containers\settings.json`

## How It Works

1. When the application starts, it loads default settings from this template
2. User settings override template values
3. "Reset to Defaults" in the Settings dialog restores values from this template
4. This file should **not** be modified by users directly

## Settings Description

- `language`: UI language (`en`, `ru`)
- `launch_mode`: Container launch method (`terminal`, `api`, `custom`)
- `custom_terminal_command`: Custom terminal command template
- `theme`: UI theme (`system`, `light`, `dark`)
- `auto_refresh_interval`: Container list refresh interval (seconds)
- `show_all_containers_default`: Default state for "Show all containers" checkbox
- `log_level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `docker_socket_path`: Custom Docker socket path (empty = auto-detect)
- `show_success_messages`: Show success message boxes after operations
- `show_logs_window`: Auto-open logs window when using API launch mode

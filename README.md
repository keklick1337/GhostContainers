# 🐳 GhostContainers

**Professional Docker Container Management System with Custom API Implementation**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

GhostContainers is a modern, feature-rich Docker container management application with a clean GUI interface, plugin system, and custom Docker API implementation that eliminates external dependencies.

**Think of it as a Qubes OS-inspired security architecture built on Docker** - providing isolated, compartmentalized environments that can run anywhere Docker is available. Unlike Qubes OS which requires specific hardware and Xen hypervisor, GhostContainers brings the same security-through-isolation philosophy to any platform supporting Docker (Linux, macOS, Windows), making advanced container isolation accessible and portable.

---

### Core Functionality
- **Complete Container Lifecycle Management** - Create, start, stop, restart, remove containers
- **Template System** - Pre-configured templates (Alpine, Debian, Fedora, Ubuntu Desktop, Tor Gateway)
- **GUI Application Support** - Launch X11 applications in containers with XQuartz/Xorg integration
- **Plugin Architecture** - Extensible plugin system for adding new features
- **Network Management** - Create and manage Docker networks
- **File Browser** - Browse and manage files inside containers
- **Real-time Logs** - View container logs with color coding and ANSI support
- **SQLite Database** - Track container metadata and applications
- **Multilingual** - English and Russian localization

### Technical Highlights
- **100% Custom Docker API** - Pure Python implementation, no docker-py dependency
- **Zero Docker CLI Calls** - Direct communication with Docker daemon via Unix socket
- **TAR Archive Handling** - Native file copy operations using Docker API
- **Plugin System** - Dynamic tab loading, hooks, and event system
- **Modular Architecture** - Clean separation of concerns across modules

---

## Roadmap

- [ ] Fix bug with containers dropdown in plugins
- [ ] Volume management interface
- [ ] Tor network isolation for containers
- [ ] Docker Compose support
- [ ] Container statistics and monitoring
- [ ] Export/Import containers
- [ ] Docker registry integration
- [ ] Container backup/restore
- [ ] SSH key management
- [ ] Multi-host Docker support
- [ ] REST API for remote management
- [ ] SSH terminal
- [ ] Performance monitoring
- [ ] Backup manager
- [ ] More templates
- [ ] Spoofing system information

---

## 🤝 Contributing

Contributions are welcome!

### Areas for Contribution

- Bug fixes
- Documentation improvements
- Translations
- New plugins
- New templates
- Feature additions

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

### What this means:
- ✅ Free to use, modify, and distribute
- ✅ Source code must be made available
- ✅ Derivative works must use GPL v3
- ✅ No warranty provided

---

## Contact

- **Issues**: [GitHub Issues](https://github.com/keklick1337/GhostContainers/issues)
- **Author**: Vladislav Tislenko aka keklick1337

**Made with ❤️ for the safety of users**

*Manage Docker containers the professional way.*

"""
CLI - command line interface
"""

import argparse
import sys
import logging
from typing import Optional

from .docker_manager import DockerManager
from .xserver_manager import XServerManager
from .template_manager import TemplateManager
from .network_manager import NetworkManager
from .file_browser import FileBrowser

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class DockerManagerCLI:
    """Docker manager CLI interface"""
    
    def __init__(self):
        """Initialize CLI"""
        try:
            self.docker_manager = DockerManager()
            self.xserver_manager = XServerManager()
            self.template_manager = TemplateManager()
            self.network_manager = NetworkManager(self.docker_manager.client)
            self.file_browser = FileBrowser(self.docker_manager)
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            sys.exit(1)
    
    def list_containers(self, all_containers: bool = True):
        """List containers"""
        containers = self.docker_manager.list_containers(all_containers=all_containers)
        
        if not containers:
            logger.info("No containers found")
            return
        
        # Header
        print(f"{'NAME':<30} {'STATUS':<15} {'IMAGE':<40} {'ID':<15}")
        print("-" * 100)
        
        # Containers
        for c in containers:
            print(f"{c['name']:<30} {c['status']:<15} {c['image']:<40} {c['id']:<15}")
        
        print(f"\nTotal: {len(containers)}")
    
    def create_container(
        self,
        template: str,
        name: str,
        hostname: Optional[str] = None,
        user: str = "user",
        uid: int = 1000,
        network: str = "bridge",
        shared: Optional[str] = None,
        disposable: bool = False,
        gui: bool = True
    ):
        """Create container from template"""
        # Check template
        template_obj = self.template_manager.get_template(template)
        if not template_obj:
            logger.error(f"Template '{template}' not found")
            logger.info("\nAvailable templates:")
            self.list_templates()
            return False
        
        # Building image
        image_tag = f"dsm-{template}:latest"
        logger.info(f"Checking image {image_tag}...")
        
        try:
            self.docker_manager.client.images.get(image_tag)
            logger.info(f"Image {image_tag} found")
        except:
            logger.info(f"Image not found, starting build...")
            if not self.docker_manager.build_image(template_obj['path'], image_tag):
                logger.error("Image build error")
                return False
        
        # Preparing parameters
        environment = {}
        volumes = {}
        
        # X Server forwarding
        if gui:
            logger.info("Setting up X Server forwarding...")
            xserver_env = self.xserver_manager.get_environment_vars()
            environment.update(xserver_env)
            xserver_vols = self.xserver_manager.get_volume_mounts()
            volumes.update(xserver_vols)
            
            # Checking X Server
            running, message = self.xserver_manager.check_xserver_running()
            if running:
                logger.info(f"✓ {message}")
            else:
                logger.warning(f"⚠ {message}")
        
        # Shared folder
        if shared:
            parts = shared.split(':')
            if len(parts) == 2:
                volumes[parts[0]] = {'bind': parts[1], 'mode': 'rw'}
                logger.info(f"Shared folder: {parts[0]} -> {parts[1]}")
        
        # Creating container
        logger.info(f"Creating container {name}...")
        container_id = self.docker_manager.create_container(
            image=image_tag,
            name=name,
            environment=environment,
            volumes=volumes,
            network_mode=network,
            hostname=hostname or name,
            remove=disposable
        )
        
        if container_id:
            logger.info(f"✓ Container {name} created: {container_id[:12]}")
            if disposable:
                logger.info("  Mode: disposable (will be removed after stop)")
            return True
        else:
            logger.error("Error container creation")
            return False
    
    def start_container(self, name: str):
        """Start container"""
        logger.info(f"Starting container {name}...")
        if self.docker_manager.start_container(name):
            logger.info(f"✓ Container {name} started")
            return True
        else:
            logger.error(f"Start error {name}")
            return False
    
    def stop_container(self, name: str):
        """Stop container"""
        logger.info(f"Stopping container {name}...")
        if self.docker_manager.stop_container(name):
            logger.info(f"✓ Container {name} stopped")
            return True
        else:
            logger.error(f"Stop error {name}")
            return False
    
    def remove_container(self, name: str, force: bool = False):
        """Remove container"""
        logger.info(f"Removing container {name}...")
        if self.docker_manager.remove_container(name, force=force):
            logger.info(f"✓ Container {name} removed")
            return True
        else:
            logger.error(f"Error removal {name}")
            return False
    
    def shell(self, name: str, user: Optional[str] = None):
        """Open shell in container"""
        # Check status
        status = self.docker_manager.get_container_status(name)
        if status != 'running':
            logger.error(f"Container {name} not started (status: {status})")
            return False
        
        logger.info(f"Opening shell in {name} (user: {user or 'root'})...")
        self.docker_manager.exec_interactive(name, "/bin/bash", user)
        return True
    
    def run_command(
        self,
        name: str,
        command: str,
        user: Optional[str] = None,
        gui: bool = False
    ):
        """Run command in container"""
        # Check status
        status = self.docker_manager.get_container_status(name)
        if status != 'running':
            logger.error(f"Container {name} not started (status: {status})")
            return False
        
        environment = {}
        
        # X Server for GUI
        if gui:
            logger.info("Setting up X Server forwarding...")
            xserver_env = self.xserver_manager.get_environment_vars()
            environment.update(xserver_env)
            
            # Checking X Server
            running, message = self.xserver_manager.check_xserver_running()
            if not running:
                logger.warning(f"⚠ {message}")
        
        logger.info(f"Running command in {name}: {command}")
        self.docker_manager.exec_interactive(name, command, user, environment)
        return True
    
    def list_templates(self):
        """List templates"""
        templates = self.template_manager.list_templates()
        
        if not templates:
            logger.info("Templates not found")
            logger.info("Create directory in templates/ with Dockerfile and config.json")
            return
        
        print(f"{'ID':<25} {'NAME':<30} {'DESCRIPTION':<50}")
        print("-" * 105)
        
        for t in templates:
            print(f"{t['id']:<25} {t['name']:<30} {t['description']:<50}")
        
        print(f"\nTotal: {len(templates)}")
    
    def list_networks(self):
        """List networks"""
        networks = self.network_manager.list_networks()
        
        if not networks:
            logger.info("Networks not found")
            return
        
        print(f"{'NAME':<25} {'DRIVER':<15} {'SCOPE':<10} {'CONTAINERS':<10}")
        print("-" * 60)
        
        for n in networks:
            print(f"{n['name']:<25} {n['driver']:<15} {n['scope']:<10} {n['containers']:<10}")
        
        print(f"\nTotal: {len(networks)}")
    
    def create_network(
        self,
        name: str,
        driver: str = "bridge",
        internal: bool = False
    ):
        """Create network"""
        logger.info(f"Creating network {name} (driver: {driver})...")
        network_id = self.network_manager.create_network(
            name=name,
            driver=driver,
            internal=internal
        )
        
        if network_id:
            logger.info(f"✓ Network {name} created: {network_id[:12]}")
            return True
        else:
            logger.error("Error network creation")
            return False
    
    def check_docker(self):
        """Check Docker"""
        version_info = self.docker_manager.check_docker_version()
        
        print("Docker information:")
        print(f"  Client: {version_info.get('client', 'Unknown')}")
        print(f"  Server: {version_info.get('server', 'Unknown')}")
        print(f"  API: {version_info.get('api', 'Unknown')}")
        
        print(f"\nX Server:")
        print(f"  Platform: {self.xserver_manager.os_type}")
        print(f"  Session: {self.xserver_manager.session_type}")
        print(f"  DISPLAY: {self.xserver_manager.detect_display()}")
        
        running, message = self.xserver_manager.check_xserver_running()
        if running:
            print(f"  Status: ✓ {message}")
        else:
            print(f"  Status: ⚠ {message}")
            print(f"\nTo configure X Server:")
            print(self.xserver_manager.get_setup_instructions())
    
    def show_logs(self, name: str, tail: int = 100):
        """Show container logs"""
        logger.info(f"Container logs {name} (last {tail} lines):\n")
        logs = self.docker_manager.get_container_logs(name, tail=tail)
        
        if logs:
            print(logs)
        else:
            logger.error(f"Failed to get logs {name}")


def run_cli():
    """Start CLI application"""
    parser = argparse.ArgumentParser(
        description='Docker Software Manager - Docker container manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s list                                    # List containers
  %(prog)s create --template debian-sid --name my-debian
  %(prog)s start --name my-debian
  %(prog)s shell --name my-debian --user user
  %(prog)s run --name my-debian --command "firefox"
  %(prog)s stop --name my-debian
  %(prog)s remove --name my-debian
  %(prog)s check                                   # Check Docker and X Server
"""
    )
    
    parser.add_argument(
        'action',
        choices=[
            'list', 'create', 'start', 'stop', 'remove',
            'shell', 'run', 'templates', 'networks',
            'create-network', 'check', 'logs'
        ],
        help='Action'
    )
    
    # Container parameters
    parser.add_argument('--name', help='Container name')
    parser.add_argument('--template', help='Template ID')
    parser.add_argument('--hostname', help='Container hostname')
    parser.add_argument('--user', default='user', help='User (default: user)')
    parser.add_argument('--uid', type=int, default=1000, help='User UID (default: 1000)')
    parser.add_argument('--network', default='bridge', help='Network (default: bridge)')
    parser.add_argument('--shared', help='Shared folder in format host_path:container_path')
    parser.add_argument('--disposable', action='store_true', help='Disposable container')
    parser.add_argument('--no-gui', action='store_true', help='Disable X Server forwarding')
    
    # Command parameters
    parser.add_argument('--command', help='Command to execute')
    parser.add_argument('--force', action='store_true', help='Force action')
    
    # Network parameters
    parser.add_argument('--driver', default='bridge', help='Network driver')
    parser.add_argument('--internal', action='store_true', help='Isolated network')
    
    # Log parameters
    parser.add_argument('--tail', type=int, default=100, help='Number of log lines')
    
    # Show all containers
    parser.add_argument('--all', action='store_true', help='Show all containers')
    
    args = parser.parse_args()
    
    # Creating CLI
    cli = DockerManagerCLI()
    
    # Executing action
    try:
        if args.action == 'list':
            cli.list_containers(all_containers=True)
        
        elif args.action == 'create':
            if not args.template or not args.name:
                parser.error("create requires --template and --name")
            cli.create_container(
                template=args.template,
                name=args.name,
                hostname=args.hostname,
                user=args.user,
                uid=args.uid,
                network=args.network,
                shared=args.shared,
                disposable=args.disposable,
                gui=not args.no_gui
            )
        
        elif args.action == 'start':
            if not args.name:
                parser.error("start requires --name")
            cli.start_container(args.name)
        
        elif args.action == 'stop':
            if not args.name:
                parser.error("stop requires --name")
            cli.stop_container(args.name)
        
        elif args.action == 'remove':
            if not args.name:
                parser.error("remove requires --name")
            cli.remove_container(args.name, force=args.force)
        
        elif args.action == 'shell':
            if not args.name:
                parser.error("shell requires --name")
            user = args.user if args.user != 'root' else None
            cli.shell(args.name, user=user)
        
        elif args.action == 'run':
            if not args.name or not args.command:
                parser.error("run requires --name and --command")
            user = args.user if args.user != 'root' else None
            cli.run_command(
                args.name,
                args.command,
                user=user,
                gui=not args.no_gui
            )
        
        elif args.action == 'templates':
            cli.list_templates()
        
        elif args.action == 'networks':
            cli.list_networks()
        
        elif args.action == 'create-network':
            if not args.name:
                parser.error("create-network requires --name")
            cli.create_network(
                name=args.name,
                driver=args.driver,
                internal=args.internal
            )
        
        elif args.action == 'check':
            cli.check_docker()
        
        elif args.action == 'logs':
            if not args.name:
                parser.error("logs requires --name")
            cli.show_logs(args.name, tail=args.tail)
    
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()

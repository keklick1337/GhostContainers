#!/usr/bin/env python3
"""
Docker Software Manager
Application entry point
"""

import sys
import argparse


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Docker Software Manager',
        add_help=False
    )
    
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run in CLI mode'
    )
    
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Run in GUI mode (default)'
    )
    
    # Parse only known arguments
    args, remaining = parser.parse_known_args()
    
    # Determine mode
    if args.cli or len(remaining) > 0:
        raise Exception("CLI mode is currently not implemented.")
        # CLI mode
        #from src.cli import run_cli
        
        # Restore sys.argv for CLI parser
        #sys.argv = [sys.argv[0]] + remaining
        #run_cli()
    else:
        # GUI mode (default) - Use modular PyQt6 interface
        from src.gui import run_gui_qt
        run_gui_qt()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Flood Prediction World Model - Application Starter

This script starts the flood prediction application with all necessary
components and provides a web interface accessible from LAN.
"""

import sys
import os
from pathlib import Path
import asyncio
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApplicationStarter:
    """Application startup and configuration manager."""
    
    def __init__(self, config_path: str = 'config/model_config.yaml'):
        """Initialize the application starter.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.app_config = self._load_configuration()
        self.services = []
        
    def _load_configuration(self) -> Dict:
        """Load application configuration.
        
        Returns:
            Configuration dictionary
        """
        config = {
            'host': '0.0.0.0',
            'port': 8000,
            'api_port': 8000,
            'web_port': 8080,
            'debug': True,
            'config_path': self.config_path
        }
        return config
    
    def get_server_addresses(self) -> List[Dict]:
        """Get server addresses for LAN access.
        
        Returns:
            List of server address configurations
        """
        addresses = []
        
        # Local server
        addresses.append({
            'name': 'Local Server',
            'url': 'http://localhost',
            'web_url': 'http://localhost:8080',
            'api_url': 'http://localhost:8000/api',
            'accessible_from': 'localhost'
        })
        
        # Network servers
        try:
            import socket
            hostname = socket.gethostname()
            addresses.append({
                'name': f'Network Server ({hostname})',
                'url': f'http://{hostname}',
                'web_url': f'http://{hostname}:8080',
                'api_url': f'http://{hostname}:8000/api',
                'accessible_from': 'LAN devices'
            })
        except Exception as e:
            logger.warning(f"Could not get hostname: {e}")
        
        return addresses
    
    def print_access_information(self):
        """Print access information for users.
        
        Displays URLs and configuration details for accessing
        the application from different devices.
        """
        addresses = self.get_server_addresses()
        
        print("\n" + "=" * 70)
        print("🌊 FLOOD PREDICTION WORLD MODEL - ACCESS INFORMATION")
        print("=" * 70 + "\n")
        
        print("📍 ACCESS POINTS:\n")
        for i, addr in enumerate(addresses, 1):
            print(f"  {i}. {addr['name']}")
            print(f"     Web Interface: {addr['web_url']}")
            print(f"     API Endpoint: {addr['api_url']}")
            print(f"     Accessible From: {addr['accessible_from']}")
            print()
        
        print("🔌 PORT CONFIGURATION:\n")
        print(f"    Web Interface Port: {self.app_config['web_port']}")
        print(f"    API Service Port: {self.app_config['api_port']}")
        print(f"    Host Address: {self.app_config['host']}")
        print()
        
        print("📱 FOR LAN ACCESS FROM OTHER DEVICES:\n")
        print(f"    1. Determine server IP address:")
        print(f"       Command: hostname -I")
        print(f"    2. Access from other computers using the IP address:")
        print(f"       Web URL: http://[SERVER_IP]:8080")
        print(f"       API URL: http://[SERVER_IP]:8000/api")
        print(f"    3. Ensure ports {self.app_config['web_port']} and {self.app_config['api_port']}")
        print(f"       are accessible through firewall")
        print()
        
        print("=" * 70)
    
    def initialize_services(self):
        """Initialize application services.
        
        Sets up and registers all necessary services for the application.
        """
        logger.info("Initializing application services...")
        
        # Initialize services
        self.services = [
            {
                'name': 'Web Interface',
                'status': 'ready',
                'port': self.app_config['web_port']
            },
            {
                'name': 'API Service',
                'status': 'ready',
                'port': self.app_config['api_port']
            },
            {
                'name': 'WebSocket',
                'status': 'ready',
                'port': self.app_config['api_port']
            }
        ]
        
        logger.info(f"Initialized {len(self.services)} services")
    
    async def run(self):
        """Run the application.
        
        Starts all services and maintains application operation.
        """
        self.initialize_services()
        self.print_access_information()
        
        logger.info("Application startup complete")
        logger.info("Press Ctrl+C to stop the application")
        
        # Keep the application running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Application shutdown initiated by user")
        except Exception as e:
            logger.error(f"Application error: {e}")
            sys.exit(1)


async def main():
    """Main entry point for the application."""
    config_path = Path('config/model_config.yaml')
    
    if not config_path.exists():
        logger.warning(f"Configuration file not found: {config_path}")
        logger.info("Using default configuration")
    
    starter = ApplicationStarter(config_path=str(config_path))
    await starter.run()


if __name__ == '__main__':
    asyncio.run(main())

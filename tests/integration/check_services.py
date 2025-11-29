#!/usr/bin/env python3
"""
Service Health Check Script for Integration Tests

Checks all required services before running integration tests.
Can be run standalone or imported by test fixtures.

Usage:
    python tests/integration/check_services.py
    python tests/integration/check_services.py --verbose
    python tests/integration/check_services.py --service postgres
"""

import sys
import time
import socket
import argparse
import requests
from typing import Dict, List, Tuple
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'tests' / 'integration'))

try:
    from agent_manager import AgentManager
except ImportError:
    AgentManager = None


class ServiceChecker:
    """Checks service health for integration tests."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Tuple[bool, str]] = {}
    
    def check_service_health(self, service_name: str, host: str, port: int, timeout: int = 30) -> Tuple[bool, str]:
        """
        Check if a service is healthy and accepting connections.
        
        Args:
            service_name: Name of the service
            host: Host address
            port: Port number
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_healthy, message)
        """
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout:
            attempts += 1
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    elapsed = time.time() - start_time
                    message = f"{service_name} is healthy on {host}:{port} (checked in {elapsed:.2f}s, {attempts} attempts)"
                    if self.verbose:
                        print(f"✅ {message}")
                    return True, message
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Attempt {attempts} failed for {service_name}: {e}")
            
            time.sleep(1)
        
        message = f"{service_name} failed health check on {host}:{port} after {timeout}s ({attempts} attempts)"
        if self.verbose:
            print(f"❌ {message}")
        return False, message
    
    def check_rabbitmq_management(self, host: str, port: int, timeout: int = 30) -> Tuple[bool, str]:
        """
        Check RabbitMQ management interface.
        
        Args:
            host: Host address
            port: Port number
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_healthy, message)
        """
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout:
            attempts += 1
            try:
                response = requests.get(f"http://{host}:{port}/api/overview", timeout=5)
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    message = f"RabbitMQ management is healthy on {host}:{port} (checked in {elapsed:.2f}s, {attempts} attempts)"
                    if self.verbose:
                        print(f"✅ {message}")
                    return True, message
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Attempt {attempts} failed for RabbitMQ management: {e}")
            
            time.sleep(1)
        
        message = f"RabbitMQ management failed health check on {host}:{port} after {timeout}s ({attempts} attempts)"
        if self.verbose:
            print(f"❌ {message}")
        return False, message
    
    def check_ollama(self, url: str = "http://localhost:11434", timeout: int = 30) -> Tuple[bool, str]:
        """
        Check Ollama service.
        
        Args:
            url: Ollama API URL
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_healthy, message)
        """
        start_time = time.time()
        attempts = 0
        
        while time.time() - start_time < timeout:
            attempts += 1
            try:
                response = requests.get(f"{url}/api/version", timeout=5)
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    message = f"Ollama is healthy on {url} (checked in {elapsed:.2f}s, {attempts} attempts)"
                    if self.verbose:
                        print(f"✅ {message}")
                    return True, message
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Attempt {attempts} failed for Ollama: {e}")
            
            time.sleep(1)
        
        message = f"Ollama failed health check on {url} after {timeout}s ({attempts} attempts)"
        if self.verbose:
            print(f"❌ {message}")
        return False, message
    
    def check_agent_containers(self, agents: List[str] = ['max', 'neo']) -> Tuple[bool, str]:
        """
        Check that agent containers are running and healthy.
        
        Args:
            agents: List of agent names to check
            
        Returns:
            Tuple of (is_healthy, message)
        """
        if AgentManager is None:
            message = "AgentManager not available - cannot check agent containers"
            if self.verbose:
                print(f"⚠️  {message}")
            return False, message
        
        try:
            manager = AgentManager()
            container_info = manager.get_agent_container_info()
            
            all_healthy = True
            messages = []
            
            for agent in agents:
                if agent not in container_info:
                    messages.append(f"Agent {agent} not found in configuration")
                    all_healthy = False
                    continue
                
                info = container_info[agent]
                if not info['running']:
                    messages.append(f"Agent {agent} ({info['container_name']}) is not running: {info['status']}")
                    all_healthy = False
                else:
                    messages.append(f"Agent {agent} ({info['container_name']}) is running: {info['status']}")
            
            message = "; ".join(messages)
            if all_healthy:
                if self.verbose:
                    print(f"✅ {message}")
                return True, message
            else:
                if self.verbose:
                    print(f"❌ {message}")
                return False, message
        except Exception as e:
            message = f"Failed to check agent containers: {e}"
            if self.verbose:
                print(f"❌ {message}")
            return False, message
    
    def check_all_services(self, include_optional: bool = False) -> Dict[str, Tuple[bool, str]]:
        """
        Check all required services.
        
        Args:
            include_optional: Whether to include optional services (RabbitMQ Management, Ollama)
            
        Returns:
            Dictionary mapping service names to (is_healthy, message) tuples
        """
        results = {}
        
        print("🔍 Checking required services for integration tests...")
        
        # Required services
        results['postgres'] = self.check_service_health("PostgreSQL", "localhost", 5432)
        results['redis'] = self.check_service_health("Redis", "localhost", 6379)
        results['rabbitmq'] = self.check_service_health("RabbitMQ", "localhost", 5672)
        results['agent_containers'] = self.check_agent_containers(['max', 'neo'])
        
        # Optional services
        if include_optional:
            results['rabbitmq_management'] = self.check_rabbitmq_management("localhost", 15672, timeout=10)
            results['ollama'] = self.check_ollama("http://localhost:11434", timeout=10)
        
        return results
    
    def print_summary(self, results: Dict[str, Tuple[bool, str]]):
        """Print summary of service check results."""
        print("\n" + "="*70)
        print("Service Health Check Summary")
        print("="*70)
        
        required_services = ['postgres', 'redis', 'rabbitmq', 'agent_containers']
        optional_services = ['rabbitmq_management', 'ollama']
        
        all_required_healthy = True
        for service in required_services:
            if service in results:
                is_healthy, message = results[service]
                status = "✅" if is_healthy else "❌"
                print(f"{status} {service.upper()}: {message}")
                if not is_healthy:
                    all_required_healthy = False
        
        print("\nOptional Services:")
        for service in optional_services:
            if service in results:
                is_healthy, message = results[service]
                status = "✅" if is_healthy else "⚠️ "
                print(f"{status} {service.upper()}: {message}")
        
        print("\n" + "="*70)
        if all_required_healthy:
            print("✅ All required services are healthy!")
            return 0
        else:
            print("❌ Some required services are not available")
            print("\nTo start services:")
            print("  docker-compose up -d postgres redis rabbitmq")
            print("  docker-compose up -d max neo")
            return 1


def main():
    """Main entry point for service health check script."""
    parser = argparse.ArgumentParser(description='Check service health for integration tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--service', '-s', help='Check specific service (postgres, redis, rabbitmq, agents, ollama)')
    parser.add_argument('--include-optional', action='store_true', help='Include optional services (RabbitMQ Management, Ollama)')
    
    args = parser.parse_args()
    
    checker = ServiceChecker(verbose=args.verbose)
    
    if args.service:
        # Check specific service
        service = args.service.lower()
        if service == 'postgres':
            is_healthy, message = checker.check_service_health("PostgreSQL", "localhost", 5432)
        elif service == 'redis':
            is_healthy, message = checker.check_service_health("Redis", "localhost", 6379)
        elif service == 'rabbitmq':
            is_healthy, message = checker.check_service_health("RabbitMQ", "localhost", 5672)
        elif service == 'rabbitmq-management':
            is_healthy, message = checker.check_rabbitmq_management("localhost", 15672)
        elif service == 'agents':
            is_healthy, message = checker.check_agent_containers(['max', 'neo'])
        elif service == 'ollama':
            is_healthy, message = checker.check_ollama("http://localhost:11434")
        else:
            print(f"❌ Unknown service: {service}")
            print("Available services: postgres, redis, rabbitmq, rabbitmq-management, agents, ollama")
            return 1
        
        if is_healthy:
            print(f"✅ {message}")
            return 0
        else:
            print(f"❌ {message}")
            return 1
    else:
        # Check all services
        results = checker.check_all_services(include_optional=args.include_optional)
        return checker.print_summary(results)


if __name__ == '__main__':
    sys.exit(main())


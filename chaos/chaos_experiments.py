#!/usr/bin/env python3
"""
Chaos Engineering Experiments for E-commerce Microservices

This script provides various chaos engineering experiments to test system resilience.
"""

import time
import random
import requests
import threading
import concurrent.futures
from datetime import datetime, timedelta
import argparse
import json
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ChaosExperiment:
    """Base class for chaos experiments"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None):
        self.name = name
        self.duration = duration
        self.target_service = target_service
        self.start_time = None
        self.end_time = None
        self.results = []
        
    def setup(self):
        """Setup experiment"""
        pass
    
    def execute(self):
        """Execute experiment"""
        raise NotImplementedError
    
    def cleanup(self):
        """Cleanup after experiment"""
        pass
    
    def run(self):
        """Run the complete experiment"""
        logger.info(f"Starting chaos experiment: {self.name}")
        self.start_time = datetime.now()
        
        try:
            self.setup()
            self.execute()
        except Exception as e:
            logger.error(f"Experiment {self.name} failed: {e}")
        finally:
            self.cleanup()
            self.end_time = datetime.now()
            
        logger.info(f"Completed chaos experiment: {self.name} in {self.end_time - self.start_time}")
        return self.results


class LatencyInjectionExperiment(ChaosExperiment):
    """Inject artificial latency into service calls"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None, 
                 latency_ms: int = 1000, probability: float = 0.2):
        super().__init__(name, duration, target_service)
        self.latency_ms = latency_ms
        self.probability = probability
        self.original_functions = {}
        
    def setup(self):
        """Setup latency injection"""
        logger.info(f"Setting up latency injection: {self.latency_ms}ms with {self.probability*100}% probability")
        
    def execute(self):
        """Execute latency injection experiment"""
        end_time = datetime.now() + timedelta(seconds=self.duration)
        
        while datetime.now() < end_time:
            # Simulate monitoring the system under latency
            if random.random() < 0.1:  # Monitor every ~10 requests
                result = self.monitor_system_health()
                self.results.append(result)
            
            time.sleep(1)
    
    def monitor_system_health(self):
        """Monitor system health during experiment"""
        try:
            # Check service health
            response = requests.get('http://localhost:8000/api/gateway/health/', timeout=5)
            health_status = response.json()
            
            # Check response times
            start_time = time.time()
            api_response = requests.get('http://localhost:8000/api/products/', timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            return {
                'timestamp': datetime.now().isoformat(),
                'health_status': health_status.get('status', 'unknown'),
                'response_time_ms': response_time,
                'status_code': api_response.status_code
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'health_status': 'error'
            }


class LoadTestExperiment(ChaosExperiment):
    """Generate load to test system under stress"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None,
                 concurrent_users: int = 100, requests_per_second: int = 50):
        super().__init__(name, duration, target_service)
        self.concurrent_users = concurrent_users
        self.requests_per_second = requests_per_second
        
    def execute(self):
        """Execute load test experiment"""
        logger.info(f"Starting load test: {self.concurrent_users} users, {self.requests_per_second} RPS")
        
        end_time = datetime.now() + timedelta(seconds=self.duration)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_users) as executor:
            futures = []
            
            while datetime.now() < end_time:
                # Submit requests
                for _ in range(min(self.requests_per_second, self.concurrent_users)):
                    future = executor.submit(self.make_request)
                    futures.append(future)
                
                time.sleep(1)  # Wait 1 second before next batch
                
                # Collect completed results
                completed_futures = [f for f in futures if f.done()]
                for future in completed_futures:
                    try:
                        result = future.result()
                        self.results.append(result)
                    except Exception as e:
                        self.results.append({
                            'timestamp': datetime.now().isoformat(),
                            'error': str(e),
                            'success': False
                        })
                    futures.remove(future)
            
            # Wait for remaining futures
            concurrent.futures.wait(futures, timeout=30)
    
    def make_request(self):
        """Make a single request"""
        endpoints = [
            '/api/products/',
            '/api/orders/',
            '/api/inventory/',
            '/api/gateway/health/'
        ]
        
        endpoint = random.choice(endpoints)
        start_time = time.time()
        
        try:
            response = requests.get(f'http://localhost:8000{endpoint}', timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            return {
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'status_code': response.status_code,
                'response_time_ms': response_time,
                'success': response.status_code < 400
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'error': str(e),
                'response_time_ms': response_time,
                'success': False
            }


class ServiceKillExperiment(ChaosExperiment):
    """Simulate service failures by making services unavailable"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None,
                 failure_probability: float = 0.1):
        super().__init__(name, duration, target_service)
        self.failure_probability = failure_probability
        
    def execute(self):
        """Execute service kill experiment"""
        logger.info(f"Starting service kill experiment with {self.failure_probability*100}% failure rate")
        
        end_time = datetime.now() + timedelta(seconds=self.duration)
        
        while datetime.now() < end_time:
            if random.random() < self.failure_probability:
                # Simulate service failure by overwhelming it
                self.simulate_service_failure()
            
            # Monitor system health
            result = self.monitor_circuit_breakers()
            self.results.append(result)
            
            time.sleep(5)
    
    def simulate_service_failure(self):
        """Simulate service failure"""
        logger.warning("Simulating service failure")
        
        # Send many requests to trigger circuit breaker
        def stress_service():
            for _ in range(10):
                try:
                    requests.get('http://localhost:8000/api/products/', timeout=0.1)
                except:
                    pass
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=stress_service)
            thread.start()
            threads.append(thread)
        
        # Don't wait for threads to complete (simulate failure)
    
    def monitor_circuit_breakers(self):
        """Monitor circuit breaker states"""
        try:
            response = requests.get('http://localhost:8000/api/resilience/circuit-breakers/', timeout=5)
            circuit_breakers = response.json()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'circuit_breakers': circuit_breakers,
                'system_health': 'monitoring'
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'system_health': 'error'
            }


class DatabaseConnectionExhaustionExperiment(ChaosExperiment):
    """Exhaust database connections to test connection pooling"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None,
                 connection_attempts: int = 50):
        super().__init__(name, duration, target_service)
        self.connection_attempts = connection_attempts
        
    def execute(self):
        """Execute database connection exhaustion experiment"""
        logger.info(f"Starting database connection exhaustion with {self.connection_attempts} concurrent connections")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.connection_attempts) as executor:
            # Submit long-running database operations
            futures = []
            for i in range(self.connection_attempts):
                future = executor.submit(self.create_long_running_connection, i)
                futures.append(future)
            
            # Monitor system during connection exhaustion
            end_time = datetime.now() + timedelta(seconds=self.duration)
            while datetime.now() < end_time:
                result = self.monitor_database_health()
                self.results.append(result)
                time.sleep(5)
            
            # Cancel all connections
            for future in futures:
                future.cancel()
    
    def create_long_running_connection(self, connection_id: int):
        """Create a long-running database connection"""
        try:
            # This would normally hold a database connection
            # For demo purposes, we'll make long-running API calls
            response = requests.get(
                'http://localhost:8000/api/products/', 
                timeout=self.duration,
                params={'connection_id': connection_id}
            )
            return response.status_code
        except Exception as e:
            logger.warning(f"Connection {connection_id} failed: {e}")
            return None
    
    def monitor_database_health(self):
        """Monitor database health"""
        try:
            # Check if database operations are still working
            response = requests.get('http://localhost:8000/api/products/', timeout=10)
            
            return {
                'timestamp': datetime.now().isoformat(),
                'database_health': 'healthy' if response.status_code == 200 else 'degraded',
                'response_time_ms': response.elapsed.total_seconds() * 1000,
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'database_health': 'failed',
                'error': str(e)
            }


class NetworkPartitionExperiment(ChaosExperiment):
    """Simulate network partitions between services"""
    
    def __init__(self, name: str, duration: int = 300, target_service: str = None,
                 partition_probability: float = 0.2):
        super().__init__(name, duration, target_service)
        self.partition_probability = partition_probability
        
    def execute(self):
        """Execute network partition experiment"""
        logger.info(f"Starting network partition experiment with {self.partition_probability*100}% partition probability")
        
        end_time = datetime.now() + timedelta(seconds=self.duration)
        
        while datetime.now() < end_time:
            if random.random() < self.partition_probability:
                self.simulate_network_partition()
            
            result = self.monitor_service_communication()
            self.results.append(result)
            
            time.sleep(3)
    
    def simulate_network_partition(self):
        """Simulate network partition by making requests fail"""
        logger.warning("Simulating network partition")
        
        # In a real scenario, this would involve iptables rules or network policies
        # For demo, we'll simulate by making requests to non-existent endpoints
        def make_failing_requests():
            for _ in range(5):
                try:
                    requests.get('http://localhost:9999/api/nonexistent/', timeout=1)
                except:
                    pass
        
        thread = threading.Thread(target=make_failing_requests)
        thread.start()
    
    def monitor_service_communication(self):
        """Monitor inter-service communication"""
        services = ['products', 'orders', 'payments', 'inventory']
        communication_health = {}
        
        for service in services:
            try:
                response = requests.get(f'http://localhost:8000/api/{service}/', timeout=5)
                communication_health[service] = {
                    'status': 'healthy' if response.status_code == 200 else 'degraded',
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                }
            except Exception as e:
                communication_health[service] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'service_communication': communication_health
        }


def run_experiment_suite():
    """Run a suite of chaos experiments"""
    experiments = [
        LatencyInjectionExperiment("latency_injection", duration=180, latency_ms=500, probability=0.3),
        LoadTestExperiment("load_test", duration=120, concurrent_users=50, requests_per_second=30),
        ServiceKillExperiment("service_kill", duration=150, failure_probability=0.15),
        DatabaseConnectionExhaustionExperiment("db_exhaustion", duration=120, connection_attempts=20),
        NetworkPartitionExperiment("network_partition", duration=180, partition_probability=0.25)
    ]
    
    all_results = {}
    
    for experiment in experiments:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running experiment: {experiment.name}")
        logger.info(f"{'='*60}")
        
        results = experiment.run()
        all_results[experiment.name] = {
            'start_time': experiment.start_time.isoformat(),
            'end_time': experiment.end_time.isoformat(),
            'duration': (experiment.end_time - experiment.start_time).total_seconds(),
            'results': results
        }
        
        # Wait between experiments
        logger.info("Waiting 30 seconds before next experiment...")
        time.sleep(30)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f'chaos_results_{timestamp}.json'
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"All experiments completed. Results saved to {results_file}")
    return all_results


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Chaos Engineering Experiments')
    parser.add_argument('--experiment', choices=[
        'latency', 'load', 'service_kill', 'db_exhaustion', 'network_partition', 'suite'
    ], default='suite', help='Experiment to run')
    parser.add_argument('--duration', type=int, default=300, help='Experiment duration in seconds')
    parser.add_argument('--target-service', help='Target service name')
    
    args = parser.parse_args()
    
    if args.experiment == 'suite':
        run_experiment_suite()
    elif args.experiment == 'latency':
        exp = LatencyInjectionExperiment("latency_injection", args.duration, args.target_service)
        exp.run()
    elif args.experiment == 'load':
        exp = LoadTestExperiment("load_test", args.duration, args.target_service)
        exp.run()
    elif args.experiment == 'service_kill':
        exp = ServiceKillExperiment("service_kill", args.duration, args.target_service)
        exp.run()
    elif args.experiment == 'db_exhaustion':
        exp = DatabaseConnectionExhaustionExperiment("db_exhaustion", args.duration, args.target_service)
        exp.run()
    elif args.experiment == 'network_partition':
        exp = NetworkPartitionExperiment("network_partition", args.duration, args.target_service)
        exp.run()


if __name__ == '__main__':
    main()

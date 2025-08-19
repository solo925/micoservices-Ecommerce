#!/usr/bin/env python3
"""
Load Test Runner for E-commerce Microservices

This script provides various load testing scenarios and configurations.
"""

import os
import sys
import time
import argparse
import subprocess
import json
from datetime import datetime
import requests


class LoadTestRunner:
    """Load test runner with various scenarios"""
    
    def __init__(self, host="http://localhost:8000"):
        self.host = host
        self.results_dir = "load_test_results"
        self.ensure_results_directory()
    
    def ensure_results_directory(self):
        """Create results directory if it doesn't exist"""
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def check_system_health(self):
        """Check if the system is ready for load testing"""
        print("🔍 Checking system health before load testing...")
        
        health_endpoints = [
            "/api/gateway/health/",
            "/api/resilience/health/",
            "/api/saga/health/"
        ]
        
        for endpoint in health_endpoints:
            try:
                response = requests.get(f"{self.host}{endpoint}", timeout=10)
                if response.status_code == 200:
                    print(f"✅ {endpoint} - Healthy")
                else:
                    print(f"⚠️  {endpoint} - Status: {response.status_code}")
            except Exception as e:
                print(f"❌ {endpoint} - Error: {e}")
                return False
        
        return True
    
    def run_baseline_test(self, duration=300, users=10):
        """Run baseline performance test"""
        print(f"🚀 Running baseline test: {users} users for {duration}s")
        
        cmd = [
            "locust",
            "-f", "comprehensive_load_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(max(1, users // 10)),
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/baseline_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/baseline_test"
        ]
        
        return self._run_locust_command(cmd, "baseline")
    
    def run_stress_test(self, duration=600, max_users=100, spawn_rate=5):
        """Run stress test with increasing load"""
        print(f"🔥 Running stress test: up to {max_users} users for {duration}s")
        
        cmd = [
            "locust",
            "-f", "comprehensive_load_test.py",
            "--host", self.host,
            "--users", str(max_users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/stress_test"
        ]
        
        return self._run_locust_command(cmd, "stress")
    
    def run_spike_test(self, duration=300, users=200):
        """Run spike test with sudden load increase"""
        print(f"⚡ Running spike test: {users} users instantly for {duration}s")
        
        cmd = [
            "locust",
            "-f", "comprehensive_load_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(users),  
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/spike_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/spike_test"
        ]
        
        return self._run_locust_command(cmd, "spike")
    
    def run_endurance_test(self, duration=3600, users=50):
        """Run endurance test for extended period"""
        print(f"🏃 Running endurance test: {users} users for {duration}s ({duration//3600}h)")
        
        cmd = [
            "locust",
            "-f", "comprehensive_load_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(max(1, users // 20)),
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/endurance_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/endurance_test"
        ]
        
        return self._run_locust_command(cmd, "endurance")
    
    def run_black_friday_test(self, duration=900, users=500):
        """Run Black Friday scenario test"""
        print(f"🛍️  Running Black Friday test: {users} users for {duration}s")
        
        # Create a special locust file for Black Friday scenario
        black_friday_content = '''
from comprehensive_load_test import BlackFridayScenario

if __name__ == "__main__":
    import os
    os.system("locust -f black_friday_test.py --host=http://localhost:8000")
'''
        
        with open("black_friday_test.py", "w") as f:
            f.write(black_friday_content)
        
        cmd = [
            "locust",
            "-f", "black_friday_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(users // 5), 
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/black_friday_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/black_friday_test"
        ]
        
        result = self._run_locust_command(cmd, "black_friday")
        
        # Clean up temporary file
        if os.path.exists("black_friday_test.py"):
            os.remove("black_friday_test.py")
        
        return result
    
    def run_chaos_resilience_test(self, duration=600, users=50):
        """Run test with chaos engineering enabled"""
        print(f"🌪️  Running chaos resilience test: {users} users for {duration}s")
        
        # Start chaos experiments before load test
        self._start_chaos_experiments()
        
        cmd = [
            "locust",
            "-f", "comprehensive_load_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(max(1, users // 10)),
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/chaos_resilience_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/chaos_resilience_test"
        ]
        
        return self._run_locust_command(cmd, "chaos_resilience")
    
    def run_api_only_test(self, duration=300, users=30):
        """Run API-only test (no web interface)"""
        print(f"🔌 Running API-only test: {users} users for {duration}s")
        
        # Create API-only test file
        api_only_content = '''
from comprehensive_load_test import APIUser

if __name__ == "__main__":
    import os
    os.system("locust -f api_only_test.py --host=http://localhost:8000")
'''
        
        with open("api_only_test.py", "w") as f:
            f.write(api_only_content)
        
        cmd = [
            "locust",
            "-f", "api_only_test.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(max(1, users // 5)),
            "--run-time", f"{duration}s",
            "--headless",
            "--print-stats",
            "--html", f"{self.results_dir}/api_only_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "--csv", f"{self.results_dir}/api_only_test"
        ]
        
        result = self._run_locust_command(cmd, "api_only")
        
        # Clean up temporary file
        if os.path.exists("api_only_test.py"):
            os.remove("api_only_test.py")
        
        return result
    
    def _start_chaos_experiments(self):
        """Start chaos engineering experiments"""
        experiments = [
            {
                "type": "latency",
                "service_name": "products-service",
                "duration": 300,
                "latency_ms": 200,
                "probability": 0.1
            },
            {
                "type": "failure",
                "service_name": "orders-service",
                "duration": 180,
                "failure_rate": 0.05
            }
        ]
        
        for experiment in experiments:
            try:
                response = requests.post(
                    f"{self.host}/api/resilience/chaos/",
                    json=experiment,
                    timeout=10
                )
                if response.status_code == 200:
                    print(f"✅ Started chaos experiment: {experiment['type']} on {experiment['service_name']}")
                else:
                    print(f"⚠️  Failed to start chaos experiment: {response.status_code}")
            except Exception as e:
                print(f"❌ Error starting chaos experiment: {e}")
    
    def _run_locust_command(self, cmd, test_type):
        """Run locust command and capture results"""
        print(f"Running command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # Run the load test
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Save test summary
            summary = {
                "test_type": test_type,
                "start_time": datetime.fromtimestamp(start_time).isoformat(),
                "end_time": datetime.fromtimestamp(end_time).isoformat(),
                "duration_seconds": duration,
                "command": ' '.join(cmd),
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            summary_file = f"{self.results_dir}/{test_type}_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            if result.returncode == 0:
                print(f"✅ {test_type.title()} test completed successfully in {duration:.2f}s")
                print(f"📊 Results saved to {self.results_dir}/")
            else:
                print(f"❌ {test_type.title()} test failed with return code {result.returncode}")
                print(f"Error output: {result.stderr}")
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Error running {test_type} test: {e}")
            return False
    
    def run_test_suite(self):
        """Run complete test suite"""
        print("🧪 Running complete load test suite...")
        
        if not self.check_system_health():
            print("❌ System health check failed. Aborting test suite.")
            return False
        
        tests = [
            ("baseline", lambda: self.run_baseline_test(duration=300, users=10)),
            ("stress", lambda: self.run_stress_test(duration=600, max_users=100)),
            ("spike", lambda: self.run_spike_test(duration=300, users=200)),
            ("api_only", lambda: self.run_api_only_test(duration=300, users=30)),
            ("chaos_resilience", lambda: self.run_chaos_resilience_test(duration=600, users=50))
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"Running {test_name} test...")
            print(f"{'='*60}")
            
            success = test_func()
            results[test_name] = success
            
            if success:
                print(f"✅ {test_name} test passed")
            else:
                print(f"❌ {test_name} test failed")
            
            # Wait between tests
            print("⏳ Waiting 30 seconds before next test...")
            time.sleep(30)
        
        # Generate final report
        self._generate_suite_report(results)
        
        print(f"\n{'='*60}")
        print("📋 Test Suite Complete")
        print(f"{'='*60}")
        
        passed = sum(1 for success in results.values() if success)
        total = len(results)
        
        print(f"Passed: {passed}/{total}")
        for test_name, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {test_name}")
        
        return passed == total
    
    def _generate_suite_report(self, results):
        """Generate comprehensive test suite report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"{self.results_dir}/test_suite_report_{timestamp}.json"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "host": self.host,
            "test_results": results,
            "summary": {
                "total_tests": len(results),
                "passed": sum(1 for success in results.values() if success),
                "failed": sum(1 for success in results.values() if not success),
                "success_rate": (sum(1 for success in results.values() if success) / len(results)) * 100
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Test suite report saved to {report_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='E-commerce Load Test Runner')
    parser.add_argument('--host', default='http://localhost:8000', help='Target host URL')
    parser.add_argument('--test', choices=[
        'baseline', 'stress', 'spike', 'endurance', 'black_friday', 
        'chaos_resilience', 'api_only', 'suite'
    ], default='baseline', help='Test type to run')
    parser.add_argument('--users', type=int, default=10, help='Number of users')
    parser.add_argument('--duration', type=int, default=300, help='Test duration in seconds')
    parser.add_argument('--spawn-rate', type=int, help='User spawn rate')
    
    args = parser.parse_args()
    
    runner = LoadTestRunner(host=args.host)
    
    if args.test == 'baseline':
        success = runner.run_baseline_test(duration=args.duration, users=args.users)
    elif args.test == 'stress':
        success = runner.run_stress_test(duration=args.duration, max_users=args.users)
    elif args.test == 'spike':
        success = runner.run_spike_test(duration=args.duration, users=args.users)
    elif args.test == 'endurance':
        success = runner.run_endurance_test(duration=args.duration, users=args.users)
    elif args.test == 'black_friday':
        success = runner.run_black_friday_test(duration=args.duration, users=args.users)
    elif args.test == 'chaos_resilience':
        success = runner.run_chaos_resilience_test(duration=args.duration, users=args.users)
    elif args.test == 'api_only':
        success = runner.run_api_only_test(duration=args.duration, users=args.users)
    elif args.test == 'suite':
        success = runner.run_test_suite()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

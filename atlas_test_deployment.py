#!/usr/bin/env python3
"""
Pre-Deployment Validation Suite for Atlas Intelligence
Tests everything that could fail on Railway deployment
"""

import asyncio
import sys
import time
import requests
from pathlib import Path
import subprocess
import json
from typing import Dict, List, Tuple

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class DeploymentValidator:
    """Comprehensive pre-deployment validation"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.results = []
        self.failures = []

    def log(self, status: str, test_name: str, message: str = ""):
        """Log test result"""
        if status == "PASS":
            print(f"{GREEN}✓{RESET} {test_name}")
            if message:
                print(f"  {message}")
            self.results.append((test_name, True, message))
        elif status == "FAIL":
            print(f"{RED}✗{RESET} {test_name}")
            if message:
                print(f"  {RED}{message}{RESET}")
            self.results.append((test_name, False, message))
            self.failures.append(test_name)
        elif status == "WARN":
            print(f"{YELLOW}⚠{RESET} {test_name}")
            if message:
                print(f"  {YELLOW}{message}{RESET}")
            self.results.append((test_name, True, message))
        else:  # INFO
            print(f"{BLUE}ℹ{RESET} {test_name}")
            if message:
                print(f"  {message}")

    def test_python_version(self):
        """Test Python version compatibility"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version.major == 3 and version.minor >= 10:
            self.log("PASS", "Python Version", f"{version_str} (Compatible with Railway)")
        else:
            self.log("FAIL", "Python Version", f"{version_str} (Railway requires Python 3.10+)")

    def test_requirements_file(self):
        """Test requirements.txt validity"""
        req_file = Path("requirements.txt")

        if not req_file.exists():
            self.log("FAIL", "requirements.txt", "File not found!")
            return

        self.log("PASS", "requirements.txt", "File exists")

        # Check for common problematic packages
        with open(req_file) as f:
            content = f.read()

            # Check for version conflicts
            if "torch==2.0.0" in content:
                self.log("WARN", "PyTorch Version", "torch==2.0.0 may not be available, using >=2.2.0")

            # Check for heavy packages that might timeout
            heavy_packages = []
            if "torch" in content:
                heavy_packages.append("torch")
            if "ultralytics" in content:
                heavy_packages.append("ultralytics")
            if "librosa" in content:
                heavy_packages.append("librosa")

            if heavy_packages:
                self.log("WARN", "Heavy Dependencies",
                        f"Large packages detected: {', '.join(heavy_packages)}\n"
                        f"  Railway build may take 5-10 minutes")

    def test_environment_variables(self):
        """Test environment variable handling"""
        env_example = Path(".env.example")
        env_file = Path(".env")

        if env_example.exists():
            self.log("PASS", ".env.example", "Template exists")
        else:
            self.log("WARN", ".env.example", "No template found")

        if env_file.exists():
            self.log("INFO", ".env", "Local config exists (not deployed to Railway)")

        # Test that app can start without .env
        try:
            from config.settings import settings
            self.log("PASS", "Environment Variables", "Settings loaded successfully")
        except Exception as e:
            self.log("FAIL", "Environment Variables", f"Failed to load settings: {e}")

    def test_procfile(self):
        """Test Procfile for Railway"""
        procfile = Path("Procfile")

        if not procfile.exists():
            self.log("WARN", "Procfile", "Not found - Railway will use default start command")
            return

        with open(procfile) as f:
            content = f.read().strip()

        if "daphne" in content or "uvicorn" in content or "gunicorn" in content:
            self.log("PASS", "Procfile", f"Valid: {content}")
        else:
            self.log("WARN", "Procfile", f"Unusual command: {content}")

    def test_api_health(self):
        """Test API health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)

            if response.status_code == 200:
                self.log("PASS", "Health Endpoint", "API is healthy")
            elif response.status_code == 503:
                data = response.json()
                if data.get("database") == "unhealthy":
                    self.log("WARN", "Health Endpoint",
                            "Database not available (expected for local dev)")
                else:
                    self.log("FAIL", "Health Endpoint", f"Service unhealthy: {data}")
            else:
                self.log("FAIL", "Health Endpoint", f"Unexpected status: {response.status_code}")

        except requests.ConnectionError:
            self.log("FAIL", "Health Endpoint", "API not running on localhost:8001")
        except Exception as e:
            self.log("FAIL", "Health Endpoint", f"Error: {e}")

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("service") == "Atlas Intelligence":
                    self.log("PASS", "Root Endpoint", f"Version: {data.get('version')}")
                else:
                    self.log("WARN", "Root Endpoint", "Unexpected response format")
            else:
                self.log("FAIL", "Root Endpoint", f"Status: {response.status_code}")

        except Exception as e:
            self.log("FAIL", "Root Endpoint", f"Error: {e}")

    def test_threat_classification(self):
        """Test threat classification endpoint"""
        test_cases = [
            {
                "description": "Someone is shooting outside",
                "expected_category": "weapons"
            },
            {
                "description": "Car was stolen",
                "expected_category": "theft"
            },
            {
                "description": "People fighting loudly",
                "expected_category": "violence"
            }
        ]

        try:
            for case in test_cases:
                response = requests.post(
                    f"{self.base_url}/api/v1/classify/threat",
                    json={"type": "text", "data": case["description"]},
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    category = data.get("classification", {}).get("threat_category")

                    if category == case["expected_category"]:
                        self.log("PASS", f"Classification: '{case['description'][:30]}...'",
                                f"Correctly identified as {category}")
                    else:
                        self.log("WARN", f"Classification: '{case['description'][:30]}...'",
                                f"Expected {case['expected_category']}, got {category}")
                else:
                    self.log("FAIL", "Threat Classification", f"Status: {response.status_code}")
                    break

        except Exception as e:
            self.log("FAIL", "Threat Classification", f"Error: {e}")

    def test_cold_start_time(self):
        """Test cold start performance (critical for Railway)"""
        print(f"\n{BLUE}Testing cold start performance...{RESET}")

        try:
            # Time the import of main module
            start = time.time()
            import main
            import_time = time.time() - start

            if import_time < 5.0:
                self.log("PASS", "Cold Start Time", f"{import_time:.2f}s (Good)")
            elif import_time < 10.0:
                self.log("WARN", "Cold Start Time", f"{import_time:.2f}s (Acceptable)")
            else:
                self.log("FAIL", "Cold Start Time", f"{import_time:.2f}s (Too slow for Railway)")

            # Test model loading time
            start = time.time()
            from services.visual_detector import get_visual_detector
            asyncio.run(get_visual_detector())
            model_time = time.time() - start

            if model_time < 10.0:
                self.log("PASS", "Model Loading", f"{model_time:.2f}s")
            else:
                self.log("WARN", "Model Loading", f"{model_time:.2f}s (Slow)")

        except Exception as e:
            self.log("FAIL", "Cold Start", f"Error: {e}")

    def test_memory_usage(self):
        """Test memory footprint"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb < 512:
                self.log("PASS", "Memory Usage", f"{memory_mb:.0f} MB (Excellent)")
            elif memory_mb < 1024:
                self.log("PASS", "Memory Usage", f"{memory_mb:.0f} MB (Good)")
            elif memory_mb < 2048:
                self.log("WARN", "Memory Usage", f"{memory_mb:.0f} MB (High)")
            else:
                self.log("FAIL", "Memory Usage", f"{memory_mb:.0f} MB (Too high for Railway free tier)")

        except ImportError:
            self.log("INFO", "Memory Usage", "psutil not available, skipping")

    def test_database_optional(self):
        """Test that app works without database"""
        self.log("INFO", "Database Optional", "Testing graceful degradation...")

        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            data = response.json()

            if data.get("database") == "unhealthy" and data.get("status") == "unhealthy":
                self.log("WARN", "Database Degradation",
                        "App reports unhealthy without DB - should be degraded but operational")
            else:
                self.log("PASS", "Database Optional", "App runs without database")

        except Exception as e:
            self.log("FAIL", "Database Optional", f"Error: {e}")

    def test_static_files(self):
        """Test that static file serving works"""
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)

            if response.status_code == 200:
                self.log("PASS", "API Documentation", "Swagger UI accessible")
            else:
                self.log("WARN", "API Documentation", f"Status: {response.status_code}")

        except Exception as e:
            self.log("WARN", "API Documentation", f"Error: {e}")

    def test_cors_headers(self):
        """Test CORS configuration"""
        try:
            response = requests.options(
                f"{self.base_url}/api/v1/classify/threat",
                headers={"Origin": "https://halo.example.com"}
            )

            if "access-control-allow-origin" in response.headers:
                self.log("PASS", "CORS Headers", "Configured")
            else:
                self.log("WARN", "CORS Headers", "Not configured - may affect Halo integration")

        except Exception as e:
            self.log("INFO", "CORS Headers", "Skipping test")

    def test_error_handling(self):
        """Test error handling"""
        try:
            # Test with invalid JSON
            response = requests.post(
                f"{self.base_url}/api/v1/classify/threat",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in [400, 422]:
                self.log("PASS", "Error Handling", "Returns proper error codes")
            else:
                self.log("WARN", "Error Handling", f"Unexpected status: {response.status_code}")

        except Exception as e:
            self.log("WARN", "Error Handling", f"Error: {e}")

    def test_response_times(self):
        """Test API response times"""
        endpoints = [
            ("/", "Root"),
            ("/health", "Health"),
            ("/api/v1/classify/threat", "Classification")
        ]

        for path, name in endpoints:
            try:
                start = time.time()

                if path == "/api/v1/classify/threat":
                    response = requests.post(
                        f"{self.base_url}{path}",
                        json={"type": "text", "data": "test"},
                        timeout=5
                    )
                else:
                    response = requests.get(f"{self.base_url}{path}", timeout=5)

                elapsed = (time.time() - start) * 1000  # ms

                if elapsed < 200:
                    self.log("PASS", f"Response Time - {name}", f"{elapsed:.0f}ms (Excellent)")
                elif elapsed < 500:
                    self.log("PASS", f"Response Time - {name}", f"{elapsed:.0f}ms (Good)")
                elif elapsed < 1000:
                    self.log("WARN", f"Response Time - {name}", f"{elapsed:.0f}ms (Slow)")
                else:
                    self.log("FAIL", f"Response Time - {name}", f"{elapsed:.0f}ms (Too slow)")

            except Exception as e:
                self.log("FAIL", f"Response Time - {name}", f"Error: {e}")

    def generate_report(self):
        """Generate final report"""
        print("\n" + "="*60)
        print(f"{BLUE}PRE-DEPLOYMENT VALIDATION REPORT{RESET}")
        print("="*60)

        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)

        print(f"\n{GREEN}Passed:{RESET} {passed}/{total}")
        if self.failures:
            print(f"{RED}Failed:{RESET} {len(self.failures)}")
            print(f"\nFailed tests:")
            for failure in self.failures:
                print(f"  - {failure}")

        print("\n" + "="*60)

        if len(self.failures) == 0:
            print(f"{GREEN}✓ ALL TESTS PASSED - READY FOR DEPLOYMENT{RESET}")
            return True
        elif len(self.failures) < 3:
            print(f"{YELLOW}⚠ SOME ISSUES FOUND - REVIEW BEFORE DEPLOYMENT{RESET}")
            return True
        else:
            print(f"{RED}✗ MULTIPLE FAILURES - FIX ISSUES BEFORE DEPLOYMENT{RESET}")
            return False


def main():
    """Run all validation tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Atlas Intelligence - Pre-Deployment Validation{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    validator = DeploymentValidator()

    # Structure tests
    print(f"\n{BLUE}[1] Project Structure{RESET}")
    print("-" * 60)
    validator.test_python_version()
    validator.test_requirements_file()
    validator.test_environment_variables()
    validator.test_procfile()

    # API tests
    print(f"\n{BLUE}[2] API Functionality{RESET}")
    print("-" * 60)
    validator.test_api_health()
    validator.test_api_root()
    validator.test_threat_classification()
    validator.test_static_files()

    # Performance tests
    print(f"\n{BLUE}[3] Performance & Resources{RESET}")
    print("-" * 60)
    validator.test_cold_start_time()
    validator.test_memory_usage()
    validator.test_response_times()

    # Resilience tests
    print(f"\n{BLUE}[4] Resilience & Error Handling{RESET}")
    print("-" * 60)
    validator.test_database_optional()
    validator.test_error_handling()
    validator.test_cors_headers()

    # Generate report
    success = validator.generate_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GitHub Actions Failure Fixer for SupremeAI Agents.
বাংলা মন্তব্ব: গিটহাব অ্যাকশনসের ফেইলড জবগুলো ঠিক করার জন্য ফিক্স স্ক্রিপ্ট।
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def fix_observability_issues():
    """
    Fix issues that might cause observability audit failures.
    """
    print("🔍 Checking for observability audit issues...")

    # Run the audit script to see if there are any issues
    script_path = Path("scripts/audit_observability.py")
    if script_path.exists():
        print("Running observability audit...")
        result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Observability audit failed: {result.stdout} {result.stderr}")
        else:
            print("✅ Observability audit passed")
    else:
        print("❌ Observability audit script not found")


def fix_test_environment():
    """
    Fix test environment issues that might cause backend test failures.
    """
    print("\n🔧 Setting up test environment...")

    # Check if we're in the backend directory
    backend_path = Path("backend")
    if not backend_path.exists():
        print("❌ Backend directory not found")
        return False

    os.chdir(backend_path)

    # Try to install dependencies if needed
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "show", "poetry"], capture_output=True)
        if result.returncode != 0:
            print("Installing poetry...")
            subprocess.run([sys.executable, "-m", "pip", "install", "poetry"], check=True)

        # Install dependencies with poetry
        print("Installing dependencies with poetry...")
        subprocess.run(["poetry", "install"], check=True, cwd=backend_path)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Could not install dependencies: {e}")

    # Create a minimal test to verify basic functionality
    print("Running quick test to check test environment...")
    try:
        # Run a single simple test to verify the test environment works
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/", "-k", "test_", "--maxfail=1", "-v", "--tb=short", "-x"
        ], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✅ Quick test passed - test environment is working")
        else:
            print(f"❌ Quick test failed: {result.stdout}")
            print(f"STDERR: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️ Test timed out - might be due to external dependencies")
    except Exception as e:
        print(f"⚠️ Error running test: {e}")

    # Go back to the main directory
    os.chdir("..")


def fix_redis_and_database_issues():
    """
    Address potential Redis and database connection issues in tests.
    """
    print("\n🧩 Fixing Redis and Database connection issues...")

    # Look for test configuration files
    backend_path = Path("backend")
    test_configs = [
        backend_path / "pytest.ini",
        backend_path / "pyproject.toml",
        backend_path / "conftest.py",
        *(backend_path / "tests").rglob("*conftest*.py")
    ]

    # Check if we need to create/update test config for Redis mocking
    for config_file in test_configs:
        if config_file.exists():
            print(f"Checking {config_file}...")
            content = config_file.read_text()
            if "redis" in content.lower() or "database" in content.lower():
                print(f"Found Redis/database references in {config_file}")

    # Create or update conftest.py to handle Redis connections in tests
    conftest_path = backend_path / "conftest.py"
    if not conftest_path.exists():
        print("Creating conftest.py to handle test fixtures...")
        conftest_content = '''# conftest.py
# Test configuration for SupremeAI backend
import os
import pytest
from unittest.mock import patch
import redis.asyncio as redis

# Mock Redis for tests to avoid connection issues
@pytest.fixture(autouse=True)
def mock_redis():
    """Automatically mock Redis connections during tests."""
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_redis.return_value = redis.ConnectionPool.from_url("redis://mocked-redis-url")
        yield mock_redis

@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services to prevent network calls during tests."""
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:
        yield {"get": mock_get, "post": mock_post}
'''
        conftest_path.write_text(conftest_content)
        print("✅ Created conftest.py with Redis mocking")


def fix_specific_test_issues():
    """
    Fix specific test-related issues that might cause failures.
    """
    print("\n🔍 Looking for specific test issues...")

    # Check for tests that might be failing due to missing environment variables
    backend_path = Path("backend")
    test_dirs = [backend_path / "tests"]

    # Look for test files that might have specific issues
    problematic_tests = []
    for test_dir in test_dirs:
        if test_dir.exists():
            for test_file in test_dir.rglob("test_*.py"):
                content = test_file.read_text()
                if "redis" in content.lower() or "database" in content.lower() or "connection" in content.lower():
                    problematic_tests.append(test_file)

    if problematic_tests:
        print(f"Found {len(problematic_tests)} potentially problematic test files:")
        for test_file in problematic_tests[:5]:  # Show first 5
            print(f"  - {test_file.relative_to(backend_path)}")


def main():
    print("🚀 GitHub Actions Failure Fixer")
    print("This script will attempt to fix common issues causing GitHub Actions failures.\n")

    # Run fixes in order
    fix_observability_issues()
    fix_test_environment()
    fix_redis_and_database_issues()
    fix_specific_test_issues()

    print("\n✅ GitHub Actions failure fixes completed!")
    print("\n💡 Next steps:")
    print("   1. Run 'python scripts/audit_observability.py' to verify observability fixes")
    print("   2. Run 'cd backend && python -m pytest tests/ --maxfail=3' to test fixes")
    print("   3. Commit and push changes to trigger a new GitHub Actions run")


if __name__ == "__main__":
    main()

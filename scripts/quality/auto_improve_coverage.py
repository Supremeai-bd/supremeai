#!/usr/bin/env python3
"""
Auto Improve Coverage Script
Automatically runs tests with coverage, identifies gaps, and generates tests to improve coverage.
"""

import os
import sys
import subprocess
import argparse
import asyncio
from pathlib import Path

# Add the parent directory of backend to the path so we can import backend.tools
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.tools.auto_coverage_improver import AutoCoverageImprover


def run_tests_with_coverage(coverage_file="coverage.xml"):
    """Run tests with coverage and generate coverage report."""
    print("Running tests with coverage...")
    
    # Change to backend directory where pyproject.toml is
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    
    # Run pytest with coverage
    cmd = [
        "poetry", "run", "pytest",
        "--cov=backend",
        f"--cov-report=xml:{coverage_file}",
        "--cov-report=term-missing",
        "-q"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        print("Test output:")
        print(result.stdout)
        if result.stderr:
            print("Test errors:")
            print(result.stderr)
            
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Automatically improve test coverage by generating tests for uncovered code"
    )
    parser.add_argument(
        "--coverage-target",
        type=float,
        default=80.0,
        help="Minimum coverage percentage to aim for (default: 80.0)"
    )
    parser.add_argument(
        "--coverage-report",
        default="coverage.xml",
        help="Path to coverage report file (default: coverage.xml)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Identify gaps and generate tests without saving files or running tests"
    )
    parser.add_argument(
        "--skip-test-run", 
        action="store_true", 
        help="Skip running tests, only generate based on existing coverage report"
    )
    
    args = parser.parse_args()
    
    # Change to project root directory
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    
    print(f"Working in: {project_root}")
    print(f"Coverage target: {args.coverage_target}%")
    print(f"Dry run: {args.dry_run}")
    print(f"Skip test run: {args.skip_test_run}")
    print("-" * 50)
    
    # Step 1: Run tests with coverage (unless skipping)
    coverage_report_path = project_root / "backend" / args.coverage_report
    
    if not args.skip_test_run:
        success = run_tests_with_coverage(str(coverage_report_path))
        if not success:
            print("Warning: Tests had failures or errors, but continuing with coverage analysis...")
    else:
        if not coverage_report_path.exists():
            print(f"Error: Coverage report not found at {coverage_report_path}")
            print("Run without --skip-test-run to generate a coverage report first.")
            return 1
        print(f"Using existing coverage report: {coverage_report_path}")
    
    # Step 2: Use auto coverage improver to find gaps and generate tests
    print("\nAnalyzing coverage gaps and generating tests...")
    
    improver = AutoCoverageImprover()
    result = await improver.run(
        coverage_report_path=str(coverage_report_path),
        min_coverage_target=args.coverage_target,
        dry_run=args.dry_run
    )
    
    # Step 3: Report results
    print("\n" + "="*50)
    print("COVERAGE IMPROVEMENT RESULTS")
    print("="*50)
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"Message: {result.get('message', 'N/A')}")
    print(f"Gaps found: {result.get('gaps_found', 0)}")
    print(f"Tests generated: {result.get('tests_generated', 0)}")
    
    if result.get('results'):
        print("\nDetailed results:")
        for i, res in enumerate(result['results'], 1):
            status = res.get('status', 'unknown')
            file_path = res.get('file_path', 'unknown')
            print(f"  {i}. {file_path}: {status}")
    
    print("="*50)
    
    if result.get('status') == 'completed' and result.get('tests_generated', 0) > 0:
        print("\nNext steps:")
        print("1. Review the generated test files")
        print("2. Run the tests to verify they pass")
        print("3. Run coverage again to see improved coverage")
        
        if not args.dry_run:
            print("\nTo run tests with coverage again:")
            print("  poetry run pytest --cov=backend --cov-report=term-missing")
    
    return 0 if result.get('status') in ['success', 'completed'] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
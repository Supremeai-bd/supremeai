"""
Unified collector runner for SupremeAI resource collection
Runs collectors as subprocesses for maximum isolation and reliability
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


def run_collector(script_path: str, description: str) -> bool:
    """
    Run a collector script as a subprocess
    
    Args:
        script_path: Path to the collector script
        description: Human-readable description
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Running {description}...")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run the script as a subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            cwd="C:/Users/n/supremeai/supremeai_2.0",  # Set working directory to project root
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check return code
        if result.returncode == 0:
            elapsed = time.time() - start_time
            print(f"\n[SUCCESS] {description} completed successfully in {elapsed:.2f}s")
            return True
        else:
            print(f"\n[ERROR] {description} failed with exit code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] {description} timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"\n[ERROR] {description} failed with exception: {e}")
        return False


def main():
    """Main function to run all collectors"""
    print("Starting SupremeAI resource collection...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Define collectors to run
    collectors = [
        # Scrapers
        ("scripts/resource_collection/awesome_selfhosted.py", "Awesome Self-Hosted Scraper"),
        ("scripts/resource_collection/awesome_go.py", "Awesome Go Scraper"),
        ("scripts/resource_collection/awesome_python.py", "Awesome Python Scraper"),
        # API Clients
        ("scripts/resource_collection/ossinsight/test.py", "OSS Insight API Client"),
        # Add more collectors here as they are implemented
    ]
    
    # Track results
    results = []
    start_time = datetime.now()
    
    # Run each collector
    for script_path, description in collectors:
        success = run_collector(script_path, description)
        results.append((description, success))
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*60}")
    print("COLLECTION SUMMARY")
    print(f"{'='*60}")
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "[SUCCESS]" if success else "[FAILED]"
        print(f"{status}: {description}")
    
    print(f"\nTotal: {successful}/{total} collectors successful")
    print(f"Duration: {duration}")
    
    if successful == total:
        print("\n🎉 All collectors completed successfully!")
        return 0
    else:
        print(f"\n❌ {total - successful} collector(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
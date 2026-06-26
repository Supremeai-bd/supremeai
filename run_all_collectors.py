"""
Unified runner for all SupremeAI resource collectors
"""

import sys
from pathlib import Path

# Add the resource_collection directory to the path
sys.path.insert(0, str(Path(__file__).parent / "resource_collection"))

import awesome_selfhosted
import awesome_go
import awesome_python
from ossinsight.client import main_ossinsight

def run_all_collectors():
    """Run all available collectors and report results"""
    print("=" * 60)
    print("SUPREMEAI RESOURCE COLLECTION SYSTEM")
    print("=" * 60)
    
    collectors = [
        ("Awesome Self-Hosted Scraper", awesome_selfhosted.main),
        ("Awesome Go Scraper", awesome_go.main),
        ("Awesome Python Scraper", awesome_python.main),
        ("OSS Insight API Client", main_ossinsight),
    ]
    
    results = []
    
    for name, main_func in collectors:
        print(f"\n{'-' * 50}")
        print(f"Running: {name}")
        print(f"{'-' * 50}")
        
        try:
            result = main_func()
            if result == 0:
                print(f"[SUCCESS] {name} completed successfully")
                results.append((name, True, None))
            else:
                print(f"[ERROR] {name} failed with exit code {result}")
                results.append((name, False, f"Exit code {result}"))
        except Exception as e:
            print(f"[ERROR] {name} failed with exception: {e}")
            results.append((name, False, str(e)))
    
    # Summary
    print(f"\n{'=' * 60}")
    print("COLLECTION SUMMARY")
    print(f"{'=' * 60}")
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {name}")
        if not success:
            print(f"      Error: {error}")
    
    print(f"\nTotal: {passed}/{total} collectors successful")
    
    if passed == total:
        print("\n🎉 ALL COLLECTORS COMPLETED SUCCESSFULLY!")
        return 0
    else:
        print("\n❌ SOME COLLECTORS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_collectors())
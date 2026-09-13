#!/usr/bin/env python3
"""Verify canonical startup command and health endpoints."""

import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

def main():
    print("Starting canonical entrypoint in test environment...")
    proc = subprocess.Popen([sys.executable, "main.py"], cwd="backend")
    
    try:
        print("Waiting 10 seconds for initialization...")
        time.sleep(10)
        
        if proc.poll() is not None:
            print("❌ Server crashed during startup!", file=sys.stderr)
            return 1
        print("✅ Server process is running.")

        port = os.getenv("PORT", "8080")
        base = f"http://127.0.0.1:{port}"
        print(f"Probing {base}/api/v1/health/live ...")
        
        live_ok = False
        for i in range(1, 31):
            try:
                with urllib.request.urlopen(f"{base}/api/v1/health/live", timeout=3) as resp:
                    if resp.status == 200:
                        print(f"✅ /api/v1/health/live returned 200 (attempt {i})")
                        live_ok = True
                        break
            except Exception as exc:
                print(f"attempt {i}: {exc}; retrying in 2s...")
            time.sleep(2)

        if not live_ok:
            print("❌ /api/v1/health/live did not return 200 within 60s", file=sys.stderr)
            return 1

        print(f"Probing {base}/api/v1/health/ready ...")
        try:
            with urllib.request.urlopen(f"{base}/api/v1/health/ready", timeout=5) as resp:
                if resp.status != 200:
                    print(f"❌ /api/v1/health/ready returned HTTP {resp.status}", file=sys.stderr)
                    return 1
        except Exception as exc:
            print(f"❌ /api/v1/health/ready probe failed: {exc}", file=sys.stderr)
            return 1

        print("✅ Canonical startup + health endpoint verification PASSED")
        return 0

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == "__main__":
    sys.exit(main())

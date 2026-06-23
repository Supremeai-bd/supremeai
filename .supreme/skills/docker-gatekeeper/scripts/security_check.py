#!/usr/bin/env python3
import sys
from pathlib import Path

def run_security_check():
    dockerfiles = [
        p for p in Path(".").glob("**/Dockerfile*")
        if not any(part in p.parts for part in ["node_modules", ".git", ".venv", ".turbo", "dist", "build"])
        and p.is_file()
    ]
    if not dockerfiles:
        print("No Dockerfile found. Skipping security check.")
        sys.exit(0)

    issues = []
    for df in dockerfiles:
        content = df.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        has_user = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("USER "):
                has_user = True
            if "ENV " in stripped and any(sec in stripped.upper() for sec in ["SECRET", "PASSWORD", "KEY", "TOKEN"]):
                issues.append(f"[{df}] Potential hardcoded secret in ENV instruction: {stripped}")
                
        if not has_user:
            issues.append(f"[{df}] Missing non-root USER instruction (runs as root by default).")

    if issues:
        print("[FAIL] Docker Security Check Failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
        
    print("[PASS] Docker Security Check Passed.")
    sys.exit(0)

if __name__ == "__main__":
    run_security_check()

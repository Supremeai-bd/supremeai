#!/usr/bin/env python3
import sys
from pathlib import Path

def run_compliance_check():
    dockerfiles = [
        p for p in Path(".").glob("**/Dockerfile*")
        if not any(part in p.parts for part in ["node_modules", ".git", ".venv", ".turbo", "dist", "build"])
        and p.is_file()
    ]
    if not dockerfiles:
        print("No Dockerfile found. Skipping compliance check.")
        sys.exit(0)

    issues = []
    allowed_bases = ["python", "node", "ubuntu", "alpine", "golang", "debian"]
    
    for df in dockerfiles:
        content = df.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("FROM "):
                base_image = stripped.split()[1]
                base_name = base_image.split(":")[0].split("/")[-1]
                if not any(allowed in base_name.lower() for allowed in allowed_bases):
                    issues.append(f"[{df}] Non-approved base image: '{base_image}'. Must use one of: {allowed_bases}")
            
            if stripped.startswith("ADD ") and not (".tar" in stripped or ".zip" in stripped):
                issues.append(f"[{df}] Use COPY instead of ADD unless copying tar/zip archives.")

    if issues:
        print("[FAIL] Docker Compliance Check Failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
        
    print("[PASS] Docker Compliance Check Passed.")
    sys.exit(0)

if __name__ == "__main__":
    run_compliance_check()

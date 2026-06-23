#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> supreme-docker-analyzer.py
# project >> SupremeAI 2.0
# purpose >> Docker settings
# module >> scripts
# ============================================================================
import os
import sys
import json
import subprocess
import yaml
from pathlib import Path

class SupremeDockerAnalyzer:
    def __init__(self, image_name, service_name="default"):
        self.image_name = image_name
        self.service_name = service_name
        self.limits = self.load_limits()
        
    def load_limits(self):
        limits_path = Path("config/docker-limits.yml")
        if limits_path.exists():
            with open(limits_path, "r") as f:
                data = yaml.safe_load(f)
                return data.get("limits", {}).get(self.service_name, data.get("limits", {}).get("default", {}))
        return {"max_size_mb": 500, "warn_size_mb": 300}

    def analyze(self):
        # Retrieve image size
        size_cmd = f"docker image inspect {self.image_name} --format='{{{{.Size}}}}'"
        try:
            size_bytes = int(subprocess.check_output(size_cmd, shell=True).decode('utf-8').strip())
            size_mb = size_bytes / (1024 * 1024)
        except Exception as e:
            print(f"❌ Failed to get image size: {e}")
            return {"status": "FAIL", "reason": f"Could not inspect image: {e}", "size_mb": 0}

        max_size = self.limits.get("max_size_mb", 500)
        warn_size = self.limits.get("warn_size_mb", 300)

        status = "PASS"
        if size_mb > max_size:
            status = "FAIL"
        elif size_mb > warn_size:
            status = "WARN"

        # Retrieve large layers
        history_cmd = f"docker history {self.image_name} --no-trunc --format '{{{{.Size}}}}\t{{{{.CreatedBy}}}}'"
        try:
            history_output = subprocess.check_output(history_cmd, shell=True).decode('utf-8')
            layers = []
            for line in history_output.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t', 1)
                size_str = parts[0]
                created_by = parts[1] if len(parts) > 1 else ""
                layers.append({"size": size_str, "created_by": created_by})
        except Exception:
            layers = []

        return {
            "status": status,
            "size_mb": round(size_mb, 2),
            "max_size_mb": max_size,
            "warn_size_mb": warn_size,
            "large_layers": layers[:10]
        }

if __name__ == '__main__':
    image = os.getenv("IMAGE_NAME", "supremeai-api:test")
    service = os.getenv("SERVICE_NAME", "default")
    analyzer = SupremeDockerAnalyzer(image, service)
    result = analyzer.analyze()
    print(json.dumps(result, indent=2))
    
    with open("docker_analysis.json", "w") as f:
        json.dump(result, f, indent=2)
        
    if result["status"] == "FAIL":
        sys.exit(1)
    sys.exit(0)

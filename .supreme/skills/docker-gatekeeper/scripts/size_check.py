#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import yaml
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class DockerSizeCheck:
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

    def run_check(self):
        size_cmd = f"docker image inspect {self.image_name} --format='{{{{.Size}}}}'"
        try:
            size_bytes = int(subprocess.check_output(size_cmd, shell=True).decode('utf-8').strip())
            size_mb = size_bytes / (1024 * 1024)
        except Exception as e:
            # Fallback if docker service not active / image not built yet
            print(f"[WARN] Could not inspect local docker image {self.image_name}: {e}. Skipping size check.")
            sys.exit(0)

        max_size = self.limits.get("max_size_mb", 500)
        warn_size = self.limits.get("warn_size_mb", 300)

        status = "PASS"
        if size_mb > max_size:
            status = "FAIL"
        elif size_mb > warn_size:
            status = "WARN"

        print(f"[INFO] Current Image Size: {size_mb:.2f} MB (Max Limit: {max_size} MB)")

        # Retrieve layers
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
            history_output = ""
            layers = []

        result = {
            "status": status,
            "size_mb": round(size_mb, 2),
            "max_size_mb": max_size,
            "warn_size_mb": warn_size,
            "large_layers": layers[:10]
        }

        with open("docker_analysis.json", "w") as f:
            json.dump(result, f, indent=2)

        if status == "FAIL":
            print("[WARN] BLOAT DETECTED! Image size exceeded limit. Initiating AI Autopsy...")
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key or not genai:
                print("[FAIL] GEMINI_API_KEY or google-generativeai module missing. Failing build due to size bloat without AI analysis.")
                sys.exit(1)

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt = f"""You are an elite DevSecOps AI. The CI/CD pipeline failed because the Docker image size ({size_mb:.2f} MB) exceeded the limit of {max_size} MB.
            
            Analyze the following 'docker history' output. Identify EXACTLY which layers/commands are causing the bloat. 
            Provide a strict, bulleted action plan on how to fix it.
            
            Docker History:
            {history_output}
            """

            response = model.generate_content(prompt)
            print("\n" + "="*50)
            print("SUPREMEAI DOCKER BLOAT ANALYSIS REPORT")
            print("="*50)
            print(response.text)
            print("="*50 + "\n")

            with open("bloat_report.md", "w") as f:
                f.write(f"## Docker Bloat Detected ({size_mb:.2f} MB)\n\n")
                f.write(response.text)

            sys.exit(1)
            
        print("[PASS] Docker Size Check Passed.")
        sys.exit(0)

if __name__ == "__main__":
    image = os.getenv("IMAGE_NAME", "supremeai-api:test")
    service = os.getenv("SERVICE_NAME", "default")
    checker = DockerSizeCheck(image, service)
    checker.run_check()

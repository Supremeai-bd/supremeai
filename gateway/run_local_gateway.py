import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Load secrets from Infisical sync file
secrets_file = os.path.join(repo_root, ".env.secrets")
if os.path.exists(secrets_file):
    with open(secrets_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("\"'")
    print("[AUTH] Loaded Gemini, Groq, OpenRouter & Webhook keys from Infisical!")

import uvicorn
from gateway.serve import app

if __name__ == "__main__":
    print("[INIT] Starting SupremeAI Gateway on 8080 with Multi-Engine Pool...")
    uvicorn.run(app, host="127.0.0.1", port=8080)

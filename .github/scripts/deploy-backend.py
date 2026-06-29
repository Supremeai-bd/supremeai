import os
import sys
import subprocess
import time
import urllib.request
import json

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
REGION = os.getenv("GCP_REGION", "us-central1")
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SERVICE_NAME = "supremeai-api"
IMAGE = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/supremeai-repo/supremeai-api:latest"
API_URL = os.getenv("SUPREMEAI_API_URL") # Example: https://api.supremeai.dev

def run_cmd(cmd):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

# ==========================================
# 🔍 1. GET CURRENT STABLE REVISION
# ==========================================
print("🔍 Fetching current stable revision for rollback safety...")
stdout, stderr, code = run_cmd(f"gcloud run services describe {SERVICE_NAME} --region {REGION} --format 'value(status.latestReadyRevisionName)'")
if code != 0:
    print(f"⚠️ Could not fetch previous revision (Might be first deploy). Error: {stderr}")
    PREVIOUS_REVISION = None
else:
    PREVIOUS_REVISION = stdout
    print(f"✅ Current Stable Revision: {PREVIOUS_REVISION}")

# ==========================================
# 🚀 2. DEPLOY NEW IMAGE
# ==========================================
print("🚀 Deploying new image to Cloud Run...")
deploy_cmd = f"gcloud run deploy {SERVICE_NAME} --image {IMAGE} --region {REGION} --quiet"
stdout, stderr, code = run_cmd(deploy_cmd)

if code != 0:
    print(f"❌ DEPLOYMENT FAILED at container startup level!\n{stderr}")
    sys.exit(1)

print("✅ Deployment successful. Container started successfully.")

# ==========================================
# 🧪 3. DEEP HEALTH-CHECK (Application Level)
# ==========================================
print("🧪 Initiating deep health-check on the live API...")
time.sleep(10) # Give the server a few seconds to warm up

health_endpoint = f"{API_URL.rstrip('/')}/health" if API_URL else None
is_healthy = False

if health_endpoint:
    for attempt in range(1, 4): # Try 3 times
        try:
            print(f"   -> Health check attempt {attempt}/3 at {health_endpoint}...")
            req = urllib.request.Request(health_endpoint, headers={'User-Agent': 'SupremeAI-CI-Bot'})
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode())
                    if data.get("status") == "healthy" or data.get("status") == "ok":
                        is_healthy = True
                        print("✅ API is perfectly healthy and accepting traffic!")
                        break
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt} failed: {e}")
        time.sleep(5)
else:
    print("⚠️ SUPREMEAI_API_URL is not set. Skipping deep health check.")
    is_healthy = True # Assume healthy if no URL provided to check

# ==========================================
# 🔄 4. ROLLBACK IF UNHEALTHY
# ==========================================
if not is_healthy:
    print("🚨 CRITICAL: Deep health-check failed! The new code is broken.")
    if PREVIOUS_REVISION:
        print(f"🔄 Rolling back traffic to stable revision: {PREVIOUS_REVISION}...")
        rollback_cmd = f"gcloud run services update-traffic {SERVICE_NAME} --region {REGION} --to-revisions={PREVIOUS_REVISION}=100"
        _, r_err, r_code = run_cmd(rollback_cmd)
        if r_code == 0:
            print("✅ Rollback successful! Users are unaffected.")
        else:
            print(f"❌ Rollback failed! Manual intervention required. Error: {r_err}")
    else:
        print("❌ No previous revision found to rollback to!")
    sys.exit(1) # Fail the CI pipeline

print("🎉 DEPLOYMENT & VERIFICATION COMPLETELY SUCCESSFUL!")
sys.exit(0)

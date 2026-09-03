import os
import json
import requests
from dotenv import load_dotenv

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

targets = [
    {
        "role": "Core (Primary)",
        "name": "supremeai-primary-node",
        "svc_id": os.getenv("RENDER_PRIMARY_SVC_ID", "srv-dabm7dfqj5pc738jkbmg"),
        "key": os.getenv("RENDER_API_KEY_1") or os.getenv("RENDER_API_KEY"),
        "url": os.getenv("RENDER_PRIMARY_URL", "https://supremeai-primary-node.onrender.com")
    },
    {
        "role": "Worker",
        "name": "supremeai-worker-node",
        "svc_id": os.getenv("RENDER_WORKER_SVC_ID", "srv-dabm7evqj5pc738jkf30"),
        "key": os.getenv("RENDER_API_KEY_2"),
        "url": os.getenv("RENDER_WORKER_URL", "https://supremeai-worker-node.onrender.com")
    },
    {
        "role": "Scraper",
        "name": "supremeai-scraper-node",
        "svc_id": os.getenv("RENDER_SCRAPER_SVC_ID", "srv-dabm7gfqj5pc738jkicg"),
        "key": os.getenv("RENDER_API_KEY_3"),
        "url": os.getenv("RENDER_SCRAPER_URL", "https://supremeai-scraper-node.onrender.com")
    },
    {
        "role": "MCP",
        "name": "supremeai-mcp-tower",
        "svc_id": os.getenv("RENDER_MCP_SVC_ID", "srv-dabm7inqj5pc738jkrt0"),
        "key": os.getenv("RENDER_API_KEY_4"),
        "url": os.getenv("RENDER_MCP_URL", "https://supremeai-mcp-tower.onrender.com")
    }
]

print("================================================================================")
print("             RENDER 4-MICROSERVICE CLUSTER DEPLOYMENT & LOG AUDIT               ")
print("================================================================================")

for t in targets:
    role = t["role"]
    svc_id = t["svc_id"]
    key = t["key"]
    name = t["name"]
    public_url = t["url"]
    
    print(f"\n🔹 Checking Service: {name} [{role}]")
    print(f"   ID: {svc_id} | Public URL: {public_url}")
    
    if not key:
        print("   ❌ Error: Missing API Key for this service!")
        continue
        
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    
    # 1. Fetch Service Details
    svc_res = requests.get(f"https://api.render.com/v1/services/{svc_id}", headers=headers)
    if svc_res.status_code != 200:
        print(f"   ❌ Failed to get service info: HTTP {svc_res.status_code} {svc_res.text}")
        continue
        
    svc_data = svc_res.json()
    suspended = svc_data.get("suspended")
    service_details = svc_data.get("serviceDetails", {})
    live_url = service_details.get("url", public_url)
    print(f"   Status: {'SUSPENDED' if suspended == 'suspended' else 'ACTIVE'}")
    print(f"   Live URL: {live_url}")
    
    # 2. Fetch Latest Deployments
    deploys_res = requests.get(f"https://api.render.com/v1/services/{svc_id}/deploys?limit=3", headers=headers)
    if deploys_res.status_code != 200:
        print(f"   ❌ Failed to get deployments: HTTP {deploys_res.status_code}")
        continue
        
    deploys = deploys_res.json()
    if not deploys:
        print("   ⚠️ No deployments found!")
        continue
        
    latest_deploy_item = deploys[0]
    dep = latest_deploy_item.get("deploy", {})
    dep_id = dep.get("id")
    status = dep.get("status")
    trigger = dep.get("trigger")
    created_at = dep.get("createdAt")
    finished_at = dep.get("finishedAt")
    commit = dep.get("commit", {})
    commit_id = commit.get("id", "")[:8]
    commit_msg = commit.get("message", "").strip().split("\n")[0]
    
    print(f"   Latest Deploy ID : {dep_id}")
    print(f"   Deploy Status    : {status.upper()}")
    print(f"   Trigger          : {trigger}")
    print(f"   Created At       : {created_at}")
    print(f"   Finished At      : {finished_at}")
    print(f"   Commit           : {commit_id} - {commit_msg}")
    
    # Check health endpoint if alive
    if status == "live":
        print("   ✅ Deployment is LIVE!")
        # Try probing /health
        for health_path in ["/health", "/api/health", "/healthz", "/"]:
            test_url = f"{live_url.rstrip('/')}{health_path}"
            try:
                h_res = requests.get(test_url, timeout=10)
                print(f"   Probe {health_path} -> HTTP {h_res.status_code} ({h_res.text[:80]}...)")
                if h_res.status_code == 200:
                    break
            except Exception as e:
                print(f"   Probe {health_path} -> Connection timeout / error: {e}")
                break
    else:
        print(f"   ⚠️ Deployment is NOT live (Current Status: {status})")

print("\n================================================================================")

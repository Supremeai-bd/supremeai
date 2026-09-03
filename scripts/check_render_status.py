import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("RENDER_API_KEY") or os.getenv("RENDER_API_KEY_1")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

# The 4 service IDs in .env:
env_services = {
    "Core (Primary)": os.getenv("RENDER_PRIMARY_SVC_ID"),
    "Worker": os.getenv("RENDER_WORKER_SVC_ID"),
    "Scraper": os.getenv("RENDER_SCRAPER_SVC_ID"),
    "MCP": os.getenv("RENDER_MCP_SVC_ID"),
}

print("Checking configured Render services in .env:")
for name, svc_id in env_services.items():
    print(f"  {name}: {svc_id}")

print("\nFetching current Render services from API...")
res = requests.get("https://api.render.com/v1/services?limit=20", headers=headers)
if res.status_code != 200:
    print(f"Error fetching services: {res.status_code} {res.text}")
    exit(1)

all_services = res.json()
print(f"Total services found on Render account: {len(all_services)}")
for item in all_services:
    svc = item.get("service", {})
    s_id = svc.get("id")
    s_name = svc.get("name")
    s_type = svc.get("type")
    s_suspended = svc.get("suspended")
    s_url = svc.get("serviceDetails", {}).get("url", "N/A")
    print(f"  - [{s_id}] {s_name} ({s_type}) | Suspended: {s_suspended} | URL: {s_url}")

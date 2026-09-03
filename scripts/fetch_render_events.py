import os
import sys
import json
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

targets = [
    ("Core", os.getenv("RENDER_API_KEY_1"), os.getenv("RENDER_PRIMARY_SVC_ID")),
    ("Worker", os.getenv("RENDER_API_KEY_2"), os.getenv("RENDER_WORKER_SVC_ID")),
    ("Scraper", os.getenv("RENDER_API_KEY_3"), os.getenv("RENDER_SCRAPER_SVC_ID")),
    ("MCP", os.getenv("RENDER_API_KEY_4"), os.getenv("RENDER_MCP_SVC_ID")),
]

for role, key, svc_id in targets:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    print(f"\n=======================================================")
    print(f"Service: {role} ({svc_id})")
    print(f"=======================================================")
    
    # 1. Check Events
    ev_res = requests.get(f"https://api.render.com/v1/services/{svc_id}/events?limit=8", headers=headers)
    if ev_res.status_code == 200:
        print("--- Recent Events ---")
        for item in ev_res.json():
            ev = item.get("event", {})
            print(f"  [{ev.get('timestamp')}] {ev.get('type')}: {json.dumps(ev.get('details'))}")
    else:
        print(f"Failed to get events: {ev_res.status_code} {ev_res.text}")
        
    # 2. Check Deploy
    d_res = requests.get(f"https://api.render.com/v1/services/{svc_id}/deploys?limit=1", headers=headers)
    if d_res.status_code == 200 and d_res.json():
        dep = d_res.json()[0].get("deploy", {})
        dep_id = dep.get("id")
        status = dep.get("status")
        print(f"--- Latest Deploy ({dep_id}) Status: {status} ---")

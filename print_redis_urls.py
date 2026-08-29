import os
import requests

RENDER_API_KEY = "***REMOVED***"
HEADERS = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json"
}

resp = requests.get(f"https://api.render.com/v1/services?limit=100", headers=HEADERS)
if resp.status_code != 200:
    print("Failed to fetch services:", resp.status_code)
    exit(1)

services = resp.json()
for s in services:
    svc = s.get("service", {})
    svc_id = svc.get("id")
    svc_name = svc.get("name")
    
    env_resp = requests.get(f"https://api.render.com/v1/services/{svc_id}/env-vars", headers=HEADERS)
    if env_resp.status_code == 200:
        for item in env_resp.json():
            if item.get("envVar", {}).get("key") == "REDIS_URL":
                print(f"[{svc_name}] REDIS_URL: {item.get('envVar', {}).get('value')}")

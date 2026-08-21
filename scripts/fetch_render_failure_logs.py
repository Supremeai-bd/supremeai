# বাংলা মন্তব্য: Render ফেইল্ড ডিপ্লয়মেন্টের বিস্তারিত লগ ও স্ট্যাটাস সংগ্রহের স্ক্রিপ্ট
import urllib.request
import json
import re
import os

env_text = open('.env', encoding='utf-8').read()
k1 = re.search(r'RENDER_API_KEY="([^"]+)"', env_text).group(1)
k2 = re.search(r'RENDER_API_KEY_BACKUP="([^"]+)"', env_text).group(1)

services = [
    ("User Backend", "srv-d9d3n58js32c738n79k0", k1),
    ("Admin Backend", "srv-da35gg2bkg8c73fp1mu0", k2)
]

for name, sid, key in services:
    print(f"\n==================== {name} ({sid}) ====================")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    
    # Fetch deploys
    try:
        req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/deploys?limit=3", headers=headers)
        with urllib.request.urlopen(req) as resp:
            deploys = json.load(resp)
            print("--- Latest Deploys ---")
            for d in deploys:
                dep = d.get("deploy", {})
                print(f"Deploy ID: {dep.get('id')} | Status: {dep.get('status')} | CreatedAt: {dep.get('createdAt')} | FinishedAt: {dep.get('finishedAt')}")
                if dep.get('id'):
                    dep_req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/deploys/{dep.get('id')}", headers=headers)
                    try:
                        with urllib.request.urlopen(dep_req) as dep_resp:
                            dep_data = json.load(dep_resp)
                            print(f"Deploy Details: {json.dumps(dep_data, indent=2)}")
                    except Exception as e:
                        print(f"Could not get deploy details: {e}")
    except Exception as e:
        print(f"Error fetching deploys: {e}")
        
    # Fetch events
    try:
        req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/events?limit=5", headers=headers)
        with urllib.request.urlopen(req) as resp:
            events = json.load(resp)
            print("--- Latest Events ---")
            print(json.dumps(events, indent=2))
    except Exception as e:
        print(f"Error fetching events: {e}")

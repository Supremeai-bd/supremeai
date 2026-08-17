# বাংলা মন্তব্য: টাইমআউটসহ দ্রুত ডিপ্লয় স্ট্যাটাস দেখার স্ক্রিপ্ট
import urllib.request
import json
import re

env_text = open('.env', encoding='utf-8').read()
k1 = re.search(r'RENDER_API_KEY="([^"]+)"', env_text).group(1)
k2 = re.search(r'RENDER_API_KEY_BACKUP="([^"]+)"', env_text).group(1)

services = [
    ("User Backend", "srv-d9d3n58js32c738n79k0", k1),
    ("Admin Backend", "srv-d9fg48bh523c73f63bb0", k2)
]

for name, sid, key in services:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/deploys?limit=2", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        deploys = json.load(resp)
        print(f"=== {name} ===")
        for d in deploys:
            dep = d.get("deploy", {})
            print(f"  Deploy ID: {dep.get('id')} | Status: {dep.get('status')} | Created: {dep.get('createdAt')} | Finished: {dep.get('finishedAt')}")

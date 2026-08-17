# বাংলা মন্তব্য: ১০ মিনিটের বেশি সময় ধরে আটকে থাকা পুরোনো ডিপ্লয়মেন্ট ক্যানসেল করার স্ক্রিপ্ট
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
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/deploys?limit=5", headers=headers)
    with urllib.request.urlopen(req) as resp:
        deploys = json.load(resp)
        for d in deploys:
            dep = d.get("deploy", {})
            status = dep.get("status")
            created = dep.get("createdAt", "")
            dep_id = dep.get("id")
            print(f"[{name}] Found deploy {dep_id}: status={status}, created={created}")
            # Cancel if currently in progress
            if status in ["update_in_progress", "build_in_progress", "created"]:
                print(f"--> Cancelling hanging deploy {dep_id}...")
                try:
                    c_req = urllib.request.Request(
                        f"https://api.render.com/v1/services/{sid}/deploys/{dep_id}/cancel",
                        data=b"{}",
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(c_req) as c_resp:
                        print(f"--> Cancel response: {c_resp.status}")
                except Exception as e:
                    print(f"--> Cancel error: {e}")

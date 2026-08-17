# বাংলা মন্তব্য: Render সার্ভিসের এনভায়রনমেন্ট ভেরিয়েবল পরীক্ষা স্ক্রিপ্ট
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
    print(f"\n==================== {name} ({sid}) ====================")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/env-vars", headers=headers)
    with urllib.request.urlopen(req) as resp:
        vars = json.load(resp)
        keys = [v['envVar']['key'] for v in vars]
        print(f"Total env vars: {len(keys)}")
        print("Configured keys:", sorted(keys))
        for key_name in ["SUPABASE_DATABASE_URL", "SUPABASE_DATABASE_URL_POOLER", "DATABASE_URL", "ENV", "SERVICE_ROLE"]:
            val = next((v['envVar']['value'] for v in vars if v['envVar']['key'] == key_name), "NOT_SET")
            if val != "NOT_SET" and "postgres" in val:
                val = val[:25] + "..."
            print(f"  {key_name}: {val}")

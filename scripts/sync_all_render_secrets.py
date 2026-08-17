# বাংলা মন্তব্য: .env থেকে সকল প্রয়োজনীয় সিক্রেট ও এনভায়রনমেন্ট ভেরিয়েবল Render-এ স্বয়ংক্রিয়ভাবে সিঙ্ক করার স্ক্রিপ্ট
import urllib.request
import json
import re

env_text = open('.env', encoding='utf-8').read()
k1 = re.search(r'RENDER_API_KEY="([^"]+)"', env_text).group(1)
k2 = re.search(r'RENDER_API_KEY_BACKUP="([^"]+)"', env_text).group(1)

# Parse all KEY=VALUE from .env
env_vars = {}
for line in env_text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    m = re.match(r'^([A-Za-z0-9_]+)=(.*)$', line)
    if m:
        key = m.group(1)
        val = m.group(2).strip().strip('"').strip("'")
        if val and key not in ["RENDER_API_KEY", "RENDER_API_KEY_BACKUP"]:
            env_vars[key] = val

# Ensure essential mapped keys exist
if "SUPREMEAI_JWT_SECRET" in env_vars:
    env_vars["JWT_SECRET"] = env_vars["SUPREMEAI_JWT_SECRET"]
if "SUPREMEAI_CREDENTIAL_ENC_KEY" in env_vars:
    env_vars["ENCRYPTION_KEY"] = env_vars["SUPREMEAI_CREDENTIAL_ENC_KEY"]
if "SUPABASE_DATABASE_URL_POOLER" in env_vars:
    env_vars["DATABASE_URL"] = env_vars["SUPABASE_DATABASE_URL_POOLER"]

services = [
    ("User Backend", "srv-d9d3n58js32c738n79k0", k1, "user"),
    ("Admin Backend", "srv-d9fg48bh523c73f63bb0", k2, "admin")
]

for name, sid, key, role in services:
    print(f"\nSyncing all secrets to {name} ({sid})...")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # 1. Fetch current env vars
    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/env-vars", headers=headers)
    with urllib.request.urlopen(req) as resp:
        current_vars = json.load(resp)
    
    # Merge existing and new
    service_env = {v['envVar']['key']: v['envVar']['value'] for v in current_vars}
    service_env.update(env_vars)
    service_env["SERVICE_ROLE"] = role
    service_env["ENV"] = "production"
    
    put_payload = [{"key": k, "value": v} for k, v in service_env.items()]
    
    # 2. PUT updated env vars
    put_data = json.dumps(put_payload).encode('utf-8')
    put_req = urllib.request.Request(
        f"https://api.render.com/v1/services/{sid}/env-vars",
        data=put_data,
        headers=headers,
        method="PUT"
    )
    with urllib.request.urlopen(put_req) as put_resp:
        result = json.load(put_resp)
        print(f"[OK] Successfully synced {len(result)} secrets/env-vars to {name}!")

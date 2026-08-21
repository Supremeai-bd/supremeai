import os
import sys
import urllib.request
import urllib.error
import json
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

env_vars = {}
k1 = os.getenv("RENDER_API_KEY", "")
k2 = os.getenv("RENDER_API_KEY_BACKUP", "") or k1

if os.path.exists('.env'):
    env_text = open('.env', encoding='utf-8').read()
    m1 = re.search(r'RENDER_API_KEY=["\']?([^"\'\r\n]+)', env_text)
    if m1 and not k1:
        k1 = m1.group(1).strip()
    m2 = re.search(r'RENDER_API_KEY_BACKUP=["\']?([^"\'\r\n]+)', env_text)
    if m2 and not k2:
        k2 = m2.group(1).strip()
    if not k2:
        k2 = k1

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
    ("Primary Backend", "srv-da07ogmgekts739amqa0", k1, "user"),
    ("Admin Backend", "srv-da35gg2bkg8c73fp1mu0", k2, "admin")
]

for name, sid, key, role in services:
    if not key:
        print(f"Skipping {name} ({sid}) — no API key.")
        continue
    print(f"\nSyncing secrets to {name} ({sid})...")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. Fetch current env vars
        req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/env-vars", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
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
        with urllib.request.urlopen(put_req, timeout=30) as put_resp:
            print(f"✅ Successfully synced {len(service_env)} env vars to {name} (HTTP {put_resp.status})!")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"⚠️ Failed to sync secrets to {name} ({sid}): HTTP {e.code} {body[:200]}")
    except Exception as e:
        print(f"⚠️ Network error syncing to {name} ({sid}): {e}")

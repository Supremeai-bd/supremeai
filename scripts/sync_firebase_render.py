import os
import requests
import json

def parse_env_file(filepath):
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env_vars[key] = val
    return env_vars

env_vars = parse_env_file('.env')
RENDER_API_KEY = env_vars.get("RENDER_API_KEY")
FIREBASE_JSON = env_vars.get("FIREBASE_SERVICE_ACCOUNT_JSON")

if not RENDER_API_KEY or not FIREBASE_JSON:
    print("Missing RENDER_API_KEY or FIREBASE_SERVICE_ACCOUNT_JSON in .env")
    exit(1)

def update_render_service(service_id, api_key, label):
    url = f"https://api.render.com/v1/services/{service_id}/env-vars?limit=100"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "Content-Type": "application/json"}
    
    print(f"Fetching env vars for {label}...")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch {label} env vars: {resp.text}")
        return

    # Render API returns a list of objects like {"envVar": {"key": "...", "value": "..."}}
    existing_vars = []
    has_firebase = False
    
    for item in resp.json():
        if 'envVar' in item:
            key = item['envVar']['key']
            value = item['envVar']['value']
            if key == "FIREBASE_SERVICE_ACCOUNT_JSON":
                has_firebase = True
                value = FIREBASE_JSON # update to current
            existing_vars.append({"key": key, "value": value})
            
    if not has_firebase:
        existing_vars.append({"key": "FIREBASE_SERVICE_ACCOUNT_JSON", "value": FIREBASE_JSON})
        
    print(f"Updating {label}...")
    put_url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    resp2 = requests.put(put_url, headers=headers, json=existing_vars)
    if resp2.status_code == 200:
        print(f"{label} updated successfully with FIREBASE_SERVICE_ACCOUNT_JSON!")
    else:
        print(f"Failed to update {label}: {resp2.text}")

# Service IDs based on clean_legacy_secrets.py
update_render_service("srv-d9d3n58js32c738n79k0", RENDER_API_KEY, "Backend")
update_render_service("srv-da35gg2bkg8c73fp1mu0", env_vars.get("RENDER_API_KEY_BACKUP") or RENDER_API_KEY, "Admin")

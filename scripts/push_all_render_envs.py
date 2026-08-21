# scripts/push_all_render_envs.py
# বাংলা মন্তব্য: এই স্ক্রিপ্টটি লোকাল .env ফাইলের ভ্যালুগুলোর সাথে Render ড্যাশবোর্ডে পূর্বে থাকা Envs কে মার্জ করে
# রেন্ডারের উভয় সার্ভিসেই (User backend ও Admin backend) নিরাপদে সিঙ্ক করে, যাতে ড্যাশবোর্ডের কোনো Secret মুছে না যায়।

import os
import sys
import requests
import re
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv('.env')

key_primary = os.getenv('RENDER_API_KEY')
key_backup = os.getenv('RENDER_API_KEY_BACKUP')

if not key_primary:
    print("Error: RENDER_API_KEY not found in .env")
    sys.exit(1)

SERVICES = [
    {"name": "User Backend (Primary)", "service_id": "srv-d9d3n58js32c738n79k0"},
    {"name": "Admin Backend (Backup)", "service_id": "srv-da35gg2bkg8c73fp1mu0"},
    {"name": "Studio Client (Frontend)", "service_id": "srv-d9d3pgvavr4c738a46mg"}
]

valid_key_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.-]*$')

# 1. Load local .env vars
local_envs = {}
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, val = line.split('=', 1)
        name = name.strip()
        val = val.strip().strip('"').strip("'")
        if valid_key_pattern.match(name) and not name.startswith('GITHUB_'):
            local_envs[name] = val

print(f"🔑 Loaded {len(local_envs)} valid environment keys from local .env.")

for service in SERVICES:
    name = service["name"]
    svc_id = service["service_id"]
    
    # Select the right API key
    if "Backup" in name:
        current_key = key_backup
    else:
        current_key = key_primary
        
    if not current_key:
        print(f"  ⚠️ Warning: API Key for {name} is missing. Skipping.")
        continue

    headers = {
        'Authorization': f'Bearer {current_key}',
        'Content-Type': 'application/json'
    }
    
    print(f"\n🔄 Merging & syncing environment variables for {name} ({svc_id})...")

    # Fetch existing env vars from Render
    existing_envs = {}
    get_res = requests.get(f'https://api.render.com/v1/services/{svc_id}/env-vars?limit=100', headers=headers, timeout=15)
    if get_res.status_code == 200:
        for item in get_res.json():
            # Render API response can be wrapped in envVar object or flat dict
            env_item = item.get("envVar", item) if isinstance(item, dict) else item
            existing_envs[env_item.get("key")] = env_item.get("value")
        print(f"  Existing Render env vars fetched: {len(existing_envs)}")
    else:
        print(f"  ⚠️ Warning: Could not fetch existing env vars for {name} (HTTP {get_res.status_code}). Proceeding with local values.")

    # Merge strategy: Existing Dashboard keys preserved, Local .env overrides/adds
    merged_envs = existing_envs.copy()
    merged_envs.update(local_envs)
    if "Admin" in name:
        merged_envs["SERVICE_ROLE"] = "admin"
    else:
        merged_envs["SERVICE_ROLE"] = "user"

    payload = [{'key': k, 'value': v} for k, v in merged_envs.items() if k and v is not None]

    put_res = requests.put(f'https://api.render.com/v1/services/{svc_id}/env-vars', headers=headers, json=payload, timeout=15)
    if put_res.status_code == 200:
        print(f"  ✅ Successfully updated {len(payload)} merged env vars for {name}!")
    else:
        print(f"  ❌ Failed to update {name}: HTTP {put_res.status_code} - {put_res.text}")

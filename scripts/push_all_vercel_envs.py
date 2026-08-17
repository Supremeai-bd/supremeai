import os
import requests
import re
from dotenv import load_dotenv

load_dotenv('.env')

token = os.getenv('VERCEL_TOKEN')
if not token:
    print("Error: VERCEL_TOKEN missing in .env")
    exit(1)

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

valid_key_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.-]*$')

env_dict = {}
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, val = line.split('=', 1)
        name = name.strip()
        val = val.strip().strip('"').strip("'")
        if valid_key_pattern.match(name) and not name.startswith('GITHUB_'):
            env_dict[name] = val

print(f"Syncing {len(env_dict)} env keys to Vercel (supremeai)...")
count = 0
for k, v in env_dict.items():
    if not v:
        continue
    body = {
        'key': k,
        'value': v,
        'type': 'encrypted',
        'target': ['production', 'preview', 'development']
    }
    r = requests.post('https://api.vercel.com/v10/projects/supremeai/env', headers=headers, json=body)
    if r.status_code in [200, 201]:
        count += 1

print(f"Done! Successfully synced {count} keys to Vercel.")

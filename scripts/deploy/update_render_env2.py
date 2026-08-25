import json
import os
import urllib.request

service_id = "srv-da666f8u01pc739bm3t0"
token = os.environ.get("RENDER_API_KEY", "")

# Get current env vars
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{service_id}/env-vars",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    current_vars = json.loads(resp.read().decode())

env_vars = []
for v in current_vars:
    env_vars.append({"key": v["envVar"]["key"], "value": v["envVar"]["value"]})

# Add FORCE_FIRESTORE_ADC
env_vars.append({"key": "FORCE_FIRESTORE_ADC", "value": "1"})

# Update env vars
req_update = urllib.request.Request(
    f"https://api.render.com/v1/services/{service_id}/env-vars",
    data=json.dumps(env_vars).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
    method="PUT"
)
try:
    with urllib.request.urlopen(req_update) as resp:
        print("Updated Render env vars with FORCE_FIRESTORE_ADC successfully!")
except Exception as e:
    print(f"Error updating env vars: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())

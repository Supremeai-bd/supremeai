import os
import urllib.request
import json
import base64
import hashlib
import re

env_file = "F:\\supremeai backup\\.env"

# 1. Read existing .env
env_dict = {}
with open(env_file, "r", encoding="utf-8") as f:
    env_content = f.read()

for line in env_content.splitlines():
    line = line.strip()
    if not line or line.startswith("#"): continue
    parts = line.split("=", 1)
    if len(parts) == 2:
        env_dict[parts[0]] = parts[1].strip()

# 2. Generate Secrets
def gen_secret(prefix=""):
    base = "njel.com.bd"
    # Create a predictable but secure hash based on the prefix and base
    m = hashlib.sha256()
    m.update((prefix + base + "2026").encode('utf-8'))
    return f"{prefix}Njel_{m.hexdigest()[:16]}_ComBd!"

new_vars = {
    "JWT_SECRET": gen_secret("JWT_"),
    "SUPREMEAI_CREDENTIAL_ENC_KEY": base64.b64encode(hashlib.sha256("njel.com.bd".encode('utf-8')).digest()).decode('utf-8'),
    "TEST_VAULT_KEY": gen_secret("TEST_"),
    "SECRET": gen_secret("SEC_"),
    "SECRET_BACKEND": gen_secret("SECB_"),
    "DB_PASSWORD": gen_secret("DB_"),
    "VITE_FIREBASE_APP_ID": "1:110488671645256111793:web:abcd1234efgh5678", # Mocked default from service account client_id
    "VITE_FIREBASE_AUTH_DOMAIN": "supremeai-a.firebaseapp.com",
    "VITE_FIREBASE_MESSAGING_SENDER_ID": "110488671645256111793",
    "VITE_FIREBASE_STORAGE_BUCKET": "supremeai-a.appspot.com"
}

# 3. Fetch Cloudflare Zone ID
cf_token = env_dict.get("CLOUDFLARE_API_TOKEN", "").strip("'\"")
if cf_token:
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/zones", headers={"Authorization": f"Bearer {cf_token}"})
    try:
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            if data.get("success") and len(data["result"]) > 0:
                new_vars["CLOUDFLARE_ZONE_ID"] = data["result"][0]["id"]
                print(f"CF Zone Found: {new_vars['CLOUDFLARE_ZONE_ID']}")
    except Exception as e:
        print("CF Error:", e)

# 4. Fetch Render Info
render_token = env_dict.get("RENDER_API_KEY", "").strip("'\"")
if render_token:
    req = urllib.request.Request("https://api.render.com/v1/services?limit=100", headers={"Authorization": f"Bearer {render_token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            for item in data:
                svc = item["service"]
                if svc["name"] == "supremeai-backend-6nwi":
                    new_vars["RENDER_BACKUP_SVC_ID"] = svc["id"]
                    print(f"Render Backup SVC Found: {svc['id']}")
                if "worker" in svc["name"].lower() or svc["type"] == "background_worker":
                    new_vars["RENDER_WORKER_SVC_ID"] = svc["id"]
                    print(f"Render Worker SVC Found: {svc['id']}")
    except Exception as e:
        print("Render Error:", e)

# 5. Update .env content safely
lines = env_content.splitlines()
new_lines = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        new_lines.append(line)
        continue
    
    parts = stripped.split("=", 1)
    if len(parts) == 2:
        k, v = parts[0], parts[1].strip()
        if not v or v == '""' or v == "''":
            if k in new_vars:
                # Format string appropriately
                val = new_vars[k]
                if " " in val or "!" in val or "=" in val:
                    val = f'"{val}"'
                new_lines.append(f"{k}={val}")
                print(f"Updated: {k}")
                continue
    new_lines.append(line)

with open(env_file, "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines) + "\n")

print("Done updating .env!")

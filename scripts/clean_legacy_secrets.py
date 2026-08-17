import os
import requests
import json
import time

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

GH_TOKEN = env_vars.get("GITHUB_API_TOKEN") or env_vars.get("GITHUB_TOKEN") or env_vars.get("GITHUB_PAT_NILOYJOY7")
VERCEL_TOKEN = env_vars.get("VERCEL_TOKEN")
VERCEL_PROJECT_ID = env_vars.get("VERCEL_PROJECT_ID")
RENDER_API_KEY = env_vars.get("RENDER_API_KEY")
RENDER_API_KEY_BACKUP = env_vars.get("RENDER_API_KEY_BACKUP")

INFISICAL_KEYS = ["INFISICAL_TOKEN", "INFISICAL_PROJECT_ID", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET"]
RENDER_PRESERVE = {"PORT", "SERVICE_ROLE", "SERVICE_TYPE", "NODE_ENV", "ENV", "RENDER_API_KEY", "RENDER_API_KEY_BACKUP"}

# ================= RENDER =================
def clean_render(service_id, api_key, label):
    if not api_key:
        print(f"⚠️ Skipping Render {label} - API Key missing")
        return
        
    url = f"https://api.render.com/v1/services/{service_id}/env-vars?limit=100"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch {label} env vars")
        return
        
    existing_keys = {item['envVar']['key']: item['envVar']['value'] for item in resp.json() if 'envVar' in item}
    
    # Payload will only contain PRESERVE_KEYS and INFISICAL_KEYS. 
    # Render's PUT endpoint replaces EVERYTHING, effectively deleting legacy secrets.
    payload = []
    
    for k in RENDER_PRESERVE:
        if k in existing_keys:
            payload.append({"key": k, "value": existing_keys[k]})
            
    for k in INFISICAL_KEYS:
        if k in env_vars and env_vars[k]:
            payload.append({"key": k, "value": env_vars[k]})
            
    put_url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    put_headers = headers.copy()
    put_headers["Content-Type"] = "application/json"
    
    resp2 = requests.put(put_url, headers=put_headers, json=payload)
    if resp2.status_code == 200:
        print(f"✅ Render {label} cleaned! Removed legacy secrets, kept {len(payload)} native/Infisical keys.")
    else:
        print(f"❌ Failed to update Render {label}: {resp2.text}")

# ================= GITHUB =================
def clean_github(repo, token):
    if not token:
        print(f"⚠️ Skipping GitHub {repo} - Token missing")
        return
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    # 1. Push Infisical keys (handled by user's sync script, but we ensure they exist)
    # We will just delete legacy keys here
    
    url = f"https://api.github.com/repos/{repo}/actions/secrets"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch GitHub secrets for {repo}: {resp.text}")
        return
        
    secrets = resp.json().get("secrets", [])
    deleted = 0
    
    # Keep PATs, Infisical keys, and Deploy hooks
    keep_prefixes = ("GITHUB_PAT_", "INFISICAL_", "RENDER_DEPLOY_", "VERCEL_")
    
    for sec in secrets:
        name = sec["name"]
        if not name.startswith(keep_prefixes) and name not in ["DISCORD_WEBHOOK_URL", "DISCORD_OTP_WEBHOOK_URL"]:
            del_url = f"https://api.github.com/repos/{repo}/actions/secrets/{name}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code == 204:
                deleted += 1
            time.sleep(0.1) # Rate limit protection
            
    print(f"✅ GitHub {repo} cleaned! Deleted {deleted} legacy secrets.")

# ================= VERCEL =================
def clean_vercel(project_id, token):
    if not token or not project_id:
        print("⚠️ Skipping Vercel - Token or Project ID missing")
        return
        
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.vercel.com/v9/projects/{project_id}/env"
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("❌ Failed to fetch Vercel envs")
        return
        
    envs = resp.json().get("envs", [])
    deleted = 0
    
    for e in envs:
        key = e["key"]
        # Keep native configs and Infisical
        if not key.startswith("INFISICAL_") and key not in ["VERCEL_TOKEN", "NODE_ENV", "PORT", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"]:
            del_url = f"https://api.vercel.com/v9/projects/{project_id}/env/{e['id']}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code == 200:
                deleted += 1
            time.sleep(0.1)
            
    print(f"✅ Vercel cleaned! Deleted {deleted} legacy secrets.")


print("🚀 Starting Master Legacy Cleanup & Integration...")

clean_render("srv-d9d3n58js32c738n79k0", RENDER_API_KEY, "Backend")
clean_render("srv-d9fg48bh523c73f63bb0", RENDER_API_KEY_BACKUP or RENDER_API_KEY, "Admin")

clean_github("SaifulHaqueNiloy/supremeai", GH_TOKEN)

clean_vercel(VERCEL_PROJECT_ID, VERCEL_TOKEN)

print("🎉 Process Complete!")

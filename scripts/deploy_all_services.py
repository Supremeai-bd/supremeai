import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

# ── Render API Keys (loaded from env — never hardcode) ──
RENDER_KEYS = {
    "primary": os.environ.get("RENDER_API_KEY_1", os.environ.get("RENDER_API_KEY", "")),
    "worker":  os.environ.get("RENDER_API_KEY_2", os.environ.get("RENDER_API_KEY_BACKUP", "")),
    "scraper": os.environ.get("RENDER_API_KEY_3", os.environ.get("RENDER_BACKUP_API_KEY_2", "")),
    "mcp":     os.environ.get("RENDER_API_KEY_4", os.environ.get("RENDER_API_KEY", "")), # fallback to main key
}

# --- Service Configurations ---
REPO_URL = "https://github.com/SaifulHaqueNiloy/supremeai"
BRANCH = "main"

def get_owner_id(api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    response = requests.get("https://api.render.com/v1/owners", headers=headers)
    if response.status_code == 200:
        owners = response.json()
        if owners:
            return owners[0]['owner']['id']
    print(f"Failed to fetch owner for key {api_key[:10]}... : {response.text}")
    return None

def create_or_update_service(role, api_key):
    print(f"\n[Processing {role.upper()} service...]")
    owner_id = get_owner_id(api_key)
    if not owner_id:
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    env_vars = [
        {"key": "SUPREMEAI_JWT_SECRET", "value": os.environ.get("SUPREMEAI_JWT_SECRET", "")},
        {"key": "SECRET_KEY", "value": os.environ.get("SECRET_KEY", "")},
        {"key": "JWT_SECRET_KEY", "value": os.environ.get("JWT_SECRET_KEY", "")},
        {"key": "ENCRYPTION_KEY", "value": os.environ.get("ENCRYPTION_KEY", "")},
        {"key": "SUPABASE_URL", "value": os.environ.get("SUPABASE_URL", "")},
        {"key": "SUPABASE_KEY", "value": os.environ.get("SUPABASE_KEY", "")},
        {"key": "SUPABASE_DATABASE_URL", "value": os.environ.get("SUPABASE_DATABASE_URL", "")},
        {"key": "INSTANCE_ROLE", "value": role},
        {"key": "ENV", "value": "production"},
        {"key": "PORT", "value": "8080"}
    ]

    if role == "mcp":
        service_name = "supremeai-mcp-tower"
        root_dir = "infrastructure/mcp-control-plane"
    else:
        service_name = f"supremeai-{role}-node"
        root_dir = "backend"

    # Find existing service
    response = requests.get("https://api.render.com/v1/services", headers=headers, params={"limit": 100})
    service_id = None
    service_url = None
    
    if response.status_code == 200:
        services = response.json()
        for s in services:
            if s['service']['name'] == service_name:
                region = s['service']['serviceDetails'].get('region', '')
                if region == "oregon":
                    print(f"Found existing {service_name} in oregon. Deleting it...")
                    del_resp = requests.delete(f"https://api.render.com/v1/services/{s['service']['id']}", headers=headers)
                    if del_resp.status_code == 204:
                        print("Deleted successfully. Will recreate in singapore.")
                    else:
                        print(f"Failed to delete: {del_resp.text}")
                else:
                    service_id = s['service']['id']
                    service_url = s['service']['serviceDetails'].get('url')
                    print(f"Service {service_name} already exists in {region}. ID: {service_id}")
                break

    if not service_id:
        print(f"Creating new service {service_name} in singapore...")
        
        env_specific_details = {
            "dockerfilePath": "Dockerfile"
        }
        
        # Add celery command for worker
        if role == "worker":
            env_specific_details["dockerCommand"] = "celery -A workers.celery_app worker --loglevel=INFO -c 2"
            
        payload = {
            "type": "web_service",
            "name": service_name,
            "ownerId": owner_id,
            "repo": REPO_URL,
            "branch": BRANCH,
            "autoDeploy": "yes",
            "rootDir": root_dir,
            "serviceDetails": {
                "env": "docker",
                "envSpecificDetails": env_specific_details,
                "plan": "free",
                "region": "singapore",
                "envVars": env_vars
            }
        }
        resp = requests.post("https://api.render.com/v1/services", headers=headers, json=payload)
        if resp.status_code in [200, 201]:
            data = resp.json()
            service_id = data.get('service', {}).get('id')
            if not service_id:
                print("[FAIL] Missing 'id' in response")
                return None
            service_url = data.get('service', {}).get('serviceDetails', {}).get('url')
            print(f"[OK] Created successfully: {service_id}")
        else:
            print(f"[FAIL] Failed to create: {resp.text}")
            return None
    else:
        print(f"Updating env vars for {service_id}...")
        resp = requests.put(f"https://api.render.com/v1/services/{service_id}/env-vars", headers=headers, json=env_vars)
        if resp.status_code == 200:
            print("[OK] Env vars updated.")
        else:
            print(f"[FAIL] Failed to update env vars: {resp.text}")

        # Update docker command for worker if updating existing service
        if role == "worker":
            print(f"Updating dockerCommand for {service_id}...")
            patch_payload = {
                "serviceDetails": {
                    "envSpecificDetails": {
                        "dockerCommand": "celery -A workers.celery_app worker --loglevel=INFO -c 2"
                    }
                }
            }
            resp = requests.patch(f"https://api.render.com/v1/services/{service_id}", headers=headers, json=patch_payload)
            if resp.status_code == 200:
                print("[OK] Docker command updated.")
            else:
                print(f"[FAIL] Failed to update docker command: {resp.text}")

        print(f"Triggering deploy for {service_id}...")
        resp = requests.post(f"https://api.render.com/v1/services/{service_id}/deploys", headers=headers)
        if resp.status_code in [200, 201]:
            print("[OK] Deploy triggered.")
        else:
            print(f"[FAIL] Failed to trigger deploy: {resp.text}")

    return {"id": service_id, "url": service_url}

if __name__ == "__main__":
    results = {}
    for role, key in RENDER_KEYS.items():
        if key:
            res = create_or_update_service(role, key)
            if res:
                results[role] = res
        else:
            print(f"Skipping {role} because API key is missing.")

    print("\n\n=== DEPLOYMENT RESULTS ===")
    for role, res in results.items():
        print(f"{role.upper()}:")
        print(f"  URL: {res.get('url')}")
        print(f"  ID:  {res.get('id')}")

    with open("deploy_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to deploy_results.json")

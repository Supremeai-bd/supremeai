import os
import requests
import json
import argparse
import time

def parse_env_file(filepath):
    env_vars = {}
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

def upload_to_infisical(env_vars, token, workspace_id, env_slug="prod"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    success = 0
    failed = 0
    
    for key, val in env_vars.items():
        url = f"https://app.infisical.com/api/v3/secrets/raw/{key}"
        payload = {
            "environment": env_slug,
            "secretValue": val,
            "workspaceId": workspace_id,
            "secretPath": "/",
            "type": "shared"
        }
        
        try:
            # We use POST to create. If it exists, POST might fail (400 or 409). 
            # In V3, to update, we use PATCH. Let's try POST, fallback to PATCH.
            r = requests.post(url, headers=headers, json=payload)
            if r.status_code in [200, 201]:
                success += 1
                print(f"Created: {key}")
            elif r.status_code in [400, 409]:
                # Secret might already exist, try PATCH
                r2 = requests.patch(url, headers=headers, json=payload)
                if r2.status_code in [200, 201]:
                    success += 1
                    print(f"Updated: {key}")
                else:
                    failed += 1
                    print(f"Failed PATCH {key}: {r2.status_code} {r2.text}")
            else:
                failed += 1
                print(f"Failed POST {key}: {r.status_code} {r.text}")
        except Exception as e:
            failed += 1
            print(f"Error {key}: {e}")
            
        time.sleep(0.05) # Rate limit protection

    print(f"\nUpload Complete! Success: {success}, Failed: {failed}")

if __name__ == "__main__":
    env_file = "infisical_upload.env"
    env_vars = parse_env_file(env_file)
    
    token = env_vars.get("INFISICAL_TOKEN")
    project_id = env_vars.get("INFISICAL_PROJECT_ID")
    client_id = env_vars.get("INFISICAL_CLIENT_ID")
    client_secret = env_vars.get("INFISICAL_CLIENT_SECRET")
    
    if client_id and client_secret:
        print("Using Machine Identity to authenticate...")
        auth_url = "https://app.infisical.com/api/v1/auth/universal-auth/login"
        resp = requests.post(auth_url, json={"clientId": client_id, "clientSecret": client_secret})
        if resp.status_code == 200:
            token = resp.json().get("accessToken")
            print("Successfully obtained access token!")
        else:
            print(f"Failed to authenticate with Machine Identity: {resp.status_code} {resp.text}")
            exit(1)

    if not token or not project_id:
        print("Missing valid token or INFISICAL_PROJECT_ID")
        exit(1)
        
    # Filter out Infisical config keys
    upload_vars = {k: v for k, v in env_vars.items() if not k.startswith("INFISICAL_")}
    
    print(f"Starting upload of {len(upload_vars)} variables to Infisical...")
    for env in ["prod", "staging", "dev"]:
        print(f"\n--- Uploading to {env} ---")
        upload_to_infisical(upload_vars, token, project_id, env_slug=env)

import os
import requests
from base64 import b64encode
from nacl import encoding, public
import argparse

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

def encrypt(public_key: str, secret_value: str) -> str:
    public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

def update_github_secret(repo, token, secret_name, secret_value):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    # Get public key
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
    if r.status_code != 200:
        print(f"Failed to fetch GH public key for {repo}: {r.status_code} {r.text}")
        return False
        
    data = r.json()
    key_id = data["key_id"]
    public_key = data["key"]
    
    encrypted_value = encrypt(public_key, secret_value)
    
    # Put secret
    put_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    r2 = requests.put(put_url, headers=headers, json=payload)
    if r2.status_code in [201, 204]:
        print(f"✅ Successfully updated GitHub Secret {secret_name} in {repo}")
        return True
    else:
        print(f"❌ Failed to update GH Secret {secret_name}: {r2.status_code} {r2.text}")
        return False

def update_vercel_env(project_id, token, key, value, targets=["production", "preview", "development"]):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    # check if it exists
    r = requests.get(f"https://api.vercel.com/v9/projects/{project_id}/env", headers=headers)
    if r.status_code == 200:
        envs = r.json().get("envs", [])
        existing = next((e for e in envs if e["key"] == key), None)
        
        if existing:
            # Edit existing
            env_id = existing["id"]
            patch_url = f"https://api.vercel.com/v9/projects/{project_id}/env/{env_id}"
            payload = {"value": value, "target": targets, "type": "encrypted"}
            r_patch = requests.patch(patch_url, headers=headers, json=payload)
            if r_patch.status_code == 200:
                print(f"✅ Successfully updated Vercel Env {key}")
            else:
                print(f"❌ Failed to update Vercel Env {key}: {r_patch.text}")
        else:
            # Create new
            post_url = f"https://api.vercel.com/v10/projects/{project_id}/env"
            payload = {"key": key, "value": value, "target": targets, "type": "encrypted"}
            r_post = requests.post(post_url, headers=headers, json=payload)
            if r_post.status_code in [200, 201]:
                print(f"✅ Successfully created Vercel Env {key}")
            else:
                print(f"❌ Failed to create Vercel Env {key}: {r_post.text}")
    else:
        print(f"❌ Failed to fetch Vercel envs: {r.status_code} {r.text}")


if __name__ == "__main__":
    env_vars = parse_env_file(".env")
    
    gh_token = env_vars.get("GITHUB_API_TOKEN") or env_vars.get("GITHUB_TOKEN") or env_vars.get("GITHUB_PAT_NILOYJOY7")
    vercel_token = env_vars.get("VERCEL_TOKEN")
    vercel_project_id = env_vars.get("VERCEL_PROJECT_ID")
    
    repo = "SaifulHaqueNiloy/supremeai"
    
    keys_to_sync = ["INFISICAL_TOKEN", "INFISICAL_PROJECT_ID", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET"]
    
    print("🚀 Starting sync to GitHub and Vercel...")
    for key in keys_to_sync:
        val = env_vars.get(key)
        if not val:
            print(f"⚠️ Warning: {key} not found in .env, skipping.")
            continue
            
        # GitHub
        if gh_token:
            update_github_secret(repo, gh_token, key, val)
        else:
            print("⚠️ GITHUB_TOKEN not found, skipping GitHub sync.")
            
        # Vercel
        if vercel_token and vercel_project_id:
            update_vercel_env(vercel_project_id, vercel_token, key, val)
        else:
            print("⚠️ VERCEL_TOKEN or VERCEL_PROJECT_ID not found, skipping Vercel sync.")

    print("🎉 Sync process completed!")

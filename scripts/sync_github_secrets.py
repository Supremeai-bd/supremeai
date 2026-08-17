import os
import requests
from base64 import b64encode
from nacl import encoding, public
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

def encrypt(public_key: str, secret_value: str) -> str:
    public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

def sync_github_secrets(repo, token, env_vars):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    print(f"Fetching public key for {repo}...")
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
    if r.status_code != 200:
        print(f"Failed to fetch GH public key: {r.status_code} {r.text}")
        return
        
    data = r.json()
    key_id = data["key_id"]
    public_key = data["key"]
    
    success = 0
    failed = 0
    
    print(f"Starting sync of {len(env_vars)} secrets to GitHub Actions...")
    for key, val in env_vars.items():
        if not val:
            continue
            
        encrypted_value = encrypt(public_key, val)
        put_url = f"https://api.github.com/repos/{repo}/actions/secrets/{key}"
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id
        }
        
        r2 = requests.put(put_url, headers=headers, json=payload)
        if r2.status_code in [201, 204]:
            print(f"Synced: {key}")
            success += 1
        else:
            print(f"Failed: {key} ({r2.status_code})")
            failed += 1
            
        time.sleep(0.1) # Small delay to avoid API rate limits

    print(f"\nSync Complete! Success: {success}, Failed: {failed}")

if __name__ == "__main__":
    env_vars = parse_env_file(".env")
    gh_token = env_vars.get("GITHUB_API_TOKEN") or env_vars.get("GITHUB_TOKEN") or env_vars.get("GITHUB_PAT_NILOYJOY7")
    repo = "SaifulHaqueNiloy/supremeai"
    
    if not gh_token:
        print("Error: GitHub Token not found in .env!")
        exit(1)
        
    sync_github_secrets(repo, gh_token, env_vars)

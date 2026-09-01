"""
Phase 3 & 4: Save all 3 backend URLs and IDs to Infisical & GitHub Actions
"""
import os
import sys
import json
import httpx
import base64
import hashlib
import nacl.public
import nacl.encoding

# ── Credentials (loaded from environment — never hardcode in source) ─────────
INFISICAL_CLIENT_ID     = os.environ.get("INFISICAL_CLIENT_ID", "")
INFISICAL_CLIENT_SECRET = os.environ.get("INFISICAL_CLIENT_SECRET", "")
INFISICAL_PROJECT_ID    = os.environ.get("INFISICAL_PROJECT_ID", "")
GITHUB_TOKEN            = os.environ.get("GITHUB_TOKEN", os.environ.get("GITHUB_PAT_AUTO_FIX", ""))
GITHUB_REPO             = "SaifulHaqueNiloy/supremeai"
CLOUDFLARE_API_TOKEN    = os.environ.get("CLOUDFLARE_API_TOKEN", os.environ.get("CLOUDFLARE_WORKERS_API_TOKEN", ""))
CLOUDFLARE_ACCOUNT_ID   = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
WORKER_NAME             = "supremeai-worker"

# ── Backend results — loaded from env (never hardcode URLs/keys in source) ──
BACKENDS = {
    "RENDER_PRIMARY_URL":    os.environ.get("RENDER_PRIMARY_URL",    ""),
    "RENDER_PRIMARY_SVC_ID": os.environ.get("RENDER_PRIMARY_SVC_ID", ""),
    "RENDER_API_KEY_1":      os.environ.get("RENDER_API_KEY_1",      os.environ.get("RENDER_API_KEY", "")),
    "RENDER_WORKER_URL":     os.environ.get("RENDER_WORKER_URL",     ""),
    "RENDER_WORKER_SVC_ID":  os.environ.get("RENDER_WORKER_SVC_ID",  ""),
    "RENDER_API_KEY_2":      os.environ.get("RENDER_API_KEY_2",      os.environ.get("RENDER_API_KEY_BACKUP", "")),
    "RENDER_SCRAPER_URL":    os.environ.get("RENDER_SCRAPER_URL",    ""),
    "RENDER_SCRAPER_SVC_ID": os.environ.get("RENDER_SCRAPER_SVC_ID", ""),
    "RENDER_API_KEY_3":      os.environ.get("RENDER_API_KEY_3",      os.environ.get("RENDER_BACKUP_API_KEY_2", "")),
}

# ───────────────────────────────────────────────────
# PHASE 3: Infisical
# ───────────────────────────────────────────────────
def get_infisical_token():
    url = "https://app.infisical.com/api/v1/auth/universal-auth/login"
    r = httpx.post(url, json={"clientId": INFISICAL_CLIENT_ID, "clientSecret": INFISICAL_CLIENT_SECRET})
    if r.status_code == 200:
        return r.json()["accessToken"]
    print(f"[FAIL] Infisical auth failed: {r.text}")
    return None

def save_to_infisical(token, key, value):
    url = f"https://app.infisical.com/api/v3/secrets/raw/{key}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "workspaceId": INFISICAL_PROJECT_ID,
        "environment": "prod",
        "secretPath": "/",
        "secretValue": value,
        "type": "shared"
    }
    # Try PATCH first (update), then POST (create)
    r = httpx.patch(url, headers=headers, json=payload)
    if r.status_code in [200, 201]:
        print(f"  [OK] Updated  Infisical: {key}")
        return True
    r = httpx.post(url, headers=headers, json=payload)
    if r.status_code in [200, 201]:
        print(f"  [OK] Created  Infisical: {key}")
        return True
    print(f"  [FAIL] Infisical {key}: {r.status_code} {r.text[:120]}")
    return False

# ───────────────────────────────────────────────────
# PHASE 4: GitHub Actions Secrets
# ───────────────────────────────────────────────────
def get_github_public_key():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = httpx.get(url, headers=headers)
    if r.status_code == 200:
        d = r.json()
        return d["key_id"], d["key"]
    print(f"[FAIL] GitHub public key: {r.text}")
    return None, None

def encrypt_github_secret(public_key_b64: str, secret_value: str) -> str:
    public_key_bytes = base64.b64decode(public_key_b64)
    pub_key = nacl.public.PublicKey(public_key_bytes)
    sealed_box = nacl.public.SealedBox(pub_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def save_to_github(key_id, public_key_b64, secret_name, secret_value):
    encrypted = encrypt_github_secret(public_key_b64, secret_value)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    payload = {"encrypted_value": encrypted, "key_id": key_id}
    r = httpx.put(url, headers=headers, json=payload)
    if r.status_code in [201, 204]:
        print(f"  [OK] GitHub Secret: {secret_name}")
        return True
    print(f"  [FAIL] GitHub {secret_name}: {r.status_code} {r.text[:120]}")
    return False

# ───────────────────────────────────────────────────
# PHASE 5+6: Cloudflare Worker vars
# ───────────────────────────────────────────────────
def update_cloudflare_worker_vars():
    print("\n[Phase 5] Updating Cloudflare Worker env vars...")
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}/env"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    bindings = [
        {"name": "PRIMARY_URL",  "text": BACKENDS["RENDER_PRIMARY_URL"],  "type": "plain_text"},
        {"name": "WORKER_URL",   "text": BACKENDS["RENDER_WORKER_URL"],   "type": "plain_text"},
        {"name": "SCRAPER_URL",  "text": BACKENDS["RENDER_SCRAPER_URL"],  "type": "plain_text"},
    ]
    r = httpx.put(url, headers=headers, json={"bindings": bindings})
    if r.status_code in [200, 201]:
        print("[OK] Cloudflare worker vars updated via API.")
    else:
        print(f"[WARN] Cloudflare env API: {r.status_code} {r.text[:200]}")

# ───────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────
def main():
    # Phase 3
    print("\n=== Phase 3: Infisical Vault ===")
    token = get_infisical_token()
    if token:
        for k, v in BACKENDS.items():
            save_to_infisical(token, k, v)
    else:
        print("[SKIP] Infisical skipped (no token)")

    # Phase 4
    print("\n=== Phase 4: GitHub Actions Secrets ===")
    try:
        import nacl.public
        key_id, pub_key = get_github_public_key()
        if key_id:
            for k, v in BACKENDS.items():
                save_to_github(key_id, pub_key, k, v)
    except ImportError:
        print("[WARN] PyNaCl not installed. Installing...")
        os.system(f"{sys.executable} -m pip install PyNaCl httpx -q")
        print("[INFO] Re-run the script after install.")

    # Phase 5: Cloudflare
    update_cloudflare_worker_vars()

    print("\n=== All phases complete ===")

if __name__ == "__main__":
    main()

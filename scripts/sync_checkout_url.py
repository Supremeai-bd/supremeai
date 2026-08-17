import json
import urllib.request
from pathlib import Path

# Load env variables directly since python-dotenv might not be installed in all contexts
env_path = Path(__file__).parent.parent / '.env'
env_vars = {}
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                env_vars[k] = v.strip('"\'')

github_token = env_vars.get('GITHUB_TOKEN')
render_key_main = env_vars.get('RENDER_API_KEY')
render_key_backup = env_vars.get('RENDER_API_KEY_BACKUP')

checkout_base_url = "https://supremeai.onrender.com"  # Using this as the base checkout URL for prod

def update_render_env(api_key, service_id, env_key, env_value):
    url = f"https://api.render.com/v1/services/{service_id}/env-vars?limit=50"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            existing = json.loads(response.read().decode())

        new_vars = [{"key": item['envVar']['key'], "value": item['envVar']['value']} for item in existing]

        # Add or update key
        updated = False
        for var in new_vars:
            if var['key'] == env_key:
                var['value'] = env_value
                updated = True
                break
        if not updated:
            new_vars.append({"key": env_key, "value": env_value})

        put_req = urllib.request.Request(
            f"https://api.render.com/v1/services/{service_id}/env-vars",
            data=json.dumps(new_vars).encode('utf-8'),
            headers={**headers, "Content-Type": "application/json"},
            method='PUT'
        )
        with urllib.request.urlopen(put_req) as res:
            print(f"OK Render ({service_id}) updated with {env_key}={env_value}")
    except Exception as e:
        print(f"FAILED to update Render ({service_id}): {e}")

def update_github_secret(token, repo, secret_name, secret_value):
    import base64
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        # Get public key
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
        with urllib.request.urlopen(req) as response:
            key_data = json.loads(response.read().decode())

        public_key = public.PublicKey(key_data['key'].encode("utf-8"), encoding.Base64Encoder)
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        data = json.dumps({"encrypted_value": encrypted_b64, "key_id": key_data['key_id']}).encode('utf-8')
        put_req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
            data=data, headers=headers, method='PUT'
        )
        with urllib.request.urlopen(put_req) as res:
            print(f"OK GitHub Action Secret ({secret_name}) updated successfully.")
    except Exception as e:
        print(f"FAILED to update GitHub Secret: {e}")

if __name__ == "__main__":
    print(f"Setting CHECKOUT_BASE_URL={checkout_base_url}")

    # 1. Update .env locally
    if env_path.exists():
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write(f'\nCHECKOUT_BASE_URL="{checkout_base_url}"\n')
        print("OK Added CHECKOUT_BASE_URL to local .env file")

    # 2. Update Render Main (supremeai-backend)
    # বাংলা মন্তব্য: প্রাইমারি ও ব্যাকআপ অ্যাকাউন্টের সঠিক সার্ভিস আইডি সেট করে আপডেট করা হলো
    if render_key_main:
        update_render_env(render_key_main, "srv-d9d3n58js32c738n79k0", "CHECKOUT_BASE_URL", checkout_base_url)

    # 3. Update Render Backup (supremeai-backend)
    if render_key_backup:
        update_render_env(render_key_backup, "srv-d9e4q5rrjlhs73bnh71g", "CHECKOUT_BASE_URL", checkout_base_url)

    # 4. Update GitHub Secrets (requires PyNaCl)
    if github_token:
        try:
            import nacl
            update_github_secret(github_token, "paykaribazaronline/supremeai", "CHECKOUT_BASE_URL", checkout_base_url)
        except ImportError:
            print("FAILED PyNaCl not installed. Cannot update GitHub secrets automatically. Skipping.")

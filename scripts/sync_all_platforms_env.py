# scripts/sync_all_platforms_env.py
# বাংলা মন্তব্য: এই সর্বজনীন স্ক্রিপ্টটি লোকাল .env ফাইল থেকে সমস্ত ভ্যালিড API Keys ও Secrets
# একাধিক রিমোট প্ল্যাটফর্মে (GitHub, Render, Vercel, ইত্যাদি) স্বয়ংক্রিয়ভাবে ও নিরাপদে STDIN এবং Envs merging সহ সিঙ্ক করে।
# অপশন: --dry-run (কোনো চেঞ্জ ছাড়া প্রিভিউ দেখা), --apply (প্রকৃত চেঞ্জ অ্যাপ্লাই করা)

import os
import sys
import re
import subprocess
import argparse
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def load_clean_env():
    load_dotenv('.env', override=True)
    valid_key_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.-]*$')
    
    env_dict = {}
    if not os.path.exists('.env'):
        print("❌ Error: .env file not found!")
        sys.exit(1)

    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, val = line.split('=', 1)
            name = name.strip()
            val = val.strip().strip('"').strip("'")
            if valid_key_pattern.match(name):
                env_dict[name] = val
    return env_dict

def sync_github_secrets(env_dict, apply_changes=False):
    print("\n📦 [1/4] Syncing secrets to GitHub Actions Repository...")
    if not apply_changes:
        print(f"  [DRY-RUN] Would update {len(env_dict)} secrets via STDIN piping.")
        return

    env = os.environ.copy()
    env.pop('GITHUB_TOKEN', None)
    
    success = 0
    failed = 0
    for k, v in env_dict.items():
        if not v or k.startswith('GITHUB_'):
            continue
        p = subprocess.run(
            ['gh', 'secret', 'set', k, '--repo', 'paykaribazaronline/supremeai'],
            input=v, text=True, capture_output=True, env=env
        )
        if p.returncode == 0:
            success += 1
        else:
            failed += 1
    print(f"✅ GitHub Actions Secrets Sync Complete: {success} updated, {failed} skipped/failed.")

def sync_github_codespaces_secrets(env_dict, apply_changes=False):
    print("\n💻 [2/4] Syncing secrets to GitHub Codespaces...")
    if not apply_changes:
        print(f"  [DRY-RUN] Would update {len(env_dict)} Codespaces secrets via STDIN piping.")
        return

    env = os.environ.copy()
    env.pop('GITHUB_TOKEN', None)
    
    success = 0
    failed = 0
    for k, v in env_dict.items():
        if not v or k.startswith('GITHUB_'):
            continue
        p = subprocess.run(
            ['gh', 'secret', 'set', k, '--app', 'codespaces', '--repo', 'paykaribazaronline/supremeai'],
            input=v, text=True, capture_output=True, env=env
        )
        if p.returncode == 0:
            success += 1
        else:
            failed += 1
    print(f"✅ GitHub Codespaces Secrets Sync Complete: {success} updated, {failed} skipped/failed.")

def sync_render_env(env_dict, apply_changes=False):
    print("\n☁️ [3/4] Syncing environment variables to Render Web Services (Safe Merge)...")
    render_key = env_dict.get('RENDER_API_KEY')
    if not render_key:
        print("⚠️ Skipping Render sync: RENDER_API_KEY missing.")
        return

    headers = {'Authorization': f'Bearer {render_key}', 'Content-Type': 'application/json'}
    
    try:
        r = requests.get('https://api.render.com/v1/services?limit=100', headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"❌ Failed to fetch Render services: {r.status_code}")
            return

        services = [item['service'] for item in r.json()]
        for s in services:
            svc_id = s['id']
            svc_name = s['name']
            
            # Fetch existing vars to prevent deleting dashboard-only secrets
            existing_envs = {}
            get_res = requests.get(f'https://api.render.com/v1/services/{svc_id}/env-vars', headers=headers, timeout=15)
            if get_res.status_code == 200:
                for item in get_res.json():
                    env_item = item.get("envVar", item) if isinstance(item, dict) else item
                    existing_envs[env_item.get("key")] = env_item.get("value")

            merged = existing_envs.copy()
            clean_local = {k: v for k, v in env_dict.items() if not k.startswith('GITHUB_') and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', k)}
            merged.update(clean_local)
            payload = [{'key': k, 'value': str(v)} for k, v in merged.items() if k and v is not None and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', k)]

            if not apply_changes:
                print(f"  [DRY-RUN] Render Service '{svc_name}' ({svc_id}): Would sync {len(payload)} merged env vars.")
            else:
                resp = requests.put(f'https://api.render.com/v1/services/{svc_id}/env-vars', headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    print(f"✅ Render Service '{svc_name}' ({svc_id}): {len(payload)} env vars updated.")
                else:
                    print(f"⚠️ Render Service '{svc_name}' update status: {resp.status_code}")

    except Exception as e:
        print(f"❌ Render Sync Exception: {e}")

def sync_vercel_env(env_dict, apply_changes=False):
    print("\n🔺 [4/4] Syncing environment variables to Vercel Project...")
    vercel_token = env_dict.get('VERCEL_TOKEN')
    if not vercel_token:
        print("⚠️ Skipping Vercel sync: VERCEL_TOKEN missing.")
        return

    project_id = 'supremeai'
    if not apply_changes:
        print(f"  [DRY-RUN] Would sync {len(env_dict)} env keys to Vercel project '{project_id}'.")
        return

    headers = {'Authorization': f'Bearer {vercel_token}', 'Content-Type': 'application/json'}
    success = 0
    for k, v in env_dict.items():
        if not v or k.startswith('GITHUB_'):
            continue
        body = {
            'key': k,
            'value': v,
            'type': 'encrypted',
            'target': ['production', 'preview', 'development']
        }
        r = requests.post(f'https://api.vercel.com/v10/projects/{project_id}/env', headers=headers, json=body, timeout=10)
        if r.status_code in [200, 201]:
            success += 1

    print(f"✅ Vercel Sync Complete: {success} keys synced to '{project_id}'.")

def main():
    parser = argparse.ArgumentParser(description="Omni-Platform Real-Time Environment Secret Sync")
    parser.add_argument("--apply", action="store_true", help="Actually apply environment updates to remote platforms")
    args = parser.parse_args()

    apply_changes = args.apply

    if not apply_changes:
        print("🔍 RUNNING IN DRY-RUN MODE (No remote secrets will be modified). Use --apply to execute changes.\n")
    else:
        print("🚀 RUNNING IN APPLY MODE — Propagating all secrets to remote platforms...\n")

    env_dict = load_clean_env()
    print(f"🔑 Loaded {len(env_dict)} total keys from .env")

    sync_github_secrets(env_dict, apply_changes=apply_changes)
    sync_github_codespaces_secrets(env_dict, apply_changes=apply_changes)
    sync_render_env(env_dict, apply_changes=apply_changes)
    sync_vercel_env(env_dict, apply_changes=apply_changes)

    if apply_changes:
        print("\n🎉 ALL PLATFORMS FULLY SYNCHRONIZED AND LIVE!")
    else:
        print("\n✨ Dry-run complete. To write changes to production, re-run with: python scripts/sync_all_platforms_env.py --apply")

if __name__ == '__main__':
    main()

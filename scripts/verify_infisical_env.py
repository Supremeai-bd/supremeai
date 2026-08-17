#!/usr/bin/env python3
# scripts/verify_infisical_env.py
from __future__ import annotations

"""
বাংলা: Infisical Vault-এ সব প্রয়োজনীয় সিক্রেট আছে কিনা তা চেক করার স্ক্রিপ্ট।

REWRITE NOTE (drift-fix): আগে এই script `docs/env_maintenance_policy.md` থেকে
key list পড়ত (via parse_env_policy.py) — যেটা `secrets_registry.yaml` থেকে
সম্পূর্ণ আলাদা, নিজে থেকে maintain হওয়া একটা দ্বিতীয় "single source of truth"
ছিল। দুটো ফাইল একই `infisical-vault` environment-এর জন্য ভিন্ন সংখ্যক key বলছিল
(policy.md ৬১টা, registry.yaml ১৩৭+টা) — কেউ একটাতে key যোগ করলে অন্যটা জানতই না।
এখন থেকে এই script সরাসরি `secrets_registry.yaml` পড়ে, ঠিক audit_env_usage.py-র
মতো একই criticality tier (critical/important/optional) সম্মান করে — একটাই
source of truth।
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Set

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import yaml
except ImportError:
    print("::error::PyYAML ইনস্টল করা নাই — `pip install pyyaml` চালান।")
    sys.exit(1)

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "secrets_registry.yaml")
TARGET_ENV = "infisical-vault"


def load_registry_keys(path: str) -> dict[str, str]:
    """বাংলা: registry থেকে {key_name: criticality} ম্যাপ বের করে, শুধু
    infisical-vault-এ entry থাকা key গুলোর জন্য।"""
    if not os.path.exists(path):
        print(f"::error::Registry ফাইল পাওয়া যায়নি: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    result: dict[str, str] = {}
    for entry in data.get("keys", []):
        name = entry.get("name")
        crit_map = entry.get("criticality", {})
        if isinstance(crit_map, str):
            continue  # legacy flat-string entries — infisical-vault-specific না
        if name and TARGET_ENV in crit_map:
            result[name] = crit_map[TARGET_ENV]
    return result


def get_infisical_token(client_id: str, client_secret: str) -> Optional[str]:
    # বাংলা: Infisical Universal Auth (Machine Identity) এর মাধ্যমে Access Token পাওয়ার এপিআই কল।
    # এটি Client ID এবং Client Secret গ্রহণ করে ১ ঘণ্টার জন্য মেয়াদ থাকা Bearer Token রিটার্ন করে।
    # ফেইল হলে sys.exit নয় — None রিটার্ন করে যাতে main() INFISICAL_TOKEN-এ fallback করতে পারে।
    url = "https://app.infisical.com/api/v1/auth/universal-auth/login"
    payload = json.dumps({"clientId": client_id, "clientSecret": client_secret}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data.get("accessToken")
    except urllib.error.HTTPError as e:
        print(f"::warning::Infisical Universal Auth HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}")
        return None
    except Exception as e:
        print(f"::warning::Infisical Universal Auth failed: {e}")
        return None


def load_env_fallback(key: str) -> Optional[str]:
    # বাংলা: os.environ-এ ভ্যালু না থাকলে local .env ফাইল থেকে পড়ার চেষ্টা করে
    val = os.environ.get(key)
    if val:
        return val
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith(f"{key}="):
                        return line.split("=", 1)[1].strip('"\'')
        except Exception:
            pass
    return None


def fetch_infisical_secrets(project_id: Optional[str], token: str, env: str = "prod") -> Set[str]:
    # বাংলা: project_id থাকলে workspaceId পাঠাব, না থাকলে শুধু environment পাঠাব
    if project_id and project_id.strip():
        url = f"https://app.infisical.com/api/v3/secrets/raw?workspaceId={project_id.strip()}&environment={env}"
    else:
        url = f"https://app.infisical.com/api/v3/secrets/raw?environment={env}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            secrets = data.get("secrets", [])
            return {s.get("secretKey") for s in secrets if s.get("secretKey")}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", "ignore")
        print(f"::error::Failed to fetch secrets from Infisical API (HTTP {e.code}): {err_msg}")
        sys.exit(1)
    except Exception as e:
        print(f"::error::Failed to fetch secrets from Infisical API: {e}")
        sys.exit(1)


def main() -> int:
    client_id = load_env_fallback("INFISICAL_CLIENT_ID")
    client_secret = load_env_fallback("INFISICAL_CLIENT_SECRET")
    project_id = load_env_fallback("INFISICAL_PROJECT_ID")
    env = load_env_fallback("INFISICAL_ENV") or "prod"

    if not client_id or not client_secret or not project_id:
        # Fallback to Service Token if Universal Auth is not available
        service_token = load_env_fallback("INFISICAL_TOKEN")
        if not service_token:
            print("::error::INFISICAL_CLIENT_ID/SECRET or INFISICAL_TOKEN is missing!")
            sys.exit(1)
        print("[info] Using INFISICAL_TOKEN (Service Token) for authentication.")
        access_token = service_token
    else:
        print("[info] Using Universal Auth (Machine Identity) for authentication.")
        access_token = get_infisical_token(client_id, client_secret)
        if not access_token:
            # বাংলা: Universal Auth (Machine Identity) fail হলে Service Token-এ fallback —
            # যাতে credential drift/rotation অসম্পূর্ণ থাকলেও vault health check ব্লক না হয়।
            service_token = load_env_fallback("INFISICAL_TOKEN")
            if not service_token:
                print("::error::Universal Auth failed এবং INFISICAL_TOKEN-ও missing! Machine Identity credential ঠিক করুন বা INFISICAL_TOKEN সেট করুন।")
                sys.exit(1)
            print("::warning::Universal Auth fail — INFISICAL_TOKEN (Service Token)-এ fallback করা হলো।")
            access_token = service_token

    registry_keys = load_registry_keys(REGISTRY_PATH)
    present = fetch_infisical_secrets(project_id, access_token, env)

    print(f"=== Infisical Vault Health Check [{env}] ===")
    print(f"[info] Infisical-এ সর্বমোট সিক্রেট সংখ্যা: {len(present)}")
    print(f"[info] secrets_registry.yaml-এ {TARGET_ENV}-এর জন্য tracked key সংখ্যা: {len(registry_keys)}")

    has_critical_failure = False
    warnings = 0

    for name in sorted(registry_keys):
        crit = registry_keys[name]
        if name in present:
            continue
        if crit == "critical":
            print(f"::error::CRITICAL secret missing in Infisical: {name} (production boot will crash)")
            has_critical_failure = True
        elif crit == "important":
            print(f"::warning::IMPORTANT secret missing in Infisical: {name} (feature degraded)")
            warnings += 1
        else:
            print(f"[optional] secret missing in Infisical: {name} (feature disabled)")
            warnings += 1

    if has_critical_failure:
        print("\n❌ FAIL: Infisical-এ এক বা একাধিক critical সিক্রেট মিসিং!")
        return 1

    if warnings:
        print(f"\n⚠️ PASS with {warnings} warning(s): critical সব ঠিক আছে, কিছু important/optional key মিসিং।")
    else:
        print("\n✅ PASS: Infisical-এ সব tracked সিক্রেট উপস্থিত আছে!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

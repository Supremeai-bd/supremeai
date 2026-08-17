#!/usr/bin/env python3
# scripts/verify_render_env.py
"""
বাংলা: Render API থেকে প্রকৃত service env vars fetch করে secrets_registry.yaml-এর
বিপরীতে চেক করে। এটি Gap #3 বন্ধ করে: CI GitHub secrets-এ set থাকলেও যদি Render
service-এর env-এ না থাকে, তবে এখানে ধরা পড়বে (production 503/crash এড়াতে)।

REWRITE NOTE (drift-fix & registry alignment): আগে এই script `docs/env_maintenance_policy.md`
থেকে key list পড়ত (via parse_env_policy.py)। এখন সরাসরি `secrets_registry.yaml` থেকে
target env (render-backend, render-admin, render-worker) অনুযায়ী tracked key এবং
criticality level (critical/important/optional) রিড করে — single source of truth।

নিরাপত্তা: কোনো secret ভ্যালু log-এ যায় না — শুধু key name।
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

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
RENDER_API = "https://api.render.com/v1"


def load_registry_keys(path: str, target_env: str) -> dict[str, str]:
    """
    বাংলা: secrets_registry.yaml থেকে {key_name: criticality} ম্যাপ বের করে,
    নির্দিষ্ট target_env (যেমন render-backend, render-admin, render-worker) এর জন্য।
    """
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
            continue  # legacy flat-string entries স্কিপ
        if name and target_env in crit_map:
            result[name] = crit_map[target_env]
    return result


def fetch_render_env(service_id: str, api_key: str) -> dict[str, str | None]:
    """
    বাংলা: Render API থেকে service env var-এর key গুলোর dict ফেরত দেয়।
    Note: Render API সিক্রেট ভ্যালু লুকায় (sync:false manual secrets) — তাই value=None আসতে পারে।
    """
    url = f"{RENDER_API}/services/{service_id}/env-vars?limit=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"::error::Render API call failed for {service_id}: HTTP {e.code} {body[:200]}")
        sys.exit(1)
    except Exception as e:  # network/timeout
        print(f"::error::Render API unreachable: {e}")
        sys.exit(1)

    env_data: dict[str, str | None] = {}
    items = payload if isinstance(payload, list) else payload.get("envVars", [])
    for item in items:
        ev = item.get("envVar", item)
        key = ev.get("key")
        val = ev.get("value")  # manual sync secrets-এ None আসে
        if key:
            env_data[key] = val
    return env_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Render runtime env vs registry")
    parser.add_argument("--env", required=True, choices=["render-backend", "render-admin", "render-worker"])
    parser.add_argument("--service-id", required=True, help="Render service ID")
    args = parser.parse_args()

    # বাংলা: admin env-এর জন্য backup key ব্যবহার, অন্যথায় primary key
    if args.env == "render-admin":
        api_key = os.environ.get("RENDER_API_KEY_BACKUP") or os.environ.get("RENDER_API_KEY")
    else:
        api_key = os.environ.get("RENDER_API_KEY")

    if not api_key:
        print("::error::RENDER_API_KEY/BACKUP env চার্জ করা হয়নি (GitHub secret থেকে ইনজেক্ট করুন)।")
        sys.exit(1)

    # বাংলা: secrets_registry.yaml থেকে এই target env-এর জন্য tracked keys ও criticality লোড করো
    registry_keys = load_registry_keys(REGISTRY_PATH, args.env)

    if not registry_keys:
        print(f"[info] কোনো tracked keys পাওয়া যায়নি {args.env}-এর জন্য secrets_registry.yaml ফাইলে।")
        return 0

    # বাংলা: Render API থেকে service-এর actual env var keys fetch করো
    present_keys = fetch_render_env(args.service_id, api_key)
    print(f"=== Render Runtime Env Health Check [{args.env}] ===")
    print(f"[info] Render [{args.env}] service-এ পাওয়া env var সংখ্যা: {len(present_keys)}")
    print(f"[info] secrets_registry.yaml-এ [{args.env}]-এর জন্য tracked key সংখ্যা: {len(registry_keys)}")

    has_critical_failure = False
    warnings = 0

    for name in sorted(registry_keys):
        crit = registry_keys[name]
        if name in present_keys:
            continue
        if crit == "critical":
            print(f"::error::CRITICAL key missing in Render [{args.env}]: {name} — সার্ভার boot crash হবে!")
            has_critical_failure = True
        elif crit == "important":
            print(f"::warning::IMPORTANT key missing in Render [{args.env}]: {name} — ফিচারের পারফরম্যান্স হ্রাস পাবে।")
            warnings += 1
        else:
            print(f"[optional] key missing in Render [{args.env}]: {name} (optional feature disabled)")
            warnings += 1

    if has_critical_failure:
        print(f"\n❌ FAIL [{args.env}]: এক বা একাধিক critical key missing! Render deploy crash করবে।")
        return 1

    if warnings:
        print(f"\n⚠️ PASS [{args.env}] with {warnings} warning(s): critical সব ঠিক আছে, কিছু important/optional key missing।")
    else:
        print(f"\n✅ PASS [{args.env}]: সব tracked key Render-এ উপস্থিত।")

    return 0


if __name__ == "__main__":
    sys.exit(main())

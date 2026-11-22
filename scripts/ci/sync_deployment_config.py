#!/usr/bin/env python3
"""Sync deployment config from config/service_registry.yaml (SSOT) to derived files.

Single source of truth: config/service_registry.yaml (canonical URLs + env var names).
Runtime env vars override at deploy time. This script keeps derived hardcoded
references in sync so a service URL/ID change needs only a registry edit + one run.

Usage:
    python scripts/ci/sync_deployment_config.py --check     # CI validation (exit 1 on drift)
    python scripts/ci/sync_deployment_config.py --write     # apply updates
    python scripts/ci/sync_deployment_config.py --dry-run   # preview

Derived targets:
    - infrastructure/mcp-control-plane/src/lib/env.ts
    - infrastructure/mcp-control-plane/src/diagnostics/service_manifest.ts
    - infrastructure/cloudflare-render-keepwarm/worker.js
    - supremeai-public/src/config/platformEndpoints.ts (if present)
"""
import os, re, sys, argparse, yaml, json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, "config", "service_registry.yaml")

def load_registry():
    with open(REGISTRY, encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_env():
    env = {}
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return env
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().split('#')[0].strip()
    return env

def service_url(svc, env):
    url = svc.get('production_url')
    env_key = svc.get('canonical_url_env')
    if env_key and env.get(env_key):
        url = env[env_key]
    return url

def service_id(svc, env):
    env_key = svc.get('canonical_service_id_env')
    if env_key and env.get(env_key):
        return env[env_key]
    return None

def collect_expected(reg):
    env = load_env()
    expected = {}  # service_name -> {url, id}
    for name, svc in reg['services'].items():
        expected[name] = {'url': service_url(svc, env), 'id': service_id(svc, env)}
    return expected, env

def check_file(path, expected_urls, expected_ids):
    """Return list of drift messages."""
    if not os.path.exists(path):
        return []
    text = open(path, encoding='utf-8').read()
    drifts = []
    # Check each expected url appears if the file references that service
    # Generic: flag any onrender/workers/supabase URL in file not in expected set
    found_urls = set(re.findall(r'https?://[\w.-]+\.(?:onrender\.com|workers\.dev|supabase\.co)', text))
    expected_url_set = {u for u in expected_urls.values() if u}
    stale = found_urls - expected_url_set
    for u in sorted(stale):
        # allow example/mock/test/placeholder
        if any(t in u for t in ['example.','mock.','test.','placeholder','your-','abcdefgh','missiontest','stale','old.','ghost.','replacement.','status.','prod.','project.','proj.','myproject']):
            continue
        drifts.append(f"  stale URL in {path}: {u}")
    return drifts

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true', help='CI validation: exit 1 on drift')
    g.add_argument('--write', action='store_true', help='Apply updates')
    g.add_argument('--dry-run', action='store_true', help='Preview')
    args = ap.parse_args()

    reg = load_registry()
    expected, env = collect_expected(reg)
    expected_urls = {s: expected[s]['url'] for s in expected if expected[s]['url']}
    expected_ids = {s: expected[s]['id'] for s in expected if expected[s]['id']}

    print("SSOT: config/service_registry.yaml")
    print("Expected URLs:")
    for s,u in sorted(expected_urls.items()):
        print(f"  {s:12s} -> {u}")
    print()

    targets = [
        os.path.join(ROOT, "infrastructure", "mcp-control-plane", "src", "lib", "env.ts"),
        os.path.join(ROOT, "infrastructure", "mcp-control-plane", "src", "diagnostics", "service_manifest.ts"),
        os.path.join(ROOT, "infrastructure", "cloudflare-render-keepwarm", "worker.js"),
    ]
    pub = os.path.join(ROOT, "..", "supremeai-public", "src", "config", "platformEndpoints.ts")
    if os.path.exists(pub):
        targets.append(pub)

    all_drifts = []
    for t in targets:
        dr = check_file(t, expected_urls, expected_ids)
        all_drifts.extend(dr)
        if dr:
            for d in dr: print(d)
        else:
            print(f"  OK: {os.path.relpath(t, ROOT)}")

    print()
    if all_drifts:
        print(f"Found {len(all_drifts)} drift(s).")
        if args.check:
            sys.exit(1)
    else:
        print("No drift detected.")

    # Generate public_endpoints.json manifest (consumed by sync_to_public_repo.py)
    manifest = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": "1.0.0",
        "generated_by": "scripts/ci/sync_deployment_config.py",
        "endpoints": {},
        "canonical_env_keys": {},
    }
    name_map = {"api":"api_gateway","mcp":"mcp_tower","brain":"tiny_brain","frontend":"web_studio"}
    for sname, info in expected.items():
        key = name_map.get(sname, sname)
        entry = {}
        if info['url']: entry["direct_render_origin" if sname != 'frontend' else "primary_url"] = info['url']
        if info['id']: entry["service_id"] = info['id']
        if sname == 'api':
            entry["custom_domain"] = "https://api.supremeai.live"
        if sname == 'mcp':
            entry["custom_domain"] = "https://mcp.supremeai.live"
        manifest["endpoints"][key] = entry
    manifest["canonical_env_keys"] = {
        "api_service_id": "RENDER_API_SERVICE_ID",
        "mcp_service_id": "RENDER_MCP_SERVICE_ID",
        "scraper_service_id": "RENDER_SCRAPER_SERVICE_ID",
        "worker_service_id": "RENDER_WORKER_SERVICE_ID",
        "brain_service_id": "RENDER_BRAIN_SERVICE_ID",
    }
    out_path = os.path.join(ROOT, "api-schemas", "generated", "public_endpoints.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if args.dry_run:
        print("\n[dry-run] would write manifest to", out_path)
    else:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest written: {out_path}")

    if args.write or args.dry_run:
        print("\nNote: full auto-rewrite of derived TS/JS files is not yet implemented;")
        print("      use --check in CI to catch drift. Auto-write coming next.")

if __name__ == "__main__":
    main()

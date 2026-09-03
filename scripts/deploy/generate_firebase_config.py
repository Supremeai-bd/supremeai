#!/usr/bin/env python3
"""
Deterministic Firebase Configuration Generator.
Reads `firebase.template.json` and deterministically substitutes the backend URLs.
Fails fast if required environment variables are missing or if any placeholders remain.
"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def generate_firebase_config():
    template_path = "firebase.template.json"
    output_path = "firebase.json"
    
    print("=== Generating Firebase Configuration ===")
    
    if not os.path.exists(template_path):
        print(f"❌ ERROR: Template file {template_path} not found.")
        sys.exit(1)
        
    backend_url = os.getenv("BACKEND_URL") or os.getenv("VITE_BACKEND_URL") or os.getenv("VITE_API_URL") or os.getenv("USER_BACKEND_URL") or os.getenv("VITE_USER_BACKEND")
    
    if not backend_url:
        print("❌ ERROR: BACKEND_URL (or VITE_BACKEND_URL / VITE_API_URL) must be set in the environment.")
        sys.exit(1)
        
    with open(template_path, "r", encoding="utf-8") as f:
        config_text = f.read()
        
    # Unify all placeholders to the single backend URL
    config_text = config_text.replace("{{BACKEND_URL}}", backend_url)
    config_text = config_text.replace("{{USER_BACKEND_URL}}", backend_url)
    config_text = config_text.replace("{{ADMIN_BACKEND_URL}}", backend_url)
    
    if "{{" in config_text or "}}" in config_text:
        print("❌ ERROR: Unresolved placeholders remain in the generated firebase.json.")
        sys.exit(1)
        
    try:
        config_json = json.loads(config_text)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Generated firebase.json is not valid JSON. {e}")
        sys.exit(1)
        
    # Verify rewrite semantics
    hosting = config_json.get("hosting", [])
    if isinstance(hosting, dict):
        hosting = [hosting]
        
    for site in hosting:
        rewrites = site.get("rewrites", [])
        has_api_rewrite = any(rw.get("source") == "/api/**" for rw in rewrites)
        if not has_api_rewrite:
            print(f"⚠️ WARNING: No /api/** rewrite found for site: {site.get('target', 'default')}")
            
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_json, f, indent=2)
        
    print(f"✅ Successfully generated {output_path}")
    print(f"   Backend URL: {backend_url}")

if __name__ == "__main__":
    generate_firebase_config()

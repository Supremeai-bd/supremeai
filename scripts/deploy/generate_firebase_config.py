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
        
    user_backend = os.getenv("USER_BACKEND_URL") or os.getenv("VITE_USER_BACKEND")
    admin_backend = os.getenv("ADMIN_BACKEND_URL") or os.getenv("VITE_ADMIN_BACKEND")
    
    if not user_backend:
        print("❌ ERROR: USER_BACKEND_URL (or VITE_USER_BACKEND) must be set in the environment.")
        sys.exit(1)
        
    if not admin_backend:
        print("❌ ERROR: ADMIN_BACKEND_URL (or VITE_ADMIN_BACKEND) must be set in the environment.")
        sys.exit(1)
        
    with open(template_path, "r", encoding="utf-8") as f:
        config_text = f.read()
        
    config_text = config_text.replace("{{USER_BACKEND_URL}}", user_backend)
    config_text = config_text.replace("{{ADMIN_BACKEND_URL}}", admin_backend)
    
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
        target = site.get("target", "")
        rewrites = site.get("rewrites", [])
        has_api_rewrite = False
        for rw in rewrites:
            if rw.get("source") == "/api/**":
                has_api_rewrite = True
                dest = rw.get("destination", "")
                if target == "admin" and not dest.startswith(admin_backend):
                    print(f"❌ ERROR: Admin target routes to incorrect backend: {dest}")
                    sys.exit(1)
                elif target == "user" and not dest.startswith(user_backend):
                    print(f"❌ ERROR: User target routes to incorrect backend: {dest}")
                    sys.exit(1)
        
        if not has_api_rewrite and target != "admin":
            print(f"⚠️ WARNING: No /api/** rewrite found for target: {target}")
            
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_json, f, indent=2)
        
    print(f"✅ Successfully generated {output_path}")
    print(f"   User Backend: {user_backend}")
    print(f"   Admin Backend: {admin_backend}")

if __name__ == "__main__":
    generate_firebase_config()

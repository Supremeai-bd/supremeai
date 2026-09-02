import json
import os
import urllib.request

# SCRUBBED (Master Audit 2026-09-02): hardcoded Render API keys removed.
# Keys are read from the environment (acct1/core, acct2/worker, acct3/scraper).
services = [
    ('Core', 'srv-dabm7dfqj5pc738jkbmg', os.environ.get('RENDER_API_KEY_1', ''), 'core'),
    ('Worker', 'srv-dabm7evqj5pc738jkf30', os.environ.get('RENDER_API_KEY_2', ''), 'worker'),
    ('Scraper', 'srv-dabm7gfqj5pc738jkicg', os.environ.get('RENDER_API_KEY_3', ''), 'scraper')
]

for name, svc_id, token, role in services:
    print(f"Updating {name}...")
    try:
        # Get current env vars
        req = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc_id}/env-vars",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            current_vars = json.loads(resp.read().decode())

        env_vars = []
        found = False
        for v in current_vars:
            key = v["envVar"]["key"]
            if key == "SUPREMEAI_SERVICE_ROLE":
                env_vars.append({"key": key, "value": role})
                found = True
            else:
                env_vars.append({"key": key, "value": v["envVar"]["value"]})

        if not found:
            env_vars.append({"key": "SUPREMEAI_SERVICE_ROLE", "value": role})

        # Update env vars
        req_update = urllib.request.Request(
            f"https://api.render.com/v1/services/{svc_id}/env-vars",
            data=json.dumps(env_vars).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req_update) as resp:
            print(f"[{name}] Successfully updated SUPREMEAI_SERVICE_ROLE={role}")
            
    except Exception as e:
        print(f"[{name}] Error: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode())

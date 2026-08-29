import os
import requests

RENDER_API_KEY = "***REMOVED***"
HEADERS = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json"
}

resp = requests.get(f"https://api.render.com/v1/env-groups?limit=100", headers=HEADERS)
if resp.status_code != 200:
    print("Failed to fetch env groups:", resp.status_code)
    exit(1)

groups = resp.json()
for g in groups:
    grp = g.get("envGroup", {})
    grp_id = grp.get("id")
    grp_name = grp.get("name")
    
    # Render env-groups endpoint structure is a bit different. Let's see envVars inside grp
    env_vars = grp.get("envVars", [])
    
    found = False
    put_data = []
    
    for item in env_vars:
        key = item.get("key")
        val = item.get("value", "")
        
        if key == "REDIS_URL" and val.startswith("redis://"):
            print(f"[EnvGroup: {grp_name}] Found REDIS_URL with redis://, changing to rediss://")
            val = val.replace("redis://", "rediss://", 1)
            found = True
            
        put_data.append({"key": key, "value": val})
        
    if found:
        # According to API, PUT /v1/env-groups/{id} updates the whole group
        # Wait, env-vars are nested inside the body for env-groups.
        # body: {"name": grp_name, "envVars": put_data}
        payload = {"name": grp_name, "envVars": put_data}
        update_resp = requests.put(f"https://api.render.com/v1/env-groups/{grp_id}", headers={"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"}, json=payload)
        if update_resp.status_code == 200:
            print(f"[EnvGroup: {grp_name}] Successfully updated REDIS_URL!")
        else:
            print(f"[EnvGroup: {grp_name}] Failed to update:", update_resp.status_code, update_resp.text)


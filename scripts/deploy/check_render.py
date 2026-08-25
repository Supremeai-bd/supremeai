import os
import urllib.request
import json

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
SERVICE_ID = "srv-da666f8u01pc739bm3t0"
URL = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys?limit=5"

req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for deploy in data:
            d = deploy['deploy']
            commit_id = d.get('commit', {})
            if commit_id is None:
                commit_id = {}
            print(f"ID: {d['id']} | Status: {d['status']} | Created: {d['createdAt']} | Finished: {d.get('finishedAt', 'N/A')} | Commit: {commit_id.get('id', 'N/A')}")
except Exception as e:
    print(f"Error fetching deploys: {e}")

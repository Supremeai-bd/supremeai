import os
import urllib.request
import json

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
SERVICE_ID = "srv-da666f8u01pc739bm3t0"
URL = f"https://api.render.com/v1/services/{SERVICE_ID}"

req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error fetching service details: {e}")

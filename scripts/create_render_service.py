import urllib.request
import json
import os

api_key = os.environ.get("RENDER_API_KEY", "")
url = "https://api.render.com/v1/services"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

data = {
    "type": "web_service",
    "name": "supremeai-backend-production",
    "ownerId": "tea-d747ms1aae7s73bcasu0",
    "serviceDetails": {
        "env": "image",
        "plan": "free",
        "region": "singapore",
        "envSpecificDetails": {
            "image": {
                "imagePath": "ghcr.io/paykaribazaronline/supremeai-backend:latest"
            }
        }
    }
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
try:
    with urllib.request.urlopen(req) as response:
        service = json.loads(response.read().decode())
        print("Success:", service['service']['url'])
except Exception as e:
    print(e.read().decode() if hasattr(e, 'read') else str(e))

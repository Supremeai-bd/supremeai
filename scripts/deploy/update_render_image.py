import json
import os
import urllib.request

service_id = 'srv-da5i4frm8hqs73cpp5hg'
api_key = os.environ.get("RENDER_API_KEY", "")

# Try to set env to image and provide imagePath
payload = {
    "serviceDetails": {
        "env": "image",
        "envSpecificDetails": {
            "imagePath": "ghcr.io/saifulhaqueniloy/supremeai/supremeai-core:main"
        }
    }
}

req = urllib.request.Request(
    f'https://api.render.com/v1/services/{service_id}',
    method='PATCH',
    headers={
        'Authorization': f'Bearer {api_key}', 
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    },
    data=json.dumps(payload).encode('utf-8')
)

try:
    with urllib.request.urlopen(req) as res:
        print("Success!")
        print(res.read().decode())
except Exception as e:
    print(f"Failed: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())

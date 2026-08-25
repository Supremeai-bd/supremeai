import os
import requests
import json

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
SERVICE_ID = 'srv-da666f8u01pc739bm3t0'
URL = f'https://api.render.com/v1/services/{SERVICE_ID}'

headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {RENDER_API_KEY}'
}

response = requests.get(URL, headers=headers)
if response.status_code == 200:
    data = response.json()
    print(json.dumps(data, indent=2))
else:
    print(f"Failed to fetch service: {response.text}")

import os

import requests

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
SERVICE_ID = 'srv-da666f8u01pc739bm3t0'
URL = f'https://api.render.com/v1/services/{SERVICE_ID}/deploys'

headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {RENDER_API_KEY}'
}

response = requests.post(URL, headers=headers, json={"clearCache": "do_not_clear"})
if response.status_code == 201:
    data = response.json()
    print(f"Deploy triggered successfully! Deploy ID: {data['id']}")
else:
    print(f"Failed to trigger deploy: {response.text}")

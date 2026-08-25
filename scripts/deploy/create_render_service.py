import os
import urllib.request, json
import sys

api_key = os.environ.get("RENDER_API_KEY", "")
req = urllib.request.Request(
    'https://api.render.com/v1/services?limit=10',
    method='GET',
    headers={
        'Authorization': f'Bearer {api_key}', 
        'Accept': 'application/json'
    }
)
try:
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode())
        for s in data:
            if s.get('service', {}).get('name') == 'supremeai-backend-v2':
                print("FOUND!")
                print(s['service']['id'])
                break
        else:
            print("Not found yet")
            print(json.dumps(data[:1], indent=2))
except Exception as e:
    print(f"Failed: {e}")

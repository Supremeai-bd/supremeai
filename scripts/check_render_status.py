# বাংলা মন্তব্য: Render service config চেক করার জন্য স্ক্রিপ্ট
import json
import re
import urllib.request

# .env থেকে Render API keys পড়া
content = open('.env', encoding='utf-8').read()
key = re.search(r'RENDER_API_KEY="([^"]+)"', content).group(1)
key2 = re.search(r'RENDER_API_KEY_BACKUP="([^"]+)"', content).group(1)

services = [
    ('srv-d9d3n58js32c738n79k0', 'User Backend', key),
    ('srv-d9fg48bh523c73f63bb0', 'Admin Backend', key2),
]

for svc_id, name, k in services:
    req = urllib.request.Request(
        f'https://api.render.com/v1/services/{svc_id}',
        headers={'Authorization': f'Bearer {k}'}
    )
    try:
        data = json.load(urllib.request.urlopen(req, timeout=15))
        print(f'=== {name} ({svc_id}) ===')
        print(f'  name: {data.get("name")}')
        print(f'  type: {data.get("type")}')
        print(f'  serviceDetails: {json.dumps(data.get("serviceDetails", {}), indent=2)[:1500]}')
    except Exception as e:
        print(f'{name}: ERROR {e}')
import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv('.env')

keys = [
    (os.getenv('RENDER_API_KEY_1'), os.getenv('RENDER_PRIMARY_SVC_ID')),
    (os.getenv('RENDER_API_KEY_2'), os.getenv('RENDER_WORKER_SVC_ID')),
    (os.getenv('RENDER_API_KEY_3'), os.getenv('RENDER_SCRAPER_SVC_ID')),
    (os.getenv('RENDER_API_KEY_4'), os.getenv('RENDER_MCP_SVC_ID')),
]

cors = '["https://supremeai.app","https://supremeai-a.web.app","https://supremeai-admin.web.app","https://supremeai.web.app","https://supremeai-lac.vercel.app","https://supremeai-studio-client.onrender.com","https://supremeai-primary-node.onrender.com"]'
user_cors = '["https://supremeai.app","https://supremeai-a.web.app","https://supremeai.web.app","https://supremeai-lac.vercel.app","https://supremeai-studio-client.onrender.com"]'
admin_cors = '["https://supremeai-admin.web.app","https://supremeai.app"]'

body = json.dumps([
    {'key': 'CORS_ORIGINS', 'value': cors},
    {'key': 'USER_CORS_ORIGINS', 'value': user_cors},
    {'key': 'ADMIN_CORS_ORIGINS', 'value': admin_cors}
]).encode('utf-8')

for k, srv in keys:
    if not k or not srv:
        print(f"Skipping empty key/srv: {k}, {srv}")
        continue
    req = urllib.request.Request(
        f'https://api.render.com/v1/services/{srv}/env-vars',
        data=body,
        headers={'Authorization': f'Bearer {k}', 'Content-Type': 'application/json'},
        method='PUT'
    )
    try:
        res = urllib.request.urlopen(req)
        print(f'{srv}: updated successfully')
    except Exception as e:
        if hasattr(e, 'read'):
            print(f'{srv}: error {e} - {e.read().decode("utf-8")}')
        else:
            print(f'{srv}: error {e}')

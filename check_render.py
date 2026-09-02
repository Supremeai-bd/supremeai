
import os, urllib.request, json
# SCRUBBED (Master Audit 2026-09-02): hardcoded Render API keys removed.
# Keys are read from the environment (Render API key for acct1/acct3).
keys = [os.environ.get('RENDER_API_KEY_1', ''), os.environ.get('RENDER_API_KEY_3', '')]
for k in keys:
    req = urllib.request.Request('https://api.render.com/v1/owners', headers={'Authorization': 'Bearer ' + k, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print('Key ending in ' + k[-4:] + ':')
            for owner in data:
                name = owner['owner']['name']
                print('  - Workspace: ' + name)
    except Exception as e:
        print('Key error: ' + str(e))


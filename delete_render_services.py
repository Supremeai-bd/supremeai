
import os, urllib.request, urllib.error
# SCRUBBED (Master Audit 2026-09-02): hardcoded Render API keys removed.
# Keys are read from the environment (acct1/acct3).
keys = {
    'ghGP': os.environ.get('RENDER_API_KEY_1', ''),
    'DSHV': os.environ.get('RENDER_API_KEY_3', '')
}

services_to_delete = {
    os.environ.get('RENDER_API_KEY_1', ''): [
        'srv-dabgugdg1s2s73cmcha0', # worker
        'srv-dabgtp7avr4c73855fgg', # scraper
        'srv-daabrass728c73fuongg', # ecosystem
        'srv-da666f8u01pc739bm3t0'  # backend-v2
    ],
    os.environ.get('RENDER_API_KEY_3', ''): [
        'srv-daacds1srm7s73eif4kg' # ecosystem-test-worker
    ]
}

for key, svcs in services_to_delete.items():
    for svc_id in svcs:
        url = f'https://api.render.com/v1/services/{svc_id}'
        req = urllib.request.Request(url, method='DELETE', headers={'Authorization': 'Bearer ' + key})
        try:
            with urllib.request.urlopen(req) as response:
                print(f'Deleted service {svc_id}')
        except urllib.error.HTTPError as e:
            print(f'Failed to delete {svc_id}: {e.code} - {e.reason}')
        except Exception as e:
            print(f'Error deleting {svc_id}: {e}')


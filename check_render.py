import urllib.request, json
service_id = 'srv-da5i4frm8hqs73cpp5hg'
api_key = '***REMOVED***'

req = urllib.request.Request(
    f'https://api.render.com/v1/services/{service_id}/env-vars',
    headers={'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    env_vars = json.loads(res.read().decode())
    for item in env_vars:
        if 'INFISICAL' in item['envVar']['key'] or 'ENV' in item['envVar']['key']:
            print(f"{item['envVar']['key']} = {item['envVar']['value'][:5]}...")

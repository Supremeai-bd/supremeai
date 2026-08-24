import urllib.request, json
API_KEY = '***REMOVED***'
svc_id = 'srv-da5i4frm8hqs73cpp5hg'
try:
    req = urllib.request.Request(f'https://api.render.com/v1/services/{svc_id}/deploys?limit=2', headers={'Authorization': f'Bearer {API_KEY}'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        if data:
            for d in data:
                deploy = d['deploy']
                print(f"ID: {deploy['id']}")
                print(f"Status: {deploy['status']}")
                print(f"Created At: {deploy['createdAt']}")
                print(f"Finished At: {deploy.get('finishedAt', 'N/A')}")
                if 'commit' in deploy:
                    print(f"Commit: {deploy['commit']['id']} - {deploy['commit']['message']}")
                print('---')
        else:
            print('No deployments found.')
except Exception as e:
    print(f'Error: {e}')

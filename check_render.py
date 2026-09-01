
import urllib.request, json
keys = ['***REMOVED***', '***REMOVED***']
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


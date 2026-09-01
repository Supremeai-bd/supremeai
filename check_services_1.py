
import urllib.request, json
k = '***REMOVED***'
req = urllib.request.Request('https://api.render.com/v1/services', headers={'Authorization': 'Bearer ' + k, 'Accept': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for service in data:
            print('Service: ' + service['service']['name'] + ' | ID: ' + service['service']['id'] + ' | URL: ' + service['service'].get('serviceDetails', {}).get('url', 'N/A'))
except Exception as e:
    print('Key error: ' + str(e))

